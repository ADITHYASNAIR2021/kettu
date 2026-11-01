"""REST API used by the PWA. Seven endpoints, as in the PRD, plus /v1/languages."""

import asyncio
import json
import logging
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from kettu.container import Context, get_ctx
from kettu.domain import languages
from kettu.domain.errors import ErrorCode, KettuError
from kettu.services import audio

log = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_SUFFIXES = {".opus", ".ogg", ".oga", ".m4a", ".mp3", ".wav", ".aac", ".amr", ".webm", ".mp4", ".3gp", ".flac"}


def _device(device_id: str | None) -> str:
    try:
        return str(uuid.UUID(str(device_id)))
    except (ValueError, TypeError):
        raise KettuError(ErrorCode.BAD_REQUEST, "Missing or invalid device id.")


def _lang(code: str | None, field: str) -> str:
    if not languages.is_supported(code):
        raise KettuError(ErrorCode.BAD_REQUEST, f"Unsupported language for {field}.")
    return code  # type: ignore[return-value]


def _parse_list(raw: str | None, limit: int) -> list[str]:
    if not raw:
        return []
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            items = [str(items)]
    except json.JSONDecodeError:
        items = raw.split(",")
    return [str(i).strip()[:60] for i in items if str(i).strip()][:limit]


async def save_upload(upload: UploadFile, max_mb: float) -> Path:
    """Stream the upload to a private temp folder, refusing oversize files early."""
    suffix = Path(upload.filename or "note.ogg").suffix.lower() or ".ogg"
    ctype = (upload.content_type or "").lower()
    if suffix not in ALLOWED_SUFFIXES and not ctype.startswith(("audio/", "video/")) and ctype != "application/ogg":
        raise KettuError(ErrorCode.UNSUPPORTED_FILE)
    folder = Path(tempfile.mkdtemp(prefix="kettu_up_"))
    dst = folder / f"upload{suffix if suffix in ALLOWED_SUFFIXES else '.bin'}"
    limit = int(max_mb * 1024 * 1024)
    written = 0
    try:
        with dst.open("wb") as f:
            while chunk := await upload.read(1024 * 256):
                written += len(chunk)
                if written > limit:
                    raise KettuError(ErrorCode.TOO_BIG)
                f.write(chunk)
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return dst


def discard(path: Path) -> None:
    shutil.rmtree(path.parent, ignore_errors=True)


# ---------------------------------------------------------------- notes


@router.post("/v1/notes", status_code=202)
async def create_note(request: Request, ctx: Context = Depends(get_ctx)):
    form = await request.form()
    upload = form.get("audio")
    if not upload or isinstance(upload, str):
        raise KettuError(ErrorCode.BAD_REQUEST, "Attach a voice note.")
    device = _device(form.get("device_id"))
    my_lang = _lang(form.get("my_lang"), "my_lang")
    mode = "orders" if form.get("mode") == "orders" else "listen"
    hints = _parse_list(form.get("hint_langs"), 4)
    keyterms = _parse_list(form.get("keyterms"), 50)

    ctx.limits.check_note(device)
    path = await save_upload(upload, ctx.settings.max_upload_mb)
    try:
        await audio.check_upload(path, ctx.settings.max_note_seconds, ctx.settings.max_upload_mb)
    except KettuError:
        discard(path)
        raise

    job = ctx.jobs.submit(lambda job: run_note(ctx, job, path, device, my_lang, mode, hints, keyterms))
    return {"job_id": job.id, "position": ctx.jobs.position(job)}


async def run_note(ctx: Context, job, path: Path, device: str, my_lang: str, mode: str,
                   hints: list[str], keyterms: list[str]):
    t0 = time.perf_counter()
    try:
        result, usage = await ctx.pipeline.understand_note(
            path, my_lang, mode, hints, keyterms, progress=job.set_stage
        )
    except KettuError as exc:
        ctx.store.log_usage(device_id=device, kind="note", my_lang=my_lang, status=exc.code.value,
                            latency_ms=int((time.perf_counter() - t0) * 1000))
        raise
    finally:
        discard(path)
    ctx.limits.record(device, "note", stt_seconds=usage.stt_seconds)
    ctx.store.log_usage(
        device_id=device, kind="note", audio_seconds=round(usage.stt_seconds, 2), llm_tokens=usage.llm_tokens,
        detected_lang=result.detected_lang, my_lang=my_lang, latency_ms=int((time.perf_counter() - t0) * 1000),
        status="ok",
    )
    return result


@router.get("/v1/jobs/{job_id}")
async def get_job(job_id: str, ctx: Context = Depends(get_ctx)):
    job = ctx.jobs.get(job_id)
    body = {"status": job.status, "position": ctx.jobs.position(job), "stage": job.stage}
    if job.status == "done":
        body["result"] = job.result.model_dump()
    elif job.status == "error" and job.error:
        body["error"] = job.error.to_dict()
    return body


# ---------------------------------------------------------------- replies


class PreviewIn(BaseModel):
    text: str = Field(max_length=2000)
    from_lang: str
    to_lang: str
    device_id: str


@router.post("/v1/replies/preview")
async def preview_reply(request: Request, ctx: Context = Depends(get_ctx)):
    ctype = request.headers.get("content-type", "")
    audio_path: Path | None = None
    if ctype.startswith("multipart/"):
        form = await request.form()
        fields = {k: form.get(k) for k in ("from_lang", "to_lang", "device_id", "text")}
        upload = form.get("audio")
        if upload is not None and not isinstance(upload, str):
            audio_path = await save_upload(upload, ctx.settings.max_upload_mb)
    else:
        try:
            fields = PreviewIn.model_validate(await request.json()).model_dump()
        except Exception:
            raise KettuError(ErrorCode.BAD_REQUEST)
    device = _device(fields.get("device_id"))
    from_lang = _lang(fields.get("from_lang"), "from_lang")
    to_lang = _lang(fields.get("to_lang"), "to_lang")
    try:
        ctx.limits.check_preview(device)
        if audio_path:
            await audio.check_upload(audio_path, 61, ctx.settings.max_upload_mb)
        t0 = time.perf_counter()
        draft, source_text, usage = await ctx.pipeline.preview_reply(
            from_lang, to_lang, text=fields.get("text"), audio_path=audio_path
        )
    finally:
        if audio_path:
            discard(audio_path)
    ctx.limits.record(device, "reply_preview")
    ctx.limits.add_stt(usage.stt_seconds)
    ctx.store.log_usage(device_id=device, kind="reply_preview", audio_seconds=round(usage.stt_seconds, 2),
                        llm_tokens=usage.llm_tokens, my_lang=from_lang, detected_lang=to_lang,
                        latency_ms=int((time.perf_counter() - t0) * 1000), status="ok")
    return {**draft.model_dump(), "source_text": source_text}


class SpeakIn(BaseModel):
    target_text: str = Field(max_length=2000)
    to_lang: str
    voice: Literal["female", "male"] = "female"
    device_id: str
    format: Literal["mp3", "ogg"] = "mp3"
    # "reply": a voice note to send back. "read_aloud": hear the translation in your own language (FR14).
    purpose: Literal["reply", "read_aloud"] = "reply"


@router.post("/v1/replies/speak")
async def speak_reply(body: SpeakIn, ctx: Context = Depends(get_ctx)):
    device = _device(body.device_id)
    to_lang = _lang(body.to_lang, "to_lang")
    kind = "read_aloud" if body.purpose == "read_aloud" else "reply_speak"
    ctx.limits.check_speak(device, len(body.target_text), kind)
    t0 = time.perf_counter()
    data, usage = await ctx.pipeline.speak_reply(body.target_text, to_lang, body.voice, body.format)
    ctx.limits.record(device, kind, tts_chars=usage.tts_chars)
    ctx.store.log_usage(device_id=device, kind=kind, tts_chars=usage.tts_chars, detected_lang=to_lang,
                        latency_ms=int((time.perf_counter() - t0) * 1000), status="ok")
    media = "audio/ogg" if body.format == "ogg" else "audio/mpeg"
    ext = "ogg" if body.format == "ogg" else "mp3"
    return Response(
        content=data, media_type=media,
        headers={"Content-Disposition": f'inline; filename="kettu-reply-{to_lang}.{ext}"', "Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------- feedback, limits, health


class FeedbackIn(BaseModel):
    job_id: str | None = None
    kind: Literal["note", "reply"]
    rating: Literal[1, -1]
    reason: Literal["wrong_language", "wrong_words", "bad_translation", "bad_voice", "other"] | None = None
    lang: str | None = None
    device_id: str


@router.post("/v1/feedback", status_code=204)
async def feedback(body: FeedbackIn, ctx: Context = Depends(get_ctx)):
    await ctx.store.add_feedback({
        "device_id": _device(body.device_id), "kind": body.kind, "rating": body.rating,
        "reason": body.reason, "lang": body.lang if languages.is_supported(body.lang) else None,
    })
    return Response(status_code=204)


@router.get("/v1/limits")
async def limits(device_id: str = Query(...), ctx: Context = Depends(get_ctx)):
    return ctx.limits.remaining(_device(device_id))


@router.get("/v1/languages")
async def list_languages():
    return [{"code": l.code, "name": l.name, "native": l.native} for l in languages.LANGUAGES.values()]


@router.get("/healthz")
async def healthz(deep: bool = False, ctx: Context = Depends(get_ctx)):
    if not deep:
        return {"ok": True}
    speech, llm, db = await asyncio.gather(ctx.speech.ping(), ctx.llm.ping(), ctx.store.ping())
    ok = speech and llm and db
    return JSONResponse({"ok": ok, "gnani": speech, "llm": llm, "supabase": db}, status_code=200 if ok else 503)

"""The three use cases: understand a note, draft a reply, speak a reply.

Channels (REST for the PWA, the WhatsApp bot) call these; they never talk to models directly.
"""

import logging
import shutil
import tempfile
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from pathlib import Path

from kettu.config import Settings
from kettu.domain import languages
from kettu.domain.errors import ErrorCode, KettuError
from kettu.domain.models import NoteResult, ReplyDraft, Transcript, Usage
from kettu.services import audio
from kettu.services.gnani import Gender, SpeechService
from kettu.services.llm import LLM

log = logging.getLogger(__name__)

Progress = Callable[[str], Awaitable[None] | None]

MAX_SPOKEN_REPLY_S = 60.0
MAX_TARGET_CHARS = 900


@contextmanager
def workdir(settings: Settings):
    """Temp folder for one job; deleted (audio included) when the job ends, success or not."""
    base = settings.work_dir or None
    path = Path(tempfile.mkdtemp(prefix="kettu_", dir=base))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


async def _notify(progress: Progress | None, stage: str) -> None:
    if progress:
        maybe = progress(stage)
        if maybe is not None:
            await maybe


class Pipeline:
    def __init__(self, settings: Settings, speech: SpeechService, llm: LLM):
        self.s = settings
        self.speech = speech
        self.llm = llm

    async def transcribe(
        self, src: Path, work: Path, language_code: str, keyterms: list[str] | None,
        progress: Progress | None = None, max_seconds: float | None = None,
    ) -> Transcript:
        clean = work / "clean.wav"
        duration = await audio.clean(src, clean)
        if max_seconds and duration > max_seconds + 1:
            raise KettuError(ErrorCode.TOO_LONG)
        chunks = await audio.split(clean, work, self.s.chunk_seconds)
        texts: list[str] = []
        lang_seconds: dict[str, float] = defaultdict(float)
        for i, (chunk, secs) in enumerate(chunks, start=1):
            await _notify(progress, f"transcribing {i}/{len(chunks)}")
            text, detected = await self.speech.transcribe(
                chunk, language_code, previous_text=" ".join(texts)[-600:], keyterms=keyterms
            )
            if text.strip():
                texts.append(text.strip())
                code = languages.normalise(detected)
                if code:
                    lang_seconds[code] += secs
        transcript = " ".join(texts).strip()
        if not transcript:
            raise KettuError(ErrorCode.NO_SPEECH)
        detected_lang = max(lang_seconds, key=lang_seconds.get) if lang_seconds else languages.normalise(language_code)
        return Transcript(text=transcript, detected_lang=detected_lang, duration_s=duration, seconds_billed=duration)

    async def understand_note(
        self, src: Path, my_lang: str, mode: str = "listen", hint_langs: list[str] | None = None,
        keyterms: list[str] | None = None, progress: Progress | None = None,
    ) -> tuple[NoteResult, Usage]:
        timings: dict[str, int] = {}
        t0 = time.perf_counter()
        hints = [h for h in (hint_langs or []) if languages.is_supported(h)][:4]
        language_code = ",".join(hints) if hints else "indic-auto"

        with workdir(self.s) as work:
            await _notify(progress, "preparing")
            tr = await self.transcribe(src, work, language_code, keyterms, progress)
        timings["stt"] = int((time.perf_counter() - t0) * 1000)

        same = languages.same_language(tr.detected_lang, my_lang)
        want_gist = tr.duration_s > self.s.gist_min_seconds
        want_translation = not same
        usage = Usage(stt_seconds=tr.seconds_billed)

        result = NoteResult(
            detected_lang=tr.detected_lang, my_lang=my_lang, duration_s=round(tr.duration_s, 1),
            transcript=tr.text, translation=None, gist=None, same_language=same,
        )
        if want_translation or want_gist or mode == "orders":
            await _notify(progress, "understanding")
            t1 = time.perf_counter()
            try:
                u, tokens = await self.llm.understand(
                    tr.text, tr.detected_lang, my_lang, tr.duration_s, want_gist, want_translation, mode
                )
            except KettuError as exc:
                if not exc.retryable:
                    raise
                log.info("llm retry after %s", exc.code.value)
                u, tokens = await self.llm.understand(
                    tr.text, tr.detected_lang, my_lang, tr.duration_s, want_gist, want_translation, mode
                )
            timings["llm"] = int((time.perf_counter() - t1) * 1000)
            usage.llm_tokens = tokens
            result.translation, result.gist = u.translation, u.gist
            result.entities = [e for e in u.entities if e.source_text and e.source_text in tr.text] or u.entities
            result.order_items = u.order_items
        timings["total"] = int((time.perf_counter() - t0) * 1000)
        result.timings_ms = timings
        return result, usage

    async def preview_reply(
        self, from_lang: str, to_lang: str, text: str | None = None, audio_path: Path | None = None,
    ) -> tuple[ReplyDraft, str, Usage]:
        """Returns the draft, the reply text in the user's own language, and usage."""
        usage = Usage()
        if audio_path is not None:
            with workdir(self.s) as work:
                tr = await self.transcribe(audio_path, work, from_lang, None, max_seconds=MAX_SPOKEN_REPLY_S)
            text = tr.text
            usage.stt_seconds = tr.seconds_billed
        text = (text or "").strip()
        if not text:
            raise KettuError(ErrorCode.BAD_REQUEST, "Type or say a reply first.")
        if len(text) > self.s.max_reply_chars:
            raise KettuError(ErrorCode.BAD_REQUEST, f"Keep replies under {self.s.max_reply_chars} characters.")
        if languages.same_language(from_lang, to_lang):
            return ReplyDraft(target_text=text, back_translation=text), text, usage
        try:
            draft, tokens = await self.llm.reply(text, from_lang, to_lang)
        except KettuError as exc:
            if not exc.retryable:
                raise
            draft, tokens = await self.llm.reply(text, from_lang, to_lang)
        usage.llm_tokens = tokens
        return draft, text, usage

    async def speak_reply(self, target_text: str, to_lang: str, gender: Gender, fmt: str) -> tuple[bytes, Usage]:
        text = target_text.strip()
        if not text:
            raise KettuError(ErrorCode.BAD_REQUEST, "Nothing to speak.")
        if len(text) > MAX_TARGET_CHARS:
            raise KettuError(ErrorCode.BAD_REQUEST, "This reply is too long to speak. Make it shorter.")
        wav = await self.speech.synthesize(text, to_lang, gender)
        with workdir(self.s) as work:
            out = await audio.encode_reply(wav, fmt, work)
        return out, Usage(tts_chars=len(text))

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
from kettu.domain.models import ActionDetail, ActionItem, Entity, NoteResult, NoteReview, ReplyDraft, TextTranslation, Transcript, Understanding, Usage
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


_INDIC_DIGITS = str.maketrans({
    chr(base + i): str(i)
    for base in (0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6, 0x0C66, 0x0CE6, 0x0D66)
    for i in range(10)
})


def _norm(text: str) -> str:
    """Compare loosely: case, spacing and Indian-script digits (৫০ = 50) don't count as differences."""
    return " ".join(text.translate(_INDIC_DIGITS).casefold().split())


def grounded(entities: list[Entity], transcript: str) -> list[Entity]:
    """Keep only facts whose source words really are in the transcript (the app highlights them there)."""
    real = [e for e in entities if e.source_text and e.source_text in transcript]
    return real


def grounded_actions(items: list[ActionItem], transcript: str) -> list[ActionItem]:
    """Reject unsupported tasks and blank any detail without a quote in this version of the transcript."""
    result = []
    for item in items[:8]:
        details = {}
        for key in ("task", "quantity", "person", "deadline"):
            detail = getattr(item, key)
            quote = detail.source_text.strip()
            details[key] = detail.model_copy() if detail.value.strip() and quote and quote in transcript else ActionDetail()
        if details["task"].value:
            result.append(ActionItem(**details))
    return result


def missing_facts(translation: str | None, entities: list[Entity]) -> list[Entity]:
    """Facts the model says it translated but that are not actually in the translation text."""
    if not translation:
        return []
    have = _norm(translation)
    return [e for e in entities if not e.in_translation.strip() or _norm(e.in_translation) not in have]


def _unique(values) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


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
        duration = await audio.clean(src, clean, max_seconds=max_seconds or self.s.max_note_seconds)
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
            tr = await self.transcribe(src, work, language_code, keyterms, progress,
                                       max_seconds=self.s.max_note_seconds)
        timings["stt"] = int((time.perf_counter() - t0) * 1000)

        same = languages.same_language(tr.detected_lang, my_lang)
        want_gist = tr.duration_s > self.s.gist_min_seconds
        want_translation = not same
        usage = Usage(stt_seconds=tr.seconds_billed)

        result = NoteResult(
            detected_lang=tr.detected_lang, my_lang=my_lang, duration_s=round(tr.duration_s, 1),
            transcript=tr.text, translation=None, gist=None, same_language=same,
            translation_live=self.llm.live,
            speech_live=getattr(self.speech, "live", True),
        )
        if want_translation or want_gist or mode == "orders":
            await _notify(progress, "understanding")
            t1 = time.perf_counter()
            u, missing, tokens = await self.understand_text(
                tr.text, tr.detected_lang, my_lang, tr.duration_s, want_gist, want_translation, mode
            )
            timings["llm"] = int((time.perf_counter() - t1) * 1000)
            usage.llm_tokens = tokens
            result.translation, result.gist = u.translation, u.gist
            result.entities = u.entities
            result.missing_facts = missing
            result.order_items = u.order_items
            result.action_items = u.action_items
        timings["total"] = int((time.perf_counter() - t0) * 1000)
        result.timings_ms = timings
        return result, usage

    async def _understand_once(self, text, source_lang, my_lang, duration_s, want_gist, want_translation, mode,
                               must_include=None):
        try:
            return await self.llm.understand(text, source_lang, my_lang, duration_s, want_gist, want_translation,
                                             mode, must_include)
        except KettuError as exc:
            if not exc.retryable:
                raise
            log.info("llm retry after %s", exc.code.value)
            return await self.llm.understand(text, source_lang, my_lang, duration_s, want_gist, want_translation,
                                             mode, must_include)

    async def understand_text(
        self, text: str, source_lang: str | None, my_lang: str, duration_s: float,
        want_gist: bool, want_translation: bool, mode: str = "listen",
    ) -> tuple[Understanding, list[str], int]:
        """Translate (and summarise) a transcript, then check every fact heard made it into the translation.

        If the model dropped an amount, time, count or name, it is asked once more with those facts listed;
        whatever is still missing is returned so the app can point the reader at the original words.
        """
        u, tokens = await self._understand_once(text, source_lang, my_lang, duration_s, want_gist,
                                                want_translation, mode)
        u.entities = grounded(u.entities, text)
        missing = missing_facts(u.translation, u.entities) if want_translation and self.llm.live else []
        if missing:
            log.info("translation dropped %d facts; asking again", len(missing))
            must = [f"{e.value} ({e.source_text})" for e in missing]
            try:
                again, more = await self._understand_once(text, source_lang, my_lang, duration_s, want_gist,
                                                          want_translation, mode, must)
                tokens += more
                again.entities = grounded(again.entities, text)
                # A repair must not make a missing fact disappear by omitting its entity.
                known = {e.source_text: e for e in u.entities}
                known.update({e.source_text: e for e in again.entities})
                again.entities = list(known.values())
                still = missing_facts(again.translation, again.entities)
                if again.translation and len(still) < len(missing):
                    u, missing = again, still
            except KettuError as exc:
                log.warning("repair pass failed (%s); keeping first translation", exc.code.value)
        u.action_items = grounded_actions(u.action_items, text)
        return u, _unique(e.value for e in missing), tokens

    async def review_note(
        self, text: str, source_lang: str | None, my_lang: str, duration_s: float, mode: str = "listen",
    ) -> tuple[NoteReview, int]:
        text = text.strip()
        if not text:
            raise KettuError(ErrorCode.BAD_REQUEST, "Enter the words you heard before updating the note.")
        if not self.llm.live:
            raise KettuError(ErrorCode.BAD_REQUEST, "Translation is unavailable on this server. Your original result has been kept.")
        same = languages.same_language(source_lang, my_lang)
        understanding, missing, tokens = await self.understand_text(
            text, source_lang, my_lang, duration_s, duration_s > self.s.gist_min_seconds, not same,
            "orders" if mode == "orders" else "actions",
        )
        return NoteReview(
            transcript=text, detected_lang=source_lang, my_lang=my_lang,
            translation=understanding.translation, gist=understanding.gist,
            entities=understanding.entities, missing_facts=missing, order_items=understanding.order_items,
            action_items=understanding.action_items, same_language=same, translation_live=True,
        ), tokens

    async def translate_text(self, text: str, source_lang: str | None, to_lang: str) -> tuple[TextTranslation, int]:
        """A transcript the person already has, put into one more language of their choice."""
        text = text.strip()
        if not text:
            raise KettuError(ErrorCode.BAD_REQUEST, "Nothing to translate.")
        if source_lang and languages.same_language(source_lang, to_lang):
            return TextTranslation(to_lang=to_lang, translation=text, translation_live=self.llm.live), 0
        u, missing, tokens = await self.understand_text(text, source_lang, to_lang, 0.0, False, True)
        return TextTranslation(
            to_lang=to_lang, translation=u.translation or "", entities=u.entities, missing_facts=missing,
            translation_live=self.llm.live,
        ), tokens

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

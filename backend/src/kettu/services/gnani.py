"""Gnani Prisma (speech to text) and Timbre (text to speech) over REST.

Every call passes one shared semaphore: some Gnani accounts allow one active request at a time.
429 and 5xx are retried with backoff; a timeout is retried once.
"""

import asyncio
import io
import logging
import wave
from pathlib import Path
from typing import Literal, Protocol

import httpx

from kettu.config import Settings
from kettu.domain import languages
from kettu.domain.errors import ErrorCode, KettuError
from kettu.services.audio import tone_wav

log = logging.getLogger(__name__)

Gender = Literal["female", "male"]

MOCK_TRANSCRIPTS = {
    "bn-IN": "দাদা, কাল সকাল আটটায় সিমেন্টের পঞ্চাশ বস্তা আসবে। রাকিবকে পাঁচশো টাকা অ্যাডভান্স দিতে হবে।",
    "hi-IN": "भैया, कल सुबह आठ बजे सीमेंट की पचास बोरी आएगी। राकिब को पाँच सौ रुपये एडवांस देने हैं।",
    "ml-IN": "ശരി, നാളെ രാവിലെ എട്ടു മണിക്ക് സൈറ്റിൽ വരണം. ശമ്പളം ശനിയാഴ്ച തരാം.",
    "en-IN": "Okay, come to the site tomorrow at eight in the morning. Wages will be paid on Saturday.",
}


class SpeechService(Protocol):
    async def transcribe(
        self, wav: Path, language_code: str, previous_text: str = "", keyterms: list[str] | None = None
    ) -> tuple[str, str | None]: ...

    async def synthesize(self, text: str, lang: str, gender: Gender) -> bytes: ...

    async def ping(self) -> bool: ...


class GnaniSpeech:
    live = True
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.s = settings
        self._client = client or httpx.AsyncClient(
            base_url=settings.gnani_base_url,
            headers={"X-API-Key-ID": settings.gnani_api_key},
            timeout=httpx.Timeout(45.0, connect=10.0),
        )
        self._gate: asyncio.Semaphore | None = None
        self._timbre_model = settings.timbre_model

    @property
    def gate(self) -> asyncio.Semaphore:
        if self._gate is None:
            self._gate = asyncio.Semaphore(max(1, self.s.gnani_concurrency))
        return self._gate

    async def _post(self, url: str, **kwargs) -> httpx.Response:
        delays = [1.0, 2.5, 5.0]
        timed_out = False
        for attempt in range(len(delays) + 1):
            try:
                async with self.gate:
                    resp = await self._client.post(url, **kwargs)
            except httpx.TimeoutException:
                if timed_out:
                    raise KettuError(ErrorCode.MODEL_TIMEOUT, retryable=True)
                timed_out = True
                continue
            except httpx.HTTPError as exc:
                log.warning("gnani network error: %s", type(exc).__name__)
                if attempt < len(delays):
                    await asyncio.sleep(delays[attempt])
                    continue
                raise KettuError(ErrorCode.MODEL_TIMEOUT, retryable=True) from exc
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < len(delays):
                    log.info("gnani %s on %s, retry %d", resp.status_code, url, attempt + 1)
                    await asyncio.sleep(delays[attempt])
                    continue
                raise KettuError(ErrorCode.BUSY if resp.status_code == 429 else ErrorCode.MODEL_TIMEOUT, retryable=True)
            if resp.status_code == 402:
                raise KettuError(ErrorCode.SERVICE_BUDGET)
            return resp
        raise KettuError(ErrorCode.MODEL_TIMEOUT, retryable=True)

    async def transcribe(
        self, wav: Path, language_code: str, previous_text: str = "", keyterms: list[str] | None = None
    ) -> tuple[str, str | None]:
        data = {"model": self.s.prisma_model, "language_code": language_code, "format": "codemix"}
        if previous_text:
            data["previous_text"] = previous_text[-600:]
        if keyterms:
            data["keyterms"] = ",".join(t.replace(",", " ") for t in keyterms[:200])
        resp = await self._post(
            "/stt/v3",
            data=data,
            files={"audio_file": (wav.name, wav.read_bytes(), "audio/wav")},
        )
        body = _json(resp)
        if resp.status_code != 200 or not body.get("success", False):
            err = (body.get("error") or {}).get("type") if isinstance(body.get("error"), dict) else None
            log.warning("prisma error status=%s type=%s", resp.status_code, err)
            if err in {"EMPTY_AUDIO"}:
                return "", None
            if err in {"UNSUPPORTED_AUDIO_FORMAT", "AUDIO_CONVERSION_ERROR"}:
                raise KettuError(ErrorCode.UNSUPPORTED_FILE)
            if err == "INVALID_FORMAT" and data["format"] == "codemix":
                # Older keys may not accept codemix; fall back to the default output once.
                data["format"] = "transcribe"
                resp = await self._post("/stt/v3", data=data, files={"audio_file": (wav.name, wav.read_bytes(), "audio/wav")})
                body = _json(resp)
                if resp.status_code == 200 and body.get("success", True):
                    return body.get("transcript", "") or "", body.get("detected_language_code")
            raise KettuError(ErrorCode.MODEL_TIMEOUT if resp.status_code in (504,) else ErrorCode.INTERNAL)
        return body.get("transcript", "") or "", body.get("detected_language_code")

    def _voice(self, model: str, lang: str, gender: Gender) -> str:
        if model.startswith("timbre-v3"):
            return self.s.timbre_voice_male if gender == "male" else self.s.timbre_voice_female
        language = languages.get(lang)
        return language.v25_male if gender == "male" else language.v25_female

    async def synthesize(self, text: str, lang: str, gender: Gender) -> bytes:
        """Primary model, a retry if the audio ran on past the text, then the fallback model."""
        primary, fallback = self._timbre_model, self.s.timbre_fallback_model
        attempts = [primary, primary] + ([fallback] if fallback != primary else [])
        for i, model in enumerate(attempts):
            if i == 1 and model == primary and self._timbre_model != primary:
                continue  # primary was rejected outright; no point retrying it
            payload = {
                "text": text,
                "model": model,
                "voice": self._voice(model, lang, gender),
                "language": lang,
                "speed": 1.0,
                "audio_config": {
                    "sample_rate": 24000,
                    "num_channels": 1,
                    "sample_width": 2,
                    "encoding": "linear_pcm",
                    "container": "wav",
                },
            }
            resp = await self._post("/api/v1/tts/inference", json=payload)
            if resp.status_code == 200 and resp.content[:4] == b"RIFF":
                secs = wav_seconds(resp.content)
                if secs > plausible_seconds(text):
                    # Generative TTS occasionally keeps talking after the text ends; never ship that.
                    log.warning("timbre %s ran on: %.1fs for %d chars, retrying", model, secs, len(text))
                    continue
                return resp.content
            log.warning("timbre %s failed status=%s", model, resp.status_code)
            if resp.status_code in (400, 403, 404, 422) and model == primary and fallback != primary:
                log.warning("timbre: %s rejected, using %s from now on", primary, fallback)
                self._timbre_model = fallback
                continue
            if resp.status_code not in (400, 403, 404, 422):
                break
        raise KettuError(ErrorCode.INTERNAL, "Could not make the voice note right now. Please try again.")

    async def ping(self) -> bool:
        try:
            resp = await self._client.get("/", timeout=5.0)
            return resp.status_code < 500
        except httpx.HTTPError:
            return False


class MockSpeech:
    """No network. Lets the whole product run without keys."""

    live = False

    async def transcribe(
        self, wav: Path, language_code: str, previous_text: str = "", keyterms: list[str] | None = None
    ) -> tuple[str, str | None]:
        await asyncio.sleep(0.3)
        lang = language_code if language_code in MOCK_TRANSCRIPTS else "bn-IN"
        return MOCK_TRANSCRIPTS[lang], lang

    async def synthesize(self, text: str, lang: str, gender: Gender) -> bytes:
        await asyncio.sleep(0.2)
        return tone_wav(seconds=min(6.0, 0.6 + len(text) / 40), freq=330 if gender == "male" else 523)

    async def ping(self) -> bool:
        return True


TTS_CHARS_PER_SECOND = 13.0  # measured on Timbre v2.5 and v3.0 across Bengali, Malayalam and Hindi


def wav_seconds(wav: bytes) -> float:
    """Length from the byte count: Timbre's WAV header carries a 0xFFFFFFFF size placeholder."""
    try:
        with wave.open(io.BytesIO(wav)) as w:
            per_second = w.getsampwidth() * w.getnchannels() * w.getframerate()
    except (wave.Error, EOFError):
        return 0.0
    return max(0, len(wav) - 44) / max(1, per_second)


def plausible_seconds(text: str) -> float:
    """Generous upper bound for how long speaking `text` can take (2.5x the measured pace, plus slack)."""
    return max(6.0, len(text) / TTS_CHARS_PER_SECOND * 2.5 + 2.0)


def _json(resp: httpx.Response) -> dict:
    try:
        body = resp.json()
        return body if isinstance(body, dict) else {}
    except ValueError:
        return {}


def build_speech(settings: Settings) -> SpeechService:
    if settings.speech_provider == "mock" or not settings.gnani_api_key:
        if settings.speech_provider != "mock":
            log.warning("GNANI_API_KEY not set: using mock speech")
        return MockSpeech()
    return GnaniSpeech(settings)

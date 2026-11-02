"""LLM providers behind one interface. Pick with LLM_PROVIDER=anthropic|gemini|mock."""

import asyncio
import json
import logging
from typing import Protocol

import anthropic
import httpx

from kettu.config import Settings
from kettu.domain import languages
from kettu.domain.errors import ErrorCode, KettuError
from kettu.domain.models import ActionItem, Entity, OrderItem, ReplyDraft, Understanding
from kettu.services import prompts

log = logging.getLogger(__name__)


class LLM(Protocol):
    async def understand(
        self, transcript: str, source_lang: str | None, my_lang: str, duration_s: float,
        want_gist: bool, want_translation: bool, mode: str, must_include: list[str] | None = None,
    ) -> tuple[Understanding, int]: ...

    async def reply(self, text: str, from_lang: str, to_lang: str) -> tuple[ReplyDraft, int]: ...

    async def ping(self) -> bool: ...


def _to_understanding(data: dict, want_gist: bool, want_translation: bool, mode: str) -> Understanding:
    if not isinstance(data, dict):
        raise KettuError(ErrorCode.INTERNAL, "The translation came back garbled. Please try again.")
    for key in ("translation", "gist"):
        if data.get(key) is not None and not isinstance(data[key], str):
            raise KettuError(ErrorCode.INTERNAL, "The translation came back garbled. Please try again.")
    if want_translation and not (data.get("translation") or "").strip():
        raise KettuError(ErrorCode.INTERNAL, "No translation was returned. Please try again.")
    for key in ("entities", "order_items", "action_items"):
        if data.get(key) is not None and not isinstance(data[key], list):
            raise KettuError(ErrorCode.INTERNAL, "The translation came back garbled. Please try again.")
    entities = []
    for e in data.get("entities") or []:
        try:
            entities.append(Entity(**e))
        except (TypeError, ValueError):
            continue
    items = []
    for item in data.get("order_items") or []:
        try:
            items.append(OrderItem(**item))
        except (TypeError, ValueError):
            continue
    actions = []
    if mode in ("actions", "orders"):
        for item in (data.get("action_items") or [])[:8]:
            try:
                actions.append(ActionItem.model_validate(item))
            except (TypeError, ValueError):
                continue
    return Understanding(
        translation=(data.get("translation") or "").strip() or None if want_translation else None,
        gist=(data.get("gist") or "").strip() or None if want_gist else None,
        entities=entities,
        order_items=items if mode == "orders" else None,
        action_items=actions,
    )


def _reply_draft(data) -> ReplyDraft:
    try:
        return ReplyDraft(**data)
    except (TypeError, ValueError) as exc:
        raise KettuError(ErrorCode.INTERNAL, "The reply came back garbled. Please try again.") from exc


class AnthropicLLM:
    live = True

    def __init__(self, settings: Settings):
        self.s = settings
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key or None, timeout=settings.llm_timeout_s, max_retries=2
        )

    async def _json_call(self, system: str, user: str, schema: dict, max_tokens: int) -> tuple[dict, int]:
        try:
            resp = await self.client.messages.create(
                model=self.s.anthropic_model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.APITimeoutError as exc:
            raise KettuError(ErrorCode.MODEL_TIMEOUT, retryable=True) from exc
        except anthropic.RateLimitError as exc:
            raise KettuError(ErrorCode.BUSY, retryable=True) from exc
        except anthropic.APIStatusError as exc:
            log.error("anthropic status=%s type=%s", exc.status_code, type(exc).__name__)
            raise KettuError(ErrorCode.INTERNAL, "The translation service failed. Please try again.") from exc
        except anthropic.APIConnectionError as exc:
            raise KettuError(ErrorCode.MODEL_TIMEOUT, retryable=True) from exc

        tokens = resp.usage.input_tokens + resp.usage.output_tokens
        if resp.stop_reason == "refusal":
            raise KettuError(ErrorCode.INTERNAL, "Kettu could not translate this note.")
        if resp.stop_reason == "max_tokens":
            log.warning("anthropic hit max_tokens")
        text = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return json.loads(text), tokens
        except json.JSONDecodeError as exc:
            raise KettuError(ErrorCode.INTERNAL, "The translation came back garbled. Please try again.") from exc

    async def understand(self, transcript, source_lang, my_lang, duration_s, want_gist, want_translation, mode,
                         must_include=None):
        system = prompts.UNDERSTAND_SYSTEM.format(my_lang_name=languages.name(my_lang))
        user = prompts.understand_user_message(source_lang, duration_s, want_gist, want_translation, mode, transcript,
                                               must_include)
        data, tokens = await self._json_call(system, user, prompts.UNDERSTAND_SCHEMA, max_tokens=8000)
        return _to_understanding(data, want_gist, want_translation, mode), tokens

    async def reply(self, text, from_lang, to_lang):
        system = prompts.REPLY_SYSTEM.format(from_lang_name=languages.name(from_lang), to_lang_name=languages.name(to_lang))
        data, tokens = await self._json_call(system, text, prompts.REPLY_SCHEMA, max_tokens=2000)
        return _reply_draft(data), tokens

    async def ping(self) -> bool:
        try:
            await self.client.models.retrieve(self.s.anthropic_model)
            return True
        except anthropic.AnthropicError:
            return False


class GeminiLLM:
    live = True
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, settings: Settings):
        self.s = settings
        self.http = httpx.AsyncClient(timeout=settings.llm_timeout_s)

    async def _json_call(self, system: str, user: str, schema: dict, max_tokens: int) -> tuple[dict, int]:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }
        for attempt in range(3):
            try:
                resp = await self.http.post(
                    self.URL.format(model=self.s.gemini_model),
                    headers={"x-goog-api-key": self.s.gemini_api_key},
                    json=body,
                )
            except httpx.TimeoutException as exc:
                if attempt == 2:
                    raise KettuError(ErrorCode.MODEL_TIMEOUT, retryable=True) from exc
                continue
            except httpx.HTTPError as exc:
                raise KettuError(ErrorCode.MODEL_TIMEOUT, retryable=True) from exc
            if resp.status_code in (429, 500, 503) and attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            break
        if resp.status_code != 200:
            log.error("gemini status=%s", resp.status_code)
            raise KettuError(ErrorCode.INTERNAL, "The translation service failed. Please try again.")
        try:
            payload = resp.json()
            usage = payload.get("usageMetadata", {})
            tokens = int(usage.get("promptTokenCount", 0)) + int(usage.get("candidatesTokenCount", 0))
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text), tokens
        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as exc:
            raise KettuError(ErrorCode.INTERNAL, "The translation came back garbled. Please try again.") from exc

    async def understand(self, transcript, source_lang, my_lang, duration_s, want_gist, want_translation, mode,
                         must_include=None):
        system = prompts.UNDERSTAND_SYSTEM.format(my_lang_name=languages.name(my_lang))
        user = prompts.understand_user_message(source_lang, duration_s, want_gist, want_translation, mode, transcript,
                                               must_include)
        data, tokens = await self._json_call(system, user, prompts.UNDERSTAND_SCHEMA, max_tokens=8000)
        return _to_understanding(data, want_gist, want_translation, mode), tokens

    async def reply(self, text, from_lang, to_lang):
        system = prompts.REPLY_SYSTEM.format(from_lang_name=languages.name(from_lang), to_lang_name=languages.name(to_lang))
        data, tokens = await self._json_call(system, text, prompts.REPLY_SCHEMA, max_tokens=2000)
        return _reply_draft(data), tokens

    async def ping(self) -> bool:
        try:
            resp = await self.http.get(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.s.gemini_model}",
                headers={"x-goog-api-key": self.s.gemini_api_key},
                timeout=5.0,
            )
            return resp.status_code == 200
        except httpx.HTTPError:
            return False


class MockLLM:
    """Stand-in so the app runs end to end without keys. It does not translate: it hands back the transcript,
    labelled, and live=False tells the app to say translation is off rather than show it as a translation."""

    live = False

    async def understand(self, transcript, source_lang, my_lang, duration_s, want_gist, want_translation, mode,
                         must_include=None):
        await asyncio.sleep(0.2)
        lang = languages.name(my_lang)
        u = Understanding(
            translation=f"[{lang}: translation off] {transcript}" if want_translation else None,
            gist=f"[{lang}: summary off] {transcript[:120]}" if want_gist else None,
            entities=[
                Entity(type="time", value="8 AM", source_text=_first(transcript, ["আটটায়", "आठ बजे", "എട്ടു മണിക്ക്", "eight"])),
                Entity(type="amount", value="₹500", source_text=_first(transcript, ["পাঁচশো টাকা", "पाँच सौ रुपये"])),
                Entity(type="name", value="Rakib", source_text=_first(transcript, ["রাকিবকে", "राकिब"])),
            ],
            order_items=[OrderItem(item="Cement", quantity="50", unit="bags")] if mode == "orders" else None,
        )
        u.entities = [e for e in u.entities if e.source_text]
        return u, 0

    async def reply(self, text, from_lang, to_lang):
        await asyncio.sleep(0.2)
        return ReplyDraft(
            target_text=f"[{languages.name(to_lang)}] {text}",
            back_translation=f"[{languages.name(from_lang)}] {text}",
        ), 0

    async def ping(self) -> bool:
        return True


def _first(text: str, options: list[str]) -> str:
    return next((o for o in options if o in text), "")


class FallbackLLM:
    """Tries each provider in order; moves on when one fails. Bad input is not retried elsewhere."""

    live = True

    def __init__(self, providers: list[tuple[str, LLM]]):
        self.providers = providers

    async def _first(self, method: str, *args):
        last: KettuError | None = None
        for name, provider in self.providers:
            try:
                return await getattr(provider, method)(*args)
            except KettuError as exc:
                if exc.code == ErrorCode.BAD_REQUEST:
                    raise
                log.warning("llm %s failed on %s (%s), trying next provider", name, method, exc.code.value)
                last = exc
        raise last or KettuError(ErrorCode.INTERNAL)

    async def understand(self, transcript, source_lang, my_lang, duration_s, want_gist, want_translation, mode,
                         must_include=None):
        return await self._first("understand", transcript, source_lang, my_lang, duration_s, want_gist,
                                 want_translation, mode, must_include)

    async def reply(self, text, from_lang, to_lang):
        return await self._first("reply", text, from_lang, to_lang)

    async def ping(self) -> bool:
        results = await asyncio.gather(*(p.ping() for _, p in self.providers))
        return any(results)


def _provider(name: str, settings: Settings) -> LLM | None:
    if name == "anthropic" and settings.anthropic_api_key:
        return AnthropicLLM(settings)
    if name == "gemini" and settings.gemini_api_key:
        return GeminiLLM(settings)
    return None


def build_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "mock":
        return MockLLM()
    names = list(dict.fromkeys([settings.llm_provider, settings.llm_fallback_provider]))
    chain = [(n, p) for n in names if n != "none" and (p := _provider(n, settings))]
    if not chain:
        log.warning("no key for %s: using mock LLM", " or ".join(n for n in names if n != "none"))
        return MockLLM()
    log.info("llm providers: %s", " → ".join(n for n, _ in chain))
    return chain[0][1] if len(chain) == 1 else FallbackLLM(chain)

import pytest

from kettu.config import Settings
from kettu.domain.errors import ErrorCode, KettuError
from kettu.domain.models import ReplyDraft
from kettu.services.llm import AnthropicLLM, FallbackLLM, GeminiLLM, MockLLM, build_llm


def cfg(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_no_keys_means_mock():
    assert isinstance(build_llm(cfg(anthropic_api_key="", gemini_api_key="")), MockLLM)


def test_only_gemini_key_uses_gemini_alone():
    assert isinstance(build_llm(cfg(anthropic_api_key="", gemini_api_key="g")), GeminiLLM)


def test_both_keys_chain_primary_then_gemini():
    llm = build_llm(cfg(anthropic_api_key="a", gemini_api_key="g"))
    assert isinstance(llm, FallbackLLM)
    assert [n for n, _ in llm.providers] == ["anthropic", "gemini"]
    assert isinstance(llm.providers[0][1], AnthropicLLM)


def test_fallback_none_keeps_single_provider():
    llm = build_llm(cfg(anthropic_api_key="a", gemini_api_key="g", llm_fallback_provider="none"))
    assert isinstance(llm, AnthropicLLM)


class Failing(MockLLM):
    def __init__(self, code):
        self.code = code
        self.calls = 0

    async def reply(self, text, from_lang, to_lang):
        self.calls += 1
        raise KettuError(self.code)


class Working(MockLLM):
    async def reply(self, text, from_lang, to_lang):
        return ReplyDraft(target_text="ok", back_translation="ok"), 1


async def test_outage_falls_through_to_next_provider():
    first = Failing(ErrorCode.MODEL_TIMEOUT)
    draft, _ = await FallbackLLM([("anthropic", first), ("gemini", Working())]).reply("hi", "ml-IN", "bn-IN")
    assert draft.target_text == "ok" and first.calls == 1


async def test_bad_input_is_not_retried_on_another_provider():
    second = Failing(ErrorCode.INTERNAL)
    with pytest.raises(KettuError) as e:
        await FallbackLLM([("anthropic", Failing(ErrorCode.BAD_REQUEST)), ("gemini", second)]).reply("x", "ml-IN", "bn-IN")
    assert e.value.code == ErrorCode.BAD_REQUEST and second.calls == 0


async def test_all_failing_raises_last_error():
    with pytest.raises(KettuError) as e:
        await FallbackLLM([("a", Failing(ErrorCode.BUSY)), ("g", Failing(ErrorCode.MODEL_TIMEOUT))]).reply("x", "ml-IN", "bn-IN")
    assert e.value.code == ErrorCode.MODEL_TIMEOUT

import uuid

import pytest
from fastapi.testclient import TestClient

from kettu.container import build_context
from kettu.domain.errors import ErrorCode, KettuError
from kettu.domain.models import ActionDetail, ActionItem, Entity, Understanding
from kettu.main import create_app
from kettu.services.llm import MockLLM, _to_understanding
from kettu.services.pipeline import Pipeline, grounded_actions


TEXT = "Please bring 60 bags of cement tomorrow. Ask Ravi to open the gate."


def detail(value, source=None):
    return ActionDetail(value=value, source_text=value if source is None else source)


def suggested_action():
    return ActionItem(task=detail("Bring cement", "bring 60 bags of cement"),
                      quantity=detail("60 bags"), deadline=detail("tomorrow"))


class NoSpeech:
    live = True

    async def transcribe(self, *args, **kwargs):
        pytest.fail("review must never transcribe the recording again")

    async def synthesize(self, *args, **kwargs):
        pytest.fail("review must not make an unapproved voice reply")


class ReviewLLM(MockLLM):
    live = True

    def __init__(self):
        self.calls = []

    async def understand(self, transcript, source_lang, my_lang, duration_s, want_gist, want_translation,
                         mode, must_include=None):
        self.calls.append(dict(text=transcript, source=source_lang, target=my_lang, mode=mode,
                               want_gist=want_gist, want_translation=want_translation))
        return Understanding(translation="Sixty bags arrive tomorrow." if want_translation else None,
                             action_items=[suggested_action()],
                             entities=[Entity(type="quantity", value="60 bags", source_text="60 bags",
                                              in_translation="Sixty bags")]), 25


@pytest.fixture
def review_client(settings):
    llm = ReviewLLM()
    context = build_context(settings, speech=NoSpeech(), llm=llm)
    logs = []
    context.store.log_usage = lambda **row: logs.append(row)
    with TestClient(create_app(settings, context)) as client:
        yield client, context, llm, logs


def body(**extra):
    return dict(text=TEXT, source_lang="bn-IN", my_lang="en-IN", duration_s=30,
                device_id=str(uuid.uuid4()), **extra)


def test_review_updates_translation_and_returns_grounded_actions_without_speech(review_client):
    client, context, llm, logs = review_client
    response = client.post("/v1/notes/review", json=body())
    assert response.status_code == 200, response.text
    output = response.json()
    assert output["transcript"] == TEXT
    assert output["translation"] == "Sixty bags arrive tomorrow."
    assert output["action_items"][0]["quantity"]["value"] == "60 bags"
    assert output["action_items"][0]["person"] == {"value": "", "source_text": ""}
    assert output["actions_reviewed"] is True
    assert "speech_live" not in output and "duration_s" not in output
    assert llm.calls[0]["mode"] == "actions"
    assert context.limits.c.stt_seconds == 0 and context.limits.c.tts_chars == 0
    assert context.limits.c.per_device[(logs[0]["device_id"], "translate")] == 1
    assert "text" not in logs[0] and TEXT not in str(logs)


def test_same_language_note_still_extracts_actions_but_does_not_request_translation(review_client):
    client, _, llm, _ = review_client
    request = body()
    request["source_lang"] = "en-IN"
    response = client.post("/v1/notes/review", json=request)
    assert response.status_code == 200
    assert response.json()["translation"] is None and response.json()["same_language"]
    assert llm.calls[0]["want_translation"] is False


def test_order_mode_is_preserved_during_review(review_client):
    client, _, llm, _ = review_client
    response = client.post("/v1/notes/review", json=body(mode="orders"))
    assert response.status_code == 200 and llm.calls[0]["mode"] == "orders"


@pytest.mark.parametrize("field,value", [("text", "   "), ("text", "x" * 6001), ("device_id", "invalid"),
                                          ("source_lang", "unknown-language"), ("my_lang", "xx"),
                                          ("mode", "arbitrary"), ("duration_s", 182)])
def test_invalid_reviews_are_rejected_before_model_calls(review_client, field, value):
    client, _, llm, logs = review_client
    request = body()
    request[field] = value
    assert client.post("/v1/notes/review", json=request).status_code == 400
    assert llm.calls == [] and logs == []


def test_review_obeys_translation_allowance(review_client):
    client, context, llm, _ = review_client
    request = body()
    context.limits.c.per_device[(request["device_id"], "translate")] = context.settings.translate_per_day
    response = client.post("/v1/notes/review", json=request)
    assert response.status_code == 429 and llm.calls == []


def test_failed_review_returns_plain_error_without_adding_usage(review_client):
    client, context, llm, logs = review_client

    async def fail(*args, **kwargs):
        raise KettuError(ErrorCode.MODEL_TIMEOUT)

    llm.understand = fail
    response = client.post("/v1/notes/review", json=body())
    assert response.status_code == 504 and response.json()["error"]["code"] == "model_timeout"
    assert not logs and context.limits.c.reserved_stt == 0
    assert not any(context.limits.c.pending.values())


async def test_mock_mode_does_not_present_canned_actions_as_real(settings):
    with pytest.raises(KettuError, match="unavailable"):
        await Pipeline(settings, NoSpeech(), MockLLM()).review_note(TEXT, "en-IN", "hi-IN", 20)


def test_task_without_a_real_source_quote_is_removed():
    item = ActionItem(task=detail("Pay someone", "invented words"), quantity=detail("60 bags"))
    assert grounded_actions([item], TEXT) == []


def test_details_without_a_quote_in_the_current_transcript_are_blank():
    item = suggested_action()
    item.quantity = detail("50 bags")
    item.person = detail("Ravi", "Ravi will bring the cement")
    item.deadline = detail("Thursday", "next Thursday")
    result = grounded_actions([item], TEXT)[0]
    assert result.task.value == "Bring cement"
    assert result.quantity.value == result.person.value == result.deadline.value == ""


def test_action_response_parser_skips_malformed_entries_and_caps_count():
    valid = suggested_action().model_dump()
    data = {"translation": "translated", "action_items": [None, {"task": 5}, valid]}
    result = _to_understanding(data, False, True, "actions")
    assert len(result.action_items) == 1
    data["action_items"] = [valid] * 12
    assert len(_to_understanding(data, False, True, "actions").action_items) == 8
    assert _to_understanding(data, False, True, "listen").action_items == []

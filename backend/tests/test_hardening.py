import asyncio
import time
import uuid
from contextlib import ExitStack

import httpx
import pytest
from fastapi.testclient import TestClient

from kettu.container import build_context
from kettu.domain.errors import ErrorCode, KettuError
from kettu.domain.models import Entity, Understanding
from kettu.main import create_app
from kettu.services import audio
from kettu.services.jobs import JobQueue
from kettu.services.limits import Limits
from kettu.services.limits import ist_midnight
from kettu.services.llm import GeminiLLM, MockLLM
from kettu.services.pipeline import Pipeline, grounded
from kettu.services.store import Store
from kettu.whatsapp.client import WhatsAppError
from kettu.whatsapp.media import download


def test_pending_notes_cannot_exceed_device_allowance(settings):
    limits = Limits(settings)
    with ExitStack() as stack:
        for _ in range(settings.notes_per_day):
            stack.enter_context(limits.reserve("device", "note", stt_seconds=10))
        assert limits.remaining("device")["notes_left"] == 0
        with pytest.raises(KettuError) as error:
            with limits.reserve("device", "note"):
                pytest.fail("accepted over quota")
        assert error.value.code == ErrorCode.DAILY_LIMIT
    assert limits.remaining("device")["notes_left"] == settings.notes_per_day


@pytest.mark.parametrize("kind,stt,tts", [("note", 7, 0), ("reply_preview", 7, 0), ("reply_speak", 0, 7)])
def test_pending_work_reserves_whole_service_budget(settings, kind, stt, tts):
    settings.daily_stt_seconds_cap = 10
    settings.daily_tts_chars_cap = 10
    limits = Limits(settings)
    with limits.reserve("one", kind, stt_seconds=stt, tts_chars=tts):
        with pytest.raises(KettuError) as error:
            with limits.reserve("two", kind, stt_seconds=stt, tts_chars=tts):
                pytest.fail("accepted over budget")
        assert error.value.code == ErrorCode.SERVICE_BUDGET


def test_rotating_device_ids_does_not_bypass_operation_cap(settings):
    settings.daily_operations_cap = 1
    limits = Limits(settings)
    with limits.reserve("one", "translate"):
        pass
    with pytest.raises(KettuError) as error:
        with limits.reserve("another", "translate"):
            pytest.fail("accepted over service cap")
    assert error.value.code == ErrorCode.SERVICE_BUDGET


def test_request_size_limit_and_private_response_headers(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/translate", content=b"x" * 65537)
        assert response.status_code == 413
        assert response.headers["cache-control"] == "no-store"
        device = str(uuid.uuid4())
        response = client.get("/v1/limits", params={"device_id": device})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"


def test_chunked_request_is_bounded_without_content_length(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/translate", content=iter([b"x" * 40000, b"x" * 40000]))
        assert response.status_code == 413


def test_rate_limit_preserves_liveness_and_cors(settings):
    settings.requests_per_minute = 1
    with TestClient(create_app(settings)) as client:
        assert client.get("/v1/languages").status_code == 200
        response = client.get("/v1/languages", headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 429
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert client.get("/healthz").status_code == 200


def test_missing_meta_secret_rejects_webhook(settings):
    settings.wa_app_secret = ""
    with TestClient(create_app(settings)) as client:
        assert client.post("/whatsapp/webhook", json={"entry": []}).status_code == 401


def test_queue_full_removes_uploaded_audio(settings, short_note, tmp_path, monkeypatch):
    import kettu.api.routes as routes

    context = build_context(settings)
    context.jobs.max_waiting = 0
    saved = tmp_path / "upload" / "note.ogg"
    saved.parent.mkdir()
    saved.write_bytes(short_note.read_bytes())

    async def save(*args):
        return saved

    monkeypatch.setattr(routes, "save_upload", save)
    with TestClient(create_app(settings, context)) as client:
        response = client.post("/v1/notes", data={"device_id": str(uuid.uuid4()), "my_lang": "en-IN"},
                               files={"audio": ("note.ogg", b"placeholder", "audio/ogg")})
        assert response.status_code == 503
        assert not saved.parent.exists()
        assert context.limits.c.reserved_stt == 0


async def test_shutdown_cleans_queued_work_and_releases_reservations():
    queue = JobQueue()
    cleaned = []
    queue.submit(lambda job: asyncio.sleep(60), cleanup=lambda: cleaned.append(True))
    await queue.stop()
    assert cleaned == [True] and not queue.jobs


def test_expired_result_cannot_be_read_before_janitor_runs():
    queue = JobQueue(ttl_s=1)
    job = queue.submit(lambda job: asyncio.sleep(0))
    job.finished = time.monotonic() - 2
    with pytest.raises(KettuError) as error:
        queue.get(job.id)
    assert error.value.code == ErrorCode.NOT_FOUND


def test_unsupported_reply_language_is_rejected_before_saving(settings, monkeypatch):
    import kettu.api.routes as routes

    async def unexpected_save(*args):
        pytest.fail("saved an upload before validating its fields")

    monkeypatch.setattr(routes, "save_upload", unexpected_save)
    with TestClient(create_app(settings)) as client:
        response = client.post("/v1/replies/preview",
                               data={"device_id": str(uuid.uuid4()), "from_lang": "xx", "to_lang": "en-IN"},
                               files={"audio": ("note.ogg", b"audio", "audio/ogg")})
        assert response.status_code == 400


async def test_playlists_cannot_fetch_network_or_local_files(tmp_path):
    playlist = tmp_path / "note.ogg"
    playlist.write_text("#EXTM3U\n#EXTINF:10,\nhttp://127.0.0.1/private\n")
    with pytest.raises(KettuError) as error:
        await audio.check_upload(playlist, 180, 10)
    assert error.value.code == ErrorCode.UNSUPPORTED_FILE


@pytest.mark.parametrize("url", ["http://api.twilio.com/media", "https://evil.example/media", "https://api.twilio.com.evil.example/a"])
async def test_media_rejects_untrusted_urls(url):
    async with httpx.AsyncClient() as client:
        with pytest.raises(WhatsAppError):
            await download(client, url, 10, ("api.twilio.com",), twilio=True)


async def test_media_size_and_cross_host_credentials():
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.host == "api.twilio.com":
            return httpx.Response(302, headers={"Location": "https://media.twiliocdn.com/a"})
        return httpx.Response(200, content=b"x" * 2048)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), auth=("account", "secret")) as client:
        with pytest.raises(KettuError) as error:
            await download(client, "https://api.twilio.com/media", .001,
                           ("api.twilio.com", "twiliocdn.com"), twilio=True)
    assert error.value.code == ErrorCode.TOO_BIG
    assert "authorization" in seen[0].headers and "authorization" not in seen[1].headers


def test_invented_entity_is_not_presented_as_grounded():
    entity = Entity(type="amount", value="₹500", source_text="invented")
    assert grounded([entity], "hello") == []


async def test_repair_cannot_hide_an_omission_by_removing_the_entity(settings):
    class HidingLLM(MockLLM):
        live = True

        async def understand(self, *args):
            entities = [] if args[-1] else [Entity(type="amount", value="₹500", source_text="500", in_translation="₹500")]
            return Understanding(translation="Hello", entities=entities), 1

    result, missing, _ = await Pipeline(settings, None, HidingLLM()).understand_text(
        "hello 500", "en-IN", "hi-IN", 0, False, True)
    assert missing == ["₹500"] and result.entities


@pytest.mark.parametrize("payload", [{"candidates": []}, {"candidates": [{"content": {"parts": [{"text": "not JSON"}]}}]}])
async def test_malformed_gemini_response_gets_plain_error(settings, payload):
    provider = GeminiLLM(settings)
    await provider.http.aclose()
    provider.http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    try:
        with pytest.raises(KettuError):
            await provider.reply("hello", "en-IN", "hi-IN")
    finally:
        await provider.http.aclose()


def test_hosted_mode_refuses_mock_models(settings):
    settings.require_live_models = True
    with pytest.raises(RuntimeError, match="Live speech"):
        with TestClient(create_app(settings)):
            pytest.fail("started a hosted deployment with mock providers")


async def test_usage_restore_paginates_even_when_database_caps_page_size(settings):
    offsets = []
    rows = [{"device_id": str(uuid.uuid4()), "kind": "note", "audio_seconds": 5, "status": "ok"}
            for _ in range(5)]

    def handler(request):
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(200, json=rows[offset:offset + 2])

    store = Store(settings)
    store.http = httpx.AsyncClient(base_url="https://db.example/rest/v1", transport=httpx.MockTransport(handler))
    try:
        restored = await store.today_usage(ist_midnight())
        assert restored == rows and offsets == [0, 2, 4, 5]
    finally:
        await store.close()


async def test_usage_restore_does_not_reset_allowances_on_database_failure(settings):
    store = Store(settings)
    store.http = httpx.AsyncClient(base_url="https://db.example/rest/v1",
                                   transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    try:
        with pytest.raises(RuntimeError, match="restore today's usage"):
            await store.today_usage(ist_midnight())
    finally:
        await store.close()

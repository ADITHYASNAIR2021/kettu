import time
import uuid

import pytest
from fastapi.testclient import TestClient

from kettu.main import create_app

DEVICE = str(uuid.uuid4())


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def wait_for(client, job_id, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/v1/jobs/{job_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def post_note(client, path, device=DEVICE, **extra):
    with open(path, "rb") as f:
        return client.post(
            "/v1/notes",
            data={"my_lang": "ml-IN", "device_id": device, "mode": "listen", **extra},
            files={"audio": ("PTT-20261101-WA0001.opus", f, "audio/ogg")},
        )


def test_note_round_trip(client, short_note):
    resp = post_note(client, short_note)
    assert resp.status_code == 202
    body = wait_for(client, resp.json()["job_id"])
    assert body["status"] == "done"
    result = body["result"]
    assert result["detected_lang"] == "bn-IN"
    assert result["translation"] and result["transcript"]
    assert {e["type"] for e in result["entities"]} >= {"time", "amount"}


def test_daily_limit_message_not_error(client, short_note):
    device = str(uuid.uuid4())
    for _ in range(3):
        wait_for(client, post_note(client, short_note, device).json()["job_id"])
    resp = post_note(client, short_note, device)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "daily_limit"
    assert client.get("/v1/limits", params={"device_id": device}).json()["notes_left"] == 0


def test_bad_inputs_get_plain_errors(client, tmp_path, short_note):
    assert post_note(client, short_note, device="not-a-uuid").json()["error"]["code"] == "bad_request"
    assert post_note(client, short_note, my_lang="xx-IN").status_code == 400
    junk = tmp_path / "junk.ogg"
    junk.write_bytes(b"\x00" * 2000)
    resp = post_note(client, junk)
    assert resp.status_code == 415 and resp.json()["error"]["code"] == "unsupported_file"


def test_reply_preview_and_speak(client):
    resp = client.post("/v1/replies/preview",
                       json={"text": "നാളെ രാവിലെ വരണം", "from_lang": "ml-IN", "to_lang": "bn-IN", "device_id": DEVICE})
    assert resp.status_code == 200
    draft = resp.json()
    assert draft["target_text"] and draft["back_translation"] and draft["source_text"] == "നാളെ രാവിലെ വരണം"

    audio = client.post("/v1/replies/speak",
                        json={"target_text": draft["target_text"], "to_lang": "bn-IN", "voice": "male",
                              "device_id": DEVICE})
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/mpeg"
    assert len(audio.content) > 500


def test_read_aloud_has_its_own_allowance(client):
    device = str(uuid.uuid4())
    body = {"target_text": "നാളെ രാവിലെ എട്ടു മണിക്ക്", "to_lang": "ml-IN", "device_id": device}
    for _ in range(2):  # replies_per_day is 2 in tests
        assert client.post("/v1/replies/speak", json=body).status_code == 200
    assert client.post("/v1/replies/speak", json=body).json()["error"]["code"] == "daily_limit"
    listen = client.post("/v1/replies/speak", json={**body, "purpose": "read_aloud"})
    assert listen.status_code == 200 and listen.headers["content-type"] == "audio/mpeg"
    assert client.get("/v1/limits", params={"device_id": device}).json()["replies_left"] == 0


def test_spoken_reply_preview(client, short_note):
    with open(short_note, "rb") as f:
        resp = client.post("/v1/replies/preview",
                           data={"from_lang": "ml-IN", "to_lang": "bn-IN", "device_id": DEVICE},
                           files={"audio": ("reply.ogg", f, "audio/ogg")})
    assert resp.status_code == 200, resp.text
    assert resp.json()["source_text"]


def test_feedback_and_health(client):
    resp = client.post("/v1/feedback", json={"kind": "note", "rating": -1, "reason": "wrong_words",
                                             "lang": "ml-IN", "device_id": DEVICE})
    assert resp.status_code == 204
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/healthz", params={"deep": 1}).json()["ok"] is True
    assert len(client.get("/v1/languages").json()) == 10


def test_expired_job_is_404(client):
    resp = client.get("/v1/jobs/nope")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "not_found"

import asyncio
import time
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from kettu.main import create_app
from kettu.whatsapp import twilio
from kettu.whatsapp.twilio import MediaStore, TwilioClient, to_bot_message, twilio_signature

PUBLIC = "https://kettu-test.trycloudflare.com"
ME = "whatsapp:+919876543210"


@pytest.fixture
def tw_settings(settings):
    settings.wa_access_token = ""  # Meta bot off; Twilio on
    settings.twilio_account_sid = "ACtest"
    settings.twilio_auth_token = "tok"
    settings.public_api_url = PUBLIC
    settings.wa_allowed_numbers = "919876543210"
    return settings


class FakeTwilio:
    """Stands in for api.twilio.com: records sent messages, serves the forwarded voice note."""

    def __init__(self, audio: bytes):
        self.audio = audio
        self.sent: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, content=self.audio, headers={"content-type": "audio/ogg"})
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.sent.append(form)
        return httpx.Response(201, json={"sid": f"SM{len(self.sent)}"})

    def bodies(self):
        return [m.get("Body", "") for m in self.sent]


def post(client, form: dict, token="tok", url=PUBLIC + "/twilio/webhook"):
    return client.post("/twilio/webhook", data=form, headers={"X-Twilio-Signature": twilio_signature(token, url, form)})


def wait_until(cond, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.1)
    raise AssertionError("timed out")


def test_menu_numbers_become_button_ids(settings):
    c = TwilioClient(settings, MediaStore(), http=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(201))))
    c.menus["91800"] = [("reply:bn-IN", "Reply in Bengali"), ("fb:up:note", "👍"), ("fb:down:note", "👎")]
    assert c.resolve_choice("91800", " 1. ") == "reply:bn-IN"
    assert c.resolve_choice("91800", "👎") == "fb:down:note"
    assert c.resolve_choice("91800", "4") is None
    msg = to_bot_message({"From": "whatsapp:+91800", "Body": "2", "NumMedia": "0", "MessageSid": "SM1"}, c)
    assert msg["type"] == "interactive" and msg["interactive"]["button_reply"]["id"] == "fb:up:note"
    voice = to_bot_message({"From": "whatsapp:+91800", "NumMedia": "1", "MediaUrl0": "https://api.twilio.com/m/1",
                            "MediaContentType0": "audio/ogg", "MessageSid": "SM2"}, c)
    assert voice["type"] == "audio" and voice["audio"]["id"] == "https://api.twilio.com/m/1"


def test_full_twilio_conversation(tw_settings, short_note, monkeypatch):
    monkeypatch.setattr(twilio, "SEND_GAP_S", 0)
    fake = FakeTwilio(short_note.read_bytes())
    app = create_app(tw_settings)
    with TestClient(app) as client:
        app.state.twilio_bot.wa.http = httpx.AsyncClient(transport=httpx.MockTransport(fake), follow_redirects=True)

        # unsigned / wrongly signed requests are refused
        assert post(client, {"From": ME, "Body": "hi", "MessageSid": "SMx"}, token="wrong").status_code == 403

        # 1. hello → welcome + numbered language list
        assert post(client, {"From": ME, "Body": "hi", "NumMedia": "0", "MessageSid": "SM1"}).status_code == 200
        wait_until(lambda: any("Reply with a number" in b for b in fake.bodies()))
        assert all(m["To"] == ME and m["From"] == "whatsapp:+14155238886" for m in fake.sent)

        # 2. "1" picks Malayalam
        post(client, {"From": ME, "Body": "1", "NumMedia": "0", "MessageSid": "SM2"})
        wait_until(lambda: any("മലയാളം" in b and "✅" in b for b in fake.bodies()))

        # 3. forwarded voice note → result text + numbered reply menu
        post(client, {"From": ME, "NumMedia": "1", "MediaUrl0": "https://api.twilio.com/media/ME1",
                      "MediaContentType0": "audio/ogg", "MessageSid": "SM3"})
        wait_until(lambda: any("*1* · বাংলা" in b for b in fake.bodies()))

        # 4. "1" = reply in Bengali, then a typed reply → preview menu
        post(client, {"From": ME, "Body": "1", "NumMedia": "0", "MessageSid": "SM4"})
        wait_until(lambda: any("🎙️" in b for b in fake.bodies()))
        post(client, {"From": ME, "Body": "നാളെ രാവിലെ വരാം", "NumMedia": "0", "MessageSid": "SM5"})
        wait_until(lambda: any("🔊" in b and "*1*" in b for b in fake.bodies()))

        # 5. "1" = make voice note → media message pointing at our public URL, which serves OGG/Opus
        post(client, {"From": ME, "Body": "1", "NumMedia": "0", "MessageSid": "SM6"})
        wait_until(lambda: any("MediaUrl" in m for m in fake.sent))
        media_url = next(m["MediaUrl"] for m in fake.sent if "MediaUrl" in m)
        assert media_url.startswith(PUBLIC + "/media/")
        audio = client.get(media_url.removeprefix(PUBLIC))
        assert audio.status_code == 200 and audio.headers["content-type"] == "audio/ogg" and audio.content[:4] == b"OggS"
        wait_until(lambda: "Forward" in fake.bodies()[-1] or "ഫോർവേഡ്" in fake.bodies()[-1] or "Forward" in "".join(fake.bodies()[-2:]))

        # duplicate delivery of the same MessageSid is ignored
        n = len(fake.sent)
        post(client, {"From": ME, "Body": "1", "NumMedia": "0", "MessageSid": "SM6"})
        time.sleep(0.5)
        assert len(fake.sent) == n


def test_strangers_are_ignored(tw_settings, short_note, monkeypatch):
    monkeypatch.setattr(twilio, "SEND_GAP_S", 0)
    fake = FakeTwilio(short_note.read_bytes())
    app = create_app(tw_settings)
    with TestClient(app) as client:
        app.state.twilio_bot.wa.http = httpx.AsyncClient(transport=httpx.MockTransport(fake))
        post(client, {"From": "whatsapp:+919999999999", "Body": "hi", "NumMedia": "0", "MessageSid": "SMz"})
        time.sleep(0.5)
        assert fake.sent == []


def test_media_links_expire(monkeypatch):
    store = MediaStore()
    token = store.put(b"OggS...", "audio/ogg")
    assert store.get(token) == (b"OggS...", "audio/ogg")
    monkeypatch.setattr(twilio, "MEDIA_TTL_S", -1)
    assert store.get(token) is None

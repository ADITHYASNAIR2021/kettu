import re
from xml.etree import ElementTree

import httpx
import pytest
from fastapi.testclient import TestClient

from kettu.main import create_app
from kettu.whatsapp import twilio
from kettu.whatsapp.twilio import twilio_signature

PUBLIC = "https://kettu-test.ngrok-free.app"
ME = "whatsapp:+919876543210"


@pytest.fixture
def app_and_api(settings, short_note):
    settings.wa_access_token = ""
    settings.twilio_account_sid, settings.twilio_auth_token = "AC", "tok"
    settings.twilio_whatsapp_from = "whatsapp:+17372508034"
    settings.twilio_mode, settings.twilio_reply = "webhook", "twiml"
    settings.public_api_url = PUBLIC
    settings.wa_allowed_numbers = "919876543210"
    twilio._seen.clear()
    calls: list[httpx.Request] = []

    def api(request: httpx.Request):
        calls.append(request)
        if request.method == "GET":  # media download of the forwarded voice note
            return httpx.Response(200, content=short_note.read_bytes(), headers={"content-type": "audio/ogg"})
        return httpx.Response(400, json={"code": 21654})  # the trial number refuses REST sends

    return create_app(settings), calls, api


def say(client, sid, body="", media=False):
    form = {"From": ME, "Body": body, "NumMedia": "1" if media else "0", "MessageSid": sid}
    if media:
        form.update(MediaUrl0="https://api.twilio.com/media/ME1", MediaContentType0="audio/ogg")
    r = client.post("/twilio/webhook", data=form,
                    headers={"X-Twilio-Signature": twilio_signature("tok", PUBLIC + "/twilio/webhook", form)})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/xml")
    root = ElementTree.fromstring(r.text)
    return [(m.findtext("Body") or "", m.findtext("Media")) for m in root.findall("Message")]


def test_replies_travel_inside_the_webhook_response(app_and_api):
    app, calls, api = app_and_api
    with TestClient(app) as client:
        app.state.twilio_bot.wa.http = httpx.AsyncClient(transport=httpx.MockTransport(api), follow_redirects=True)

        msgs = say(client, "SM1", "hi")
        assert any("Kettu" in b for b, _ in msgs) and any("Reply with a number" in b for b, _ in msgs)

        assert any("✅" in b for b, _ in say(client, "SM2", "1"))

        msgs = say(client, "SM3", media=True)
        assert any(re.search(r"\*1\* · বাংলা", b) for b, _ in msgs)

        say(client, "SM4", "1")
        assert any("🔊" in b for b, _ in say(client, "SM5", "നാളെ വരാം"))

        msgs = say(client, "SM6", "1")
        media = [m for _, m in msgs if m]
        assert media and media[0].startswith(PUBLIC + "/media/")
        assert client.get(media[0].removeprefix(PUBLIC)).content[:4] == b"OggS"

        assert say(client, "SM6", "1") == []  # Twilio retry of the same message: answered once
        assert not [c for c in calls if c.method == "POST"], "nothing may go through the REST API in twiml mode"

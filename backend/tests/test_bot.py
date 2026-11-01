import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from kettu.container import build_context
from kettu.main import create_app
from kettu.whatsapp import webhook
from kettu.whatsapp.bot import Bot, device_for
from kettu.whatsapp.client import split_text

PHONE = "919800000001"


class FakeWhatsApp:
    def __init__(self, media: bytes):
        self.media = media
        self.sent: list[tuple] = []

    async def mark_read(self, message_id, typing=True):
        pass

    async def download_media(self, media_id):
        return self.media, "audio/ogg; codecs=opus"

    async def send_text(self, to, text, reply_to=None):
        self.sent.append(("text", text, reply_to))

    async def send_buttons(self, to, body, buttons, reply_to=None):
        self.sent.append(("buttons", body, [b[0] for b in buttons]))

    async def send_list(self, to, body, button, rows, section):
        self.sent.append(("list", body, [r[0] for r in rows]))

    async def send_voice(self, to, ogg):
        self.sent.append(("voice", ogg[:4], None))

    def kinds(self):
        return [s[0] for s in self.sent]

    def last(self, kind):
        return next(s for s in reversed(self.sent) if s[0] == kind)


def audio_msg(mid):
    return {"from": PHONE, "id": mid, "type": "audio", "audio": {"id": "media-1", "voice": True}}


def choice(mid, cid, kind="button_reply"):
    return {"from": PHONE, "id": mid, "type": "interactive", "interactive": {"type": kind, kind: {"id": cid}}}


def text(mid, body):
    return {"from": PHONE, "id": mid, "type": "text", "text": {"body": body}}


@pytest.fixture
async def bot(settings, short_note):
    ctx = build_context(settings)
    ctx.jobs.start()
    wa = FakeWhatsApp(short_note.read_bytes())
    yield Bot(ctx, wa), wa
    await ctx.jobs.stop()


async def test_full_conversation(bot):
    b, wa = bot
    # 1. First voice note: no language yet → welcome + language list, note parked
    await b.handle(audio_msg("m1"))
    assert wa.kinds() == ["text", "list"]
    assert "lang:ml-IN" in wa.last("list")[2]

    # 2. Pick Malayalam → confirmation, then the parked note is processed automatically
    await b.handle(choice("m2", "lang:ml-IN", "list_reply"))
    result = [s for s in wa.sent if s[0] == "text" and s[2] == "m1"]
    assert result, "result should quote the original voice note"
    assert "বাংলা" in result[0][1]  # detected Bengali, shown by its native name to a Malayalam reader
    buttons = wa.last("buttons")[2]
    assert buttons == ["reply:bn-IN", "fb:up:note", "fb:down:note"]

    # 3. Reply in Bengali → prompt; send text → preview with back-translation and 3 buttons
    await b.handle(choice("m3", "reply:bn-IN"))
    assert "Bengali" in wa.last("text")[1] or "বাংলা" in wa.last("text")[1]
    await b.handle(text("m4", "നാളെ രാവിലെ എട്ടിന് വരണം"))
    assert wa.last("buttons")[2] == ["speak", "retry", "cancel"]

    # 4. Make voice note → real OGG/Opus voice bubble + forward hint
    await b.handle(choice("m5", "speak"))
    assert wa.last("voice")[1] == b"OggS"
    assert "Forward" in wa.last("text")[1]
    assert b.sessions[PHONE].state == "idle"


async def test_spoken_reply_and_feedback(bot):
    b, wa = bot
    await b.handle(choice("a1", "lang:hi-IN", "list_reply"))
    await b.handle(choice("a2", "reply:bn-IN"))
    await b.handle(audio_msg("a3"))  # voice reply while awaiting a reply
    assert wa.last("buttons")[2] == ["speak", "retry", "cancel"]
    await b.handle(choice("a4", "fb:down:note"))
    assert wa.last("buttons")[2][0].startswith("fbr:wrong_language")
    await b.handle(choice("a5", "fbr:wrong_words:note"))
    assert b.ctx.store._feedback[-1]["reason"] == "wrong_words"


async def test_commands_and_limits(bot):
    b, wa = bot
    await b.handle(choice("c1", "lang:bn-IN", "list_reply"))
    await b.handle(text("c2", "help"))
    assert "Kettu" in wa.last("text")[1] or "কেট্টু" in wa.last("text")[1]
    await b.handle(text("c3", "orders"))
    assert b.sessions[PHONE].orders_next
    await b.handle(choice("c4", "speak"))  # nothing to speak yet
    assert wa.last("text")[1]
    for i in range(3):
        await b.handle(audio_msg(f"n{i}"))
    await b.handle(audio_msg("n4"))  # 4th note, limit is 3 in tests
    assert "⚠️" in wa.last("text")[1]


async def test_allowlist_blocks_strangers(settings, short_note):
    settings.wa_allowed_numbers = "911111111111"
    ctx = build_context(settings)
    wa = FakeWhatsApp(short_note.read_bytes())
    await Bot(ctx, wa).handle(text("x", "hi"))
    assert wa.sent == []


def test_device_ids_are_stable_and_not_the_number():
    key1, dev1 = device_for(PHONE, "salt")
    key2, dev2 = device_for(PHONE, "salt")
    assert (key1, dev1) == (key2, dev2)
    assert PHONE not in key1 and PHONE not in dev1


def test_split_text_respects_limit():
    parts = split_text("a" * 5000 + "\n" + "b" * 10, 4096)
    assert all(len(p) <= 4096 for p in parts) and "".join(parts).replace("\n", "") == "a" * 5000 + "b" * 10


def test_webhook_verification_and_signature(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        ok = client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me",
                                                     "hub.challenge": "42"})
        assert ok.status_code == 200 and ok.text == "42"
        assert client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "no",
                                                       "hub.challenge": "42"}).status_code == 403

        received = []

        async def fake_handle(msg, name=""):
            received.append(msg["id"])

        app.state.bot.handle = fake_handle
        body = json.dumps({"entry": [{"changes": [{"value": {
            "contacts": [{"wa_id": PHONE, "profile": {"name": "Joseph"}}],
            "messages": [text("dup-1", "hi")]}}]}]}).encode()
        sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        assert client.post("/whatsapp/webhook", content=body, headers={"x-hub-signature-256": "sha256=bad"}).status_code == 401
        webhook._seen.clear()
        for _ in range(2):  # Meta retries: second delivery must be ignored
            assert client.post("/whatsapp/webhook", content=body, headers={"x-hub-signature-256": sig}).status_code == 200
        time.sleep(0.2)
        assert received == ["dup-1"]

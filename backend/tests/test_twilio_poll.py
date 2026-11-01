import asyncio
from urllib.parse import parse_qs

import httpx
import pytest

from kettu.container import build_context
from kettu.whatsapp import twilio
from kettu.whatsapp.bot import Bot
from kettu.whatsapp.twilio import MediaStore, TwilioClient, TwilioPoller

ME = "whatsapp:+919876543210"
KETTU = "whatsapp:+17372508034"


class FakeTwilioApi:
    """Messages list (newest first, like Twilio), media lookup and download, and outgoing sends."""

    def __init__(self, audio: bytes):
        self.audio = audio
        self.inbound: list[dict] = []
        self.sent: list[dict] = []

    def add(self, sid, body="", media=False, status="received"):
        self.inbound.insert(0, {"sid": sid, "direction": "inbound", "from": ME, "to": KETTU, "status": status,
                                "body": body, "num_media": "1" if media else "0"})

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST":
            self.sent.append({k: v[0] for k, v in parse_qs(request.content.decode()).items()})
            return httpx.Response(201, json={})
        if path.endswith("/Messages.json"):
            assert request.url.params["To"] == KETTU
            return httpx.Response(200, json={"messages": self.inbound})
        if path.endswith("/Media.json"):
            sid = path.split("/Messages/")[1].split("/")[0]
            return httpx.Response(200, json={"media_list": [
                {"content_type": "audio/ogg", "uri": f"/2010-04-01/Accounts/AC/Messages/{sid}/Media/ME1.json"}]})
        if "/Media/" in path:
            return httpx.Response(200, content=self.audio, headers={"content-type": "audio/ogg"})
        return httpx.Response(404)


@pytest.fixture
async def setup(settings, short_note, monkeypatch):
    monkeypatch.setattr(twilio, "SEND_GAP_S", 0)
    twilio._seen.clear()
    settings.twilio_account_sid, settings.twilio_auth_token = "AC", "tok"
    settings.twilio_whatsapp_from, settings.twilio_mode = KETTU, "poll"
    settings.public_api_url = "https://example.ngrok-free.app"
    api = FakeTwilioApi(short_note.read_bytes())
    ctx = build_context(settings)
    ctx.jobs.start()
    client = TwilioClient(settings, MediaStore(), http=httpx.AsyncClient(transport=httpx.MockTransport(api)))
    bot = Bot(ctx, client)
    yield api, TwilioPoller(bot, settings)
    await ctx.jobs.stop()


async def settle(api, check, timeout=20.0):
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        if check():
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"timed out; sent={[m.get('Body', m.get('MediaUrl'))[:40] for m in api.sent]}")


async def test_poller_answers_only_new_messages(setup):
    api, poller = setup
    api.add("SMold", "Hi")  # arrived before Kettu started
    await poller.seed()

    api.add("SMjoin", "join twilio-trial")
    api.add("SMhi", "hi")
    await poller.tick()
    await settle(api, lambda: any("Reply with a number" in m.get("Body", "") for m in api.sent))
    assert all(m["From"] == KETTU and m["To"] == ME for m in api.sent)
    welcome_count = sum("Kettu" in m.get("Body", "") for m in api.sent)
    assert welcome_count == 1, "the old 'Hi' and the join message must not be answered"

    api.add("SM1", "1")  # Malayalam
    await poller.tick()
    await settle(api, lambda: any("✅" in m.get("Body", "") for m in api.sent))

    api.add("SMvoice", media=True)
    await poller.tick()
    await settle(api, lambda: any("*1* · বাংলা" in m.get("Body", "") for m in api.sent))

    n = len(api.sent)
    await poller.tick()  # nothing new → nothing sent
    await asyncio.sleep(0.2)
    assert len(api.sent) == n


async def test_messages_still_arriving_wait_for_next_tick(setup):
    api, poller = setup
    await poller.seed()
    api.add("SMslow", "hi", status="receiving")
    await poller.tick()
    await asyncio.sleep(0.2)
    assert api.sent == []
    api.inbound[0]["status"] = "received"
    await poller.tick()
    await settle(api, lambda: len(api.sent) > 0)

"""WhatsApp through Twilio (works with the Twilio sandbox, no Facebook account needed).

Plugs into the same Bot as the Meta Cloud API client. Twilio has no tap buttons in the sandbox,
so buttons and lists become numbered menus ("reply 1, 2 or 3"); the webhook turns the person's
number back into the button id the Bot expects. Reply audio is served from memory at a short-lived
random URL so Twilio can fetch it, then forgotten.
"""

import asyncio
import base64
import contextvars
import hashlib
import hmac
import logging
import secrets
import time
from xml.sax.saxutils import escape

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

from kettu.config import Settings
from kettu.whatsapp.client import WhatsAppError, split_text

log = logging.getLogger(__name__)
router = APIRouter()

TWILIO_BODY_LIMIT = 1600
SEND_GAP_S = 1.0  # Twilio does not guarantee order; space messages to one person
MEDIA_TTL_S = 600
EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
TWIML_DEADLINE_S = 13.0  # Twilio waits 15 s for a webhook response

# In TwiML reply mode, messages the bot "sends" while handling one webhook are collected here
# and returned in that webhook's response instead of being sent through the REST API.
_collector: contextvars.ContextVar[list[tuple[str, str | None]] | None] = contextvars.ContextVar("twiml", default=None)


def twiml(messages: list[tuple[str, str | None]]) -> str:
    parts = []
    for body, media_url in messages:
        inner = (f"<Body>{escape(body)}</Body>" if body else "") + (f"<Media>{escape(media_url)}</Media>" if media_url else "")
        parts.append(f"<Message>{inner}</Message>")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{"".join(parts)}</Response>'


class MediaStore:
    """Reply audio waiting for Twilio to fetch it. In memory only; gone after 10 minutes."""

    def __init__(self):
        self._items: dict[str, tuple[bytes, str, float]] = {}

    def put(self, data: bytes, mime: str) -> str:
        self._sweep()
        token = secrets.token_urlsafe(24)
        self._items[token] = (data, mime, time.monotonic())
        return token

    def get(self, token: str) -> tuple[bytes, str] | None:
        self._sweep()
        item = self._items.get(token)
        return (item[0], item[1]) if item else None

    def _sweep(self) -> None:
        now = time.monotonic()
        for k in [k for k, (_, _, t) in self._items.items() if now - t > MEDIA_TTL_S]:
            self._items.pop(k, None)


def twilio_signature(auth_token: str, url: str, params: dict[str, str]) -> str:
    """Twilio's scheme: HMAC-SHA1 over the URL followed by each POST key+value in key order."""
    payload = url + "".join(k + params[k] for k in sorted(params))
    return base64.b64encode(hmac.new(auth_token.encode(), payload.encode(), hashlib.sha1).digest()).decode()


def plain(number: str) -> str:
    """'whatsapp:+919876543210' → '919876543210' (the form the Bot and the allow-list use)."""
    return number.removeprefix("whatsapp:").lstrip("+")


class TwilioClient:
    """Same methods as WhatsAppClient, so the Bot does not care which one it talks to."""

    def __init__(self, settings: Settings, media: MediaStore, http: httpx.AsyncClient | None = None):
        self.s = settings
        self.media = media
        self.http = http or httpx.AsyncClient(
            auth=(settings.twilio_account_sid, settings.twilio_auth_token), timeout=30.0, follow_redirects=True
        )
        self.url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        self.menus: dict[str, list[tuple[str, str]]] = {}  # phone → [(button id, title)] awaiting a number
        self._locks: dict[str, asyncio.Lock] = {}

    async def _send(self, to: str, body: str = "", media_url: str | None = None) -> None:
        collected = _collector.get()
        if collected is not None:
            collected.append((body, media_url))
            return
        data = {"From": self.s.twilio_whatsapp_from, "To": f"whatsapp:+{plain(to)}"}
        if body:
            data["Body"] = body
        if media_url:
            data["MediaUrl"] = media_url
        lock = self._locks.setdefault(to, asyncio.Lock())
        async with lock:
            resp = await self.http.post(self.url, data=data)
            if resp.status_code >= 300:
                log.warning("twilio send failed status=%s body=%s", resp.status_code, resp.text[:300])
                raise WhatsAppError(resp.status_code)
            await asyncio.sleep(SEND_GAP_S)

    async def mark_read(self, message_id: str, typing: bool = True) -> None:
        return None  # not available through Twilio

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        """For Twilio the media id is the MediaUrl itself; fetching it needs the account credentials."""
        resp = await self.http.get(media_id)
        if resp.status_code != 200:
            raise WhatsAppError(f"media download {resp.status_code}")
        return resp.content, resp.headers.get("content-type", "audio/ogg")

    async def send_text(self, to: str, text: str, reply_to: str | None = None) -> None:
        self.menus.pop(to, None)  # a menu is only valid until the bot says something else
        for part in split_text(text, TWILIO_BODY_LIMIT):
            await self._send(to, part)

    async def send_buttons(self, to: str, body: str, buttons: list[tuple[str, str]], reply_to: str | None = None) -> None:
        options = buttons[:3]
        lines = [body, ""] + [f"*{i}* · {title}" for i, (_, title) in enumerate(options, start=1)]
        await self._send(to, "\n".join(lines)[:TWILIO_BODY_LIMIT])
        self.menus[to] = options

    async def send_list(self, to: str, body: str, button: str, rows: list[tuple[str, str, str]], section: str) -> None:
        options = [(rid, title) for rid, title, _ in rows[:10]]
        lines = [body, ""] + [
            f"*{i}* · {title}" + (f" ({desc})" if desc and desc != title else "")
            for i, (_, title, desc) in enumerate(rows[:10], start=1)
        ]
        lines += ["", "_Reply with a number._"]
        await self._send(to, "\n".join(lines)[:TWILIO_BODY_LIMIT])
        self.menus[to] = options

    async def send_voice(self, to: str, ogg_opus: bytes) -> None:
        if not self.s.public_api_url:
            raise WhatsAppError("PUBLIC_API_URL is not set, Twilio cannot fetch the audio")
        token = self.media.put(ogg_opus, "audio/ogg")
        self.menus.pop(to, None)
        await self._send(to, media_url=f"{self.s.public_api_url.rstrip('/')}/media/{token}.ogg")

    def resolve_choice(self, phone: str, text: str) -> str | None:
        """'2', '2.', ' 2 ' or the option's own title (e.g. '👍') → that option's button id."""
        options = self.menus.get(phone)
        if not options:
            return None
        t = text.strip().rstrip(".").strip()
        if t.isdigit() and 1 <= int(t) <= len(options):
            return options[int(t) - 1][0]
        for bid, title in options:
            if t.casefold() == title.casefold():
                return bid
        return None


def to_bot_message(form: dict[str, str], client: TwilioClient) -> dict:
    """Twilio webhook fields → the Meta-style message dict the Bot understands."""
    phone = plain(form.get("From", ""))
    msg: dict = {"from": phone, "id": form.get("MessageSid", "")}
    if int(form.get("NumMedia", "0") or 0) > 0:
        ctype = form.get("MediaContentType0", "")
        if ctype.startswith("audio/") or ctype in ("application/ogg", "video/ogg"):
            msg.update(type="audio", audio={"id": form.get("MediaUrl0", ""), "mime_type": ctype})
            return msg
        msg.update(type="unsupported")
        return msg
    body = form.get("Body", "")
    choice = client.resolve_choice(phone, body)
    if choice:
        msg.update(type="interactive", interactive={"type": "button_reply", "button_reply": {"id": choice}})
    else:
        msg.update(type="text", text={"body": body})
    return msg


_tasks: set[asyncio.Task] = set()
_seen: dict[str, float] = {}


@router.post("/twilio/webhook")
async def twilio_webhook(request: Request):
    form = {k: str(v) for k, v in (await request.form()).items()}
    s: Settings = request.app.state.ctx.settings
    bot = getattr(request.app.state, "twilio_bot", None)
    if bot is None:
        return Response(EMPTY_TWIML, media_type="text/xml")

    url = (s.public_api_url.rstrip("/") + "/twilio/webhook") if s.public_api_url else str(request.url)
    sent = request.headers.get("x-twilio-signature", "")
    if not hmac.compare_digest(sent, twilio_signature(s.twilio_auth_token, url, form)):
        log.warning("twilio webhook signature mismatch (check PUBLIC_API_URL matches the URL in the Twilio console)")
        return Response(status_code=403)

    if s.twilio_reply == "twiml":
        return Response(await answer_inline(bot, form), media_type="text/xml")
    dispatch(bot, form)
    return Response(EMPTY_TWIML, media_type="text/xml")


async def answer_inline(bot, form: dict[str, str]) -> str:
    """Run the bot for this one message and return everything it says as TwiML."""
    sid = form.get("MessageSid", "")
    if not sid or sid in _seen:
        return EMPTY_TWIML
    _seen[sid] = time.monotonic()
    collected: list[tuple[str, str | None]] = []
    token = _collector.set(collected)
    try:
        await asyncio.wait_for(bot.handle(to_bot_message(form, bot.wa), form.get("ProfileName", "")), TWIML_DEADLINE_S)
    except asyncio.TimeoutError:
        log.warning("twiml: bot took longer than %.0fs, replying with what is ready", TWIML_DEADLINE_S)
        collected.append(("⏳ That one is taking long. Please forward it again in a minute.", None))
    finally:
        _collector.reset(token)
    return twiml(collected)


def dispatch(bot, form: dict[str, str]) -> None:
    """Hand one incoming message to the bot in the background, once per MessageSid."""
    sid = form.get("MessageSid", "")
    now = time.monotonic()
    for k in [k for k, t in _seen.items() if now - t > 3600]:
        _seen.pop(k, None)
    if not sid or sid in _seen:
        return
    _seen[sid] = now
    task = asyncio.create_task(bot.handle(to_bot_message(form, bot.wa), form.get("ProfileName", "")))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


class TwilioPoller:
    """For Twilio's trial "Try out WhatsApp" number, which cannot call a webhook: read new incoming
    messages from the Messages API every few seconds and feed them to the bot like webhook calls."""

    def __init__(self, bot, settings: Settings):
        self.bot = bot
        self.s = settings
        self.base = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}"
        self.seen: set[str] = set()

    @property
    def http(self) -> httpx.AsyncClient:
        return self.bot.wa.http  # the authenticated Twilio client

    async def _inbound(self) -> list[dict]:
        resp = await self.http.get(f"{self.base}/Messages.json", params={"To": self.s.twilio_whatsapp_from, "PageSize": 30})
        if resp.status_code != 200:
            log.warning("twilio poll status=%s", resp.status_code)
            return []
        return [m for m in resp.json().get("messages", []) if m.get("direction") == "inbound"]

    async def _media(self, sid: str) -> tuple[str, str] | None:
        resp = await self.http.get(f"{self.base}/Messages/{sid}/Media.json")
        items = resp.json().get("media_list", []) if resp.status_code == 200 else []
        if not items:
            return None
        return "https://api.twilio.com" + items[0]["uri"].removesuffix(".json"), items[0].get("content_type", "")

    async def seed(self) -> None:
        """Messages that arrived before Kettu started are not answered."""
        self.seen.update(m["sid"] for m in await self._inbound())

    async def tick(self) -> None:
        fresh = [m for m in await self._inbound() if m["sid"] not in self.seen and m.get("status") == "received"]
        for m in reversed(fresh):  # the API lists newest first
            self.seen.add(m["sid"])
            body = m.get("body") or ""
            if body.strip().lower().startswith("join "):
                continue  # Twilio's own sandbox join message
            form = {"From": m.get("from", ""), "Body": body, "NumMedia": str(m.get("num_media") or "0"),
                    "MessageSid": m["sid"]}
            if int(form["NumMedia"]) > 0 and (media := await self._media(m["sid"])):
                form["MediaUrl0"], form["MediaContentType0"] = media
            dispatch(self.bot, form)
        if len(self.seen) > 5000:
            self.seen = set(list(self.seen)[-1000:])

    async def run(self) -> None:
        await self.seed()
        log.info("twilio: polling %s every %.1fs", self.s.twilio_whatsapp_from, self.s.twilio_poll_seconds)
        while True:
            try:
                await self.tick()
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                log.warning("twilio poll failed: %s", type(exc).__name__)
            await asyncio.sleep(self.s.twilio_poll_seconds)


@router.get("/media/{name}")
async def media(name: str, request: Request):
    store: MediaStore | None = getattr(request.app.state, "media", None)
    item = store.get(name.split(".")[0]) if store else None
    if not item:
        return Response(status_code=404)
    data, mime = item
    return Response(data, media_type=mime, headers={"Cache-Control": "no-store"})

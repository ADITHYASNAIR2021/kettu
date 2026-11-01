"""WhatsApp Cloud API webhook: verification handshake, signature check, dedupe, hand-off to the bot.

Meta expects a 200 within a few seconds and retries otherwise, so work runs in the background.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse, Response

log = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp")

_seen: dict[str, float] = {}
_tasks: set[asyncio.Task] = set()
SEEN_TTL_S = 3600


def valid_signature(secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def first_time(message_id: str) -> bool:
    now = time.monotonic()
    for mid in [m for m, t in _seen.items() if now - t > SEEN_TTL_S]:
        _seen.pop(mid, None)
    if message_id in _seen:
        return False
    _seen[message_id] = now
    return True


@router.get("/webhook")
async def verify(
    request: Request,
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
):
    s = request.app.state.ctx.settings
    if mode == "subscribe" and s.wa_verify_token and hmac.compare_digest(token, s.wa_verify_token):
        return PlainTextResponse(challenge)
    return Response(status_code=403)


@router.post("/webhook")
async def receive(request: Request):
    body = await request.body()
    s = request.app.state.ctx.settings
    if s.wa_app_secret:
        if not valid_signature(s.wa_app_secret, body, request.headers.get("x-hub-signature-256")):
            return Response(status_code=401)
    else:
        log.warning("WA_APP_SECRET not set: webhook signature not checked")

    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return Response(status_code=200)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=200)

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                if not first_time(msg.get("id", "")):
                    continue
                task = asyncio.create_task(bot.handle(msg, names.get(msg.get("from"), "")))
                _tasks.add(task)
                task.add_done_callback(_tasks.discard)
    return Response(status_code=200)

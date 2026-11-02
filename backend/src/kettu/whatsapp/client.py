"""WhatsApp Cloud API (Meta Graph API) client: download media, upload media, send messages."""

import logging

import httpx

from kettu.config import Settings

log = logging.getLogger(__name__)

TEXT_LIMIT = 4096
BUTTON_TITLE_LIMIT = 20
BODY_LIMIT = 1024


class WhatsAppError(Exception):
    pass


class WhatsAppClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient | None = None):
        self.s = settings
        self.base = f"https://graph.facebook.com/{settings.wa_graph_version}"
        self.http = http or httpx.AsyncClient(
            headers={"Authorization": f"Bearer {settings.wa_access_token}"}, timeout=30.0
        )

    async def _send(self, payload: dict) -> dict:
        body = {"messaging_product": "whatsapp", **payload}
        resp = await self.http.post(f"{self.base}/{self.s.wa_phone_number_id}/messages", json=body)
        if resp.status_code >= 300:
            log.warning("whatsapp send failed status=%s", resp.status_code)
            raise WhatsAppError(resp.status_code)
        return resp.json()

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        from kettu.whatsapp.media import download

        if not media_id.isdigit():
            raise WhatsAppError("Invalid media id")
        meta = await self.http.get(f"{self.base}/{media_id}")
        if meta.status_code != 200:
            raise WhatsAppError(f"media lookup {meta.status_code}")
        info = meta.json()
        data, mime = await download(self.http, info["url"], self.s.max_upload_mb,
                                    ("fbsbx.com", "facebook.com", "fbcdn.net"))
        return data, info.get("mime_type", mime)

    async def upload_media(self, data: bytes, mime: str, filename: str) -> str:
        resp = await self.http.post(
            f"{self.base}/{self.s.wa_phone_number_id}/media",
            data={"messaging_product": "whatsapp", "type": mime},
            files={"file": (filename, data, mime)},
        )
        if resp.status_code >= 300:
            log.warning("whatsapp upload failed status=%s", resp.status_code)
            raise WhatsAppError(resp.status_code)
        return resp.json()["id"]

    async def mark_read(self, message_id: str, typing: bool = True) -> None:
        payload: dict = {"status": "read", "message_id": message_id}
        if typing:
            payload["typing_indicator"] = {"type": "text"}
        try:
            await self._send(payload)
        except (WhatsAppError, httpx.HTTPError):
            pass  # cosmetic only

    async def send_text(self, to: str, text: str, reply_to: str | None = None) -> None:
        parts = split_text(text, TEXT_LIMIT)
        for i, part in enumerate(parts):
            payload: dict = {"to": to, "type": "text", "text": {"body": part, "preview_url": False}}
            if reply_to and i == 0:
                payload["context"] = {"message_id": reply_to}
            await self._send(payload)

    async def send_buttons(self, to: str, body: str, buttons: list[tuple[str, str]], reply_to: str | None = None) -> None:
        payload: dict = {
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body[:BODY_LIMIT]},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": bid, "title": title[:BUTTON_TITLE_LIMIT]}}
                        for bid, title in buttons[:3]
                    ]
                },
            },
        }
        if reply_to:
            payload["context"] = {"message_id": reply_to}
        await self._send(payload)

    async def send_list(self, to: str, body: str, button: str, rows: list[tuple[str, str, str]], section: str) -> None:
        await self._send({
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body[:BODY_LIMIT]},
                "action": {
                    "button": button[:BUTTON_TITLE_LIMIT],
                    "sections": [{
                        "title": section[:24],
                        "rows": [{"id": rid, "title": title[:24], "description": desc[:72]} for rid, title, desc in rows[:10]],
                    }],
                },
            },
        })

    async def send_voice(self, to: str, ogg_opus: bytes) -> None:
        media_id = await self.upload_media(ogg_opus, "audio/ogg", "kettu-reply.ogg")
        await self._send({"to": to, "type": "audio", "audio": {"id": media_id, "voice": True}})


def split_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts, current = [], ""
    for para in text.split("\n"):
        while len(para) > limit:
            if current:
                parts.append(current)
                current = ""
            parts.append(para[:limit])
            para = para[limit:]
        if len(current) + len(para) + 1 > limit:
            parts.append(current)
            current = para
        else:
            current = f"{current}\n{para}" if current else para
    if current:
        parts.append(current)
    return parts

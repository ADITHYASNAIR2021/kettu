"""Bound provider media downloads and prevent fetching arbitrary webhook URLs."""

from urllib.parse import urlsplit

import httpx

from kettu.domain.errors import ErrorCode, KettuError
from kettu.whatsapp.client import WhatsAppError


async def download(client: httpx.AsyncClient, url: str, max_mb: float, hosts: tuple[str, ...],
                   *, twilio: bool = False) -> tuple[bytes, str]:
    for attempt in range(4):
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443)
                or not any(host == h or host.endswith("." + h) for h in hosts)):
            raise WhatsAppError("Untrusted media URL")
        # Account credentials belong only on Twilio's API, never its CDN or a redirect target.
        kwargs = {"auth": None} if twilio and host != "api.twilio.com" else {}
        async with client.stream("GET", url, follow_redirects=False, **kwargs) as response:
            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    raise WhatsAppError("Missing media redirect")
                url = str(response.url.join(location))
                continue
            if response.status_code != 200:
                raise WhatsAppError(f"media download {response.status_code}")
            limit = int(max_mb * 1024 * 1024)
            data = bytearray()
            async for chunk in response.aiter_bytes():
                if len(data) + len(chunk) > limit:
                    raise KettuError(ErrorCode.TOO_BIG)
                data.extend(chunk)
            return bytes(data), response.headers.get("content-type", "audio/ogg")
    raise WhatsAppError("Too many media redirects")

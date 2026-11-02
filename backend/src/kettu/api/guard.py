"""Bound request bodies before multipart parsing and apply a small, process-local ingress gate."""

import asyncio
import tempfile
import time
from collections import deque

from starlette.responses import JSONResponse


class RequestGuard:
    def __init__(self, app, settings):
        self.app, self.settings = app, settings
        self.active = 0
        self.peers = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        path = scope["path"]
        private = path.startswith(("/v1/", "/media/"))

        async def private_send(message):
            if message["type"] == "http.response.start":
                extra = [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer")]
                if private:
                    extra.append((b"cache-control", b"no-store"))
                message["headers"] = [
                    (k, v) for k, v in message.get("headers", [])
                    if k.lower() not in {k for k, _ in extra}
                ] + extra
            await send(message)

        async def reject(status, code, message):
            await JSONResponse({"error": {"code": code, "message": message}}, status_code=status)(scope, receive, private_send)

        # Cheap liveness probes must not depend on rate limits or model availability.
        if path == "/healthz" and not scope.get("query_string"):
            return await self.app(scope, receive, private_send)
        if scope["method"] == "OPTIONS":
            return await self.app(scope, receive, private_send)
        now = time.monotonic()
        # Use only the server's resolved peer; never trust a user-supplied forwarded header here.
        peer = (scope.get("client") or ("unknown", 0))[0]
        for key in [k for k, values in self.peers.items() if not values or now - values[-1] >= 60]:
            self.peers.pop(key, None)
        if peer not in self.peers and len(self.peers) >= 10000:
            return await reject(503, "busy", "Kettu is busy. Please try again shortly.")
        values = self.peers.setdefault(peer, deque())
        while values and now - values[0] >= 60:
            values.popleft()
        if len(values) >= self.settings.requests_per_minute:
            return await reject(429, "busy", "Too many requests. Please wait a minute.")
        values.append(now)
        if self.active >= self.settings.max_active_requests:
            return await reject(503, "busy", "Kettu is busy. Please try again shortly.")

        multipart = headers.get(b"content-type", b"").lower().startswith(b"multipart/")
        limit = int(self.settings.max_upload_mb * 1024 * 1024) + 65536 if multipart else 65536
        try:
            length = int(headers.get(b"content-length", b"0"))
            if length < 0:
                raise ValueError
        except ValueError:
            return await reject(400, "bad_request", "Invalid request size.")
        if length > limit:
            return await reject(413, "too_big", "That request is too large.")

        self.active += 1
        try:
            # Spool larger bodies to disk, with a hard byte limit even for chunked requests.
            with tempfile.SpooledTemporaryFile(max_size=65536) as body:
                size = 0
                try:
                    async with asyncio.timeout(30):
                        while True:
                            message = await receive()
                            if message["type"] == "http.disconnect":
                                return
                            chunk = message.get("body", b"")
                            size += len(chunk)
                            if size > limit:
                                return await reject(413, "too_big", "That request is too large.")
                            body.write(chunk)
                            if not message.get("more_body", False):
                                break
                except TimeoutError:
                    return await reject(408, "bad_request", "The upload took too long. Please try again.")
                body.seek(0)
                exhausted = False

                async def replay():
                    nonlocal exhausted
                    if exhausted:
                        return await receive()
                    chunk = body.read(65536)
                    exhausted = body.tell() >= size
                    return {"type": "http.request", "body": chunk, "more_body": not exhausted}

                await self.app(scope, replay, private_send)
        finally:
            self.active -= 1

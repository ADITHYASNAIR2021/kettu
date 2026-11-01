"""Persistence for numbers only: usage events, feedback, bot preferences.

Supabase is reached through its REST (PostgREST) API with the service key, server-side only.
Without Supabase settings everything stays in memory, which is fine for local development.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from kettu.config import Settings

log = logging.getLogger(__name__)


class Store:
    def __init__(self, settings: Settings):
        self.enabled = bool(settings.supabase_url and settings.supabase_service_key)
        self._prefs: dict[str, dict] = {}
        self._feedback: list[dict] = []
        self._tasks: set[asyncio.Task] = set()
        self.http = (
            httpx.AsyncClient(
                base_url=settings.supabase_url.rstrip("/") + "/rest/v1",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
            if self.enabled
            else None
        )

    def _background(self, coro) -> None:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _insert(self, table: str, row: dict) -> None:
        if not self.http:
            return
        try:
            resp = await self.http.post(f"/{table}", json=row, headers={"Prefer": "return=minimal"})
            if resp.status_code >= 300:
                log.warning("supabase insert %s status=%s", table, resp.status_code)
        except httpx.HTTPError as exc:
            log.warning("supabase insert %s failed: %s", table, type(exc).__name__)

    def log_usage(self, **row: Any) -> None:
        """Fire and forget. Rows hold ids, numbers, languages and status, never words."""
        self._background(self._insert("usage_events", row))

    async def add_feedback(self, row: dict) -> None:
        self._feedback.append(row)
        await self._insert("feedback", row)

    async def today_usage(self, since: datetime) -> list[dict]:
        """Rows since IST midnight, used to restore counters after a restart."""
        if not self.http:
            return []
        try:
            resp = await self.http.get(
                "/usage_events",
                params={
                    "select": "device_id,kind,audio_seconds,tts_chars,status",
                    "created_at": f"gte.{since.isoformat()}",
                    "limit": "20000",
                },
            )
            return resp.json() if resp.status_code == 200 else []
        except (httpx.HTTPError, ValueError):
            return []

    async def get_prefs(self, key: str) -> dict | None:
        if key in self._prefs:
            return self._prefs[key]
        if not self.http:
            return None
        try:
            resp = await self.http.get("/wa_prefs", params={"wa_hash": f"eq.{key}", "select": "*"})
            rows = resp.json() if resp.status_code == 200 else []
        except (httpx.HTTPError, ValueError):
            rows = []
        if rows:
            self._prefs[key] = rows[0]
            return rows[0]
        return None

    async def put_prefs(self, key: str, prefs: dict) -> None:
        row = {"wa_hash": key, **prefs}
        self._prefs[key] = row
        if not self.http:
            return
        try:
            await self.http.post(
                "/wa_prefs", json=row, headers={"Prefer": "resolution=merge-duplicates,return=minimal"}
            )
        except httpx.HTTPError as exc:
            log.warning("supabase prefs failed: %s", type(exc).__name__)

    async def ping(self) -> bool:
        if not self.http:
            return True
        try:
            resp = await self.http.get("/daily_budget", params={"select": "day", "limit": "1"})
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

"""One in-process queue for notes, shared by the PWA and the WhatsApp bot.

Gnani may allow one active request per account, so notes run one after another and every
caller sees a queue position. Results are kept in memory for JOB_TTL seconds, then dropped.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from kettu.domain.errors import ErrorCode, KettuError

log = logging.getLogger(__name__)

Status = Literal["queued", "processing", "done", "error"]
Work = Callable[["Job"], Awaitable[Any]]


@dataclass
class Job:
    id: str
    work: Work
    cleanup: Callable[[], None] | None = None
    status: Status = "queued"
    stage: str = "queued"
    result: Any = None
    error: KettuError | None = None
    created: float = field(default_factory=time.monotonic)
    finished: float | None = None
    done_event: asyncio.Event = field(default_factory=asyncio.Event)

    async def set_stage(self, stage: str) -> None:
        self.stage = stage


class JobQueue:
    def __init__(self, workers: int = 1, ttl_s: int = 600, max_waiting: int = 50):
        self.workers = workers
        self.ttl_s = ttl_s
        self.max_waiting = max_waiting
        self.jobs: dict[str, Job] = {}
        self.waiting: list[str] = []
        self._queue: asyncio.Queue[str] | None = None
        self._tasks: list[asyncio.Task] = []

    @property
    def queue(self) -> asyncio.Queue[str]:
        if self._queue is None:
            self._queue = asyncio.Queue()
        return self._queue

    def start(self) -> None:
        if self._tasks:
            return
        self._tasks = [asyncio.create_task(self._worker(i)) for i in range(self.workers)]
        self._tasks.append(asyncio.create_task(self._janitor()))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        for job in self.jobs.values():
            if job.cleanup:
                job.cleanup()
                job.cleanup = None
        self.jobs.clear()
        self.waiting.clear()
        self._queue = None

    def submit(self, work: Work, cleanup: Callable[[], None] | None = None) -> Job:
        if len(self.waiting) >= self.max_waiting:
            raise KettuError(ErrorCode.BUSY, "Kettu is very busy right now. Please try again in a few minutes.")
        job = Job(id=uuid.uuid4().hex, work=work, cleanup=cleanup)
        self.jobs[job.id] = job
        self.waiting.append(job.id)
        self.queue.put_nowait(job.id)
        return job

    def position(self, job: Job) -> int:
        """0 = being processed now; n = n notes ahead."""
        if job.status != "queued":
            return 0
        try:
            return self.waiting.index(job.id) + 1
        except ValueError:
            return 0

    def get(self, job_id: str) -> Job:
        job = self.jobs.get(job_id)
        if not job or (job.finished is not None and time.monotonic() - job.finished >= self.ttl_s):
            self.jobs.pop(job_id, None)
            raise KettuError(ErrorCode.NOT_FOUND)
        return job

    async def _worker(self, n: int) -> None:
        while True:
            job_id = await self.queue.get()
            job = self.jobs.get(job_id)
            if job_id in self.waiting:
                self.waiting.remove(job_id)
            if not job:
                continue
            job.status, job.stage = "processing", "preparing"
            try:
                job.result = await job.work(job)
                job.status, job.stage = "done", "done"
            except KettuError as exc:
                job.error, job.status, job.stage = exc, "error", "error"
            except Exception:  # never leak a stack trace to the user
                log.exception("job %s failed", job.id)
                job.error, job.status, job.stage = KettuError(ErrorCode.INTERNAL), "error", "error"
            finally:
                if job.cleanup:
                    job.cleanup()
                    job.cleanup = None
                job.finished = time.monotonic()
                job.done_event.set()

    async def _janitor(self) -> None:
        while True:
            await asyncio.sleep(30)
            now = time.monotonic()
            for jid in [j.id for j in self.jobs.values() if j.finished and now - j.finished > self.ttl_s]:
                self.jobs.pop(jid, None)

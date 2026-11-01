"""Wires services together once per process."""

from dataclasses import dataclass

from fastapi import Request

from kettu.config import Settings
from kettu.services.gnani import SpeechService, build_speech
from kettu.services.jobs import JobQueue
from kettu.services.limits import Limits
from kettu.services.llm import LLM, build_llm
from kettu.services.pipeline import Pipeline
from kettu.services.store import Store


@dataclass
class Context:
    settings: Settings
    speech: SpeechService
    llm: LLM
    pipeline: Pipeline
    jobs: JobQueue
    limits: Limits
    store: Store


def build_context(settings: Settings, speech: SpeechService | None = None, llm: LLM | None = None) -> Context:
    speech = speech or build_speech(settings)
    llm = llm or build_llm(settings)
    return Context(
        settings=settings,
        speech=speech,
        llm=llm,
        pipeline=Pipeline(settings, speech, llm),
        jobs=JobQueue(workers=1, ttl_s=settings.job_ttl_s),
        limits=Limits(settings),
        store=Store(settings),
    )


def get_ctx(request: Request) -> Context:
    return request.app.state.ctx

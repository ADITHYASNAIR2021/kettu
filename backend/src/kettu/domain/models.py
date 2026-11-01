"""Shapes passed between services and returned by the API."""

from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["listen", "orders"]
EntityType = Literal["time", "date", "amount", "quantity", "name", "place"]


class Entity(BaseModel):
    type: EntityType
    value: str = Field(description="value written in the reader's language")
    source_text: str = Field(description="exact words from the transcript")


class OrderItem(BaseModel):
    item: str
    quantity: str
    unit: str = ""


class Understanding(BaseModel):
    """What the LLM returns for a note."""

    translation: str | None = None
    gist: str | None = None
    entities: list[Entity] = []
    order_items: list[OrderItem] | None = None


class ReplyDraft(BaseModel):
    target_text: str
    back_translation: str


class NoteResult(BaseModel):
    detected_lang: str | None
    my_lang: str
    duration_s: float
    transcript: str
    translation: str | None
    gist: str | None
    entities: list[Entity] = []
    order_items: list[OrderItem] | None = None
    same_language: bool = False
    timings_ms: dict[str, int] = {}


class Transcript(BaseModel):
    text: str
    detected_lang: str | None
    duration_s: float
    seconds_billed: float


class Usage(BaseModel):
    stt_seconds: float = 0.0
    tts_chars: int = 0
    llm_tokens: int = 0

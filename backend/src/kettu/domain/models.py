"""Shapes passed between services and returned by the API."""

from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["listen", "orders"]
EntityType = Literal["time", "date", "amount", "quantity", "name", "place"]


class Entity(BaseModel):
    type: EntityType
    value: str = Field(description="value written in the reader's language")
    source_text: str = Field(description="exact words from the transcript")
    in_translation: str = Field("", description="exact words in the translation that carry this fact")


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
    # Facts (amounts, times, names...) heard in the note that the translation still leaves out after one repair.
    missing_facts: list[str] = []
    # False when no AI key is set: the server cannot translate, and the app says so instead of faking it.
    translation_live: bool = True
    timings_ms: dict[str, int] = {}


class TextTranslation(BaseModel):
    """A transcript put into one more language, on request."""

    to_lang: str
    translation: str
    entities: list[Entity] = []
    missing_facts: list[str] = []
    translation_live: bool = True


class Transcript(BaseModel):
    text: str
    detected_lang: str | None
    duration_s: float
    seconds_billed: float


class Usage(BaseModel):
    stt_seconds: float = 0.0
    tts_chars: int = 0
    llm_tokens: int = 0

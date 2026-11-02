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


class ActionDetail(BaseModel):
    value: str = Field(default="", max_length=300)
    source_text: str = Field(default="", max_length=1200)


class ActionItem(BaseModel):
    task: ActionDetail
    quantity: ActionDetail = Field(default_factory=ActionDetail)
    person: ActionDetail = Field(default_factory=ActionDetail)
    deadline: ActionDetail = Field(default_factory=ActionDetail)


class Understanding(BaseModel):
    """What the LLM returns for a note."""

    translation: str | None = None
    gist: str | None = None
    entities: list[Entity] = []
    order_items: list[OrderItem] | None = None
    action_items: list[ActionItem] = Field(default_factory=list, max_length=8)


class ReplyDraft(BaseModel):
    target_text: str = Field(min_length=1, max_length=900)
    back_translation: str = Field(min_length=1, max_length=2000)


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
    speech_live: bool = True
    timings_ms: dict[str, int] = {}
    action_items: list[ActionItem] = Field(default_factory=list, max_length=8)


class NoteReview(BaseModel):
    """A refreshed interpretation of user-supplied text; no new speech-recognition claim."""

    transcript: str
    detected_lang: str | None
    my_lang: str
    translation: str | None
    gist: str | None
    entities: list[Entity] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    order_items: list[OrderItem] | None = None
    action_items: list[ActionItem] = Field(default_factory=list, max_length=8)
    same_language: bool
    translation_live: bool
    actions_reviewed: bool = True


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

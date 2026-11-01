"""Errors the user can see. Each has a stable code and a plain sentence, never a stack trace."""

from enum import Enum


class ErrorCode(str, Enum):
    UNSUPPORTED_FILE = "unsupported_file"
    TOO_LONG = "too_long"
    TOO_BIG = "too_big"
    NO_SPEECH = "no_speech"
    MODEL_TIMEOUT = "model_timeout"
    BUSY = "busy"
    DAILY_LIMIT = "daily_limit"
    SERVICE_BUDGET = "service_budget"
    BAD_REQUEST = "bad_request"
    NOT_FOUND = "not_found"
    INTERNAL = "internal"


MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.UNSUPPORTED_FILE: "That file is not an audio note Kettu can read. Try a WhatsApp voice note, .mp3, .m4a or .wav.",
    ErrorCode.TOO_LONG: "This note is longer than 3 minutes. Kettu handles notes up to 3 minutes for now.",
    ErrorCode.TOO_BIG: "This file is bigger than 10 MB.",
    ErrorCode.NO_SPEECH: "Kettu could not hear any speech in this note.",
    ErrorCode.MODEL_TIMEOUT: "The speech service took too long. Please try again in a minute.",
    ErrorCode.BUSY: "Kettu is busy right now. You are in the queue.",
    ErrorCode.DAILY_LIMIT: "You have used today's free notes. Come back tomorrow.",
    ErrorCode.SERVICE_BUDGET: "Kettu has used today's budget. Join the waitlist and try again tomorrow.",
    ErrorCode.BAD_REQUEST: "Something in that request was not right.",
    ErrorCode.NOT_FOUND: "That result has expired. Results are kept for 10 minutes.",
    ErrorCode.INTERNAL: "Something went wrong on our side. Please try again.",
}

HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.UNSUPPORTED_FILE: 415,
    ErrorCode.TOO_LONG: 413,
    ErrorCode.TOO_BIG: 413,
    ErrorCode.NO_SPEECH: 422,
    ErrorCode.MODEL_TIMEOUT: 504,
    ErrorCode.BUSY: 503,
    ErrorCode.DAILY_LIMIT: 429,
    ErrorCode.SERVICE_BUDGET: 429,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.INTERNAL: 500,
}


class KettuError(Exception):
    def __init__(self, code: ErrorCode, message: str | None = None, retryable: bool = False):
        self.code = code
        self.message = message or MESSAGES[code]
        self.retryable = retryable
        super().__init__(f"{code.value}: {self.message}")

    @property
    def status(self) -> int:
        return HTTP_STATUS[self.code]

    def to_dict(self) -> dict:
        return {"code": self.code.value, "message": self.message}

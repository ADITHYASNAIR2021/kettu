"""Settings, all from environment variables (or backend/.env in development)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env.local (your keys, never committed) overrides .env; real environment variables override both.
    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), env_file_encoding="utf-8", extra="ignore")

    # Gnani (Prisma STT + Timbre TTS)
    gnani_api_key: str = ""
    gnani_base_url: str = "https://api.vachana.ai"
    gnani_concurrency: int = 1
    prisma_model: str = "prisma-v3.0"
    timbre_model: str = "timbre-v3.0"
    timbre_fallback_model: str = "timbre-v2.5"
    timbre_voice_female: str = "Shivani"
    timbre_voice_male: str = "Avinash"
    # "mock" runs the whole app without any paid API (UI work, tests, demos of the flow)
    speech_provider: Literal["gnani", "mock"] = "gnani"

    # LLM for translation, gist, orders, replies. Swap providers with one value.
    llm_provider: Literal["anthropic", "gemini", "mock"] = "anthropic"
    # Used when the primary has no key, or a call to it fails (outage, rate limit, refusal)
    llm_fallback_provider: Literal["anthropic", "gemini", "none"] = "gemini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    llm_timeout_s: float = 30.0

    # Supabase (counters + feedback only). Empty = in-memory only.
    supabase_url: str = ""
    supabase_service_key: str = ""

    # HTTP
    cors_origins: str = "http://localhost:3000"
    public_app_url: str = "http://localhost:3000"

    # Audio limits
    max_upload_mb: float = 10.0
    max_note_seconds: float = 180.0
    chunk_seconds: float = 28.0
    gist_min_seconds: float = 45.0
    max_reply_chars: int = 700  # about a minute spoken; Timbre takes up to 900 characters

    # Per device (or WhatsApp user) per IST day
    notes_per_day: int = 10
    replies_per_day: int = 5
    read_aloud_per_day: int = 10
    translate_per_day: int = 30
    # Whole service per IST day
    daily_stt_seconds_cap: float = 6000.0
    daily_tts_chars_cap: int = 60000

    job_ttl_s: int = 600
    work_dir: str = ""  # empty = system temp

    # WhatsApp Cloud API bot (optional; disabled when token is empty)
    wa_access_token: str = ""
    wa_phone_number_id: str = ""
    wa_app_secret: str = ""
    wa_verify_token: str = ""
    wa_graph_version: str = "v23.0"
    wa_allowed_numbers: str = ""  # comma-separated E.164 without "+"; empty = anyone who can reach the number
    wa_hash_salt: str = Field(default="change-me", description="salt for hashing phone numbers")

    # WhatsApp bot via Twilio (sandbox works without a Facebook account; off while the SID is empty)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"  # Twilio's sandbox number
    # "webhook": Twilio calls /twilio/webhook (legacy sandbox, paid numbers).
    # "poll": Kettu reads new messages from Twilio's API (the trial "Try out WhatsApp" number has no webhook).
    twilio_mode: Literal["webhook", "poll"] = "webhook"
    # "api": send replies through Twilio's REST API. "twiml": put them in the webhook's HTTP response,
    # for the trial "Try out WhatsApp" number, which rejects free-form API sends (error 21654).
    twilio_reply: Literal["api", "twiml"] = "api"
    twilio_poll_seconds: float = 2.0
    # Public HTTPS address of this API (tunnel or Cloud Run). Twilio fetches reply audio from it
    # and signs webhooks against it.
    public_api_url: str = ""

    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(self.wa_access_token and self.wa_phone_number_id)

    @property
    def twilio_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)

    @property
    def wa_allowed(self) -> set[str]:
        return {n.strip().lstrip("+") for n in self.wa_allowed_numbers.split(",") if n.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()

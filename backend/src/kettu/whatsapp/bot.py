"""Kettu as a WhatsApp contact. Same pipeline, queue and limits as the PWA.

Forward a voice note → text in your language (+ gist, chips, order list) → [Reply in X] →
send your answer (voice or text) → check the back-translation → [Make voice note] →
a real voice-note bubble in their language that you forward to the original chat.
"""

import hashlib
import logging
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from kettu.api.routes import discard, enqueue_note  # shared with the REST channel
from kettu.container import Context
from kettu.domain import languages
from kettu.domain.errors import ErrorCode, KettuError
from kettu.services import audio
from kettu.whatsapp import messages as m
from kettu.whatsapp.client import WhatsAppClient, WhatsAppError

log = logging.getLogger(__name__)

SESSION_TTL_S = 15 * 60

MIME_SUFFIX = {
    "audio/ogg": ".ogg", "audio/opus": ".opus", "audio/mpeg": ".mp3", "audio/mp4": ".m4a",
    "audio/aac": ".aac", "audio/amr": ".amr", "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/webm": ".webm",
}


@dataclass
class Session:
    state: str = "idle"  # idle | await_reply | preview
    to_lang: str | None = None
    target_text: str = ""
    orders_next: bool = False
    pending_media: tuple[str, str] | None = None  # (media_id, message_id) waiting for a language choice
    last_job: str | None = None
    touched: float = field(default_factory=time.monotonic)

    def expired(self) -> bool:
        return time.monotonic() - self.touched > SESSION_TTL_S

    def reset(self) -> None:
        self.state, self.to_lang, self.target_text = "idle", None, ""


def device_for(phone: str, salt: str) -> tuple[str, str]:
    """(hash key for prefs, uuid for limits/usage). The raw number is never stored."""
    digest = hashlib.sha256(f"{salt}:{phone}".encode()).hexdigest()
    return digest, str(uuid.uuid5(uuid.NAMESPACE_URL, f"kettu-wa:{digest}"))


class Bot:
    def __init__(self, ctx: Context, wa: WhatsAppClient):
        self.ctx = ctx
        self.wa = wa
        self.sessions: dict[str, Session] = {}
        self._active: set[str] = set()

    def sweep(self) -> None:
        for phone in [p for p, s in self.sessions.items() if s.expired() and p not in self._active]:
            self.sessions.pop(phone, None)
            menus = getattr(self.wa, "menus", {})
            menus.pop(phone, None)
            locks = getattr(self.wa, "_locks", {})
            locks.pop(phone, None)

    # ------------------------------------------------------------ plumbing

    def session(self, phone: str) -> Session:
        self.sweep()
        s = self.sessions.get(phone)
        if s is None or s.expired():
            s = Session()
            self.sessions[phone] = s
        s.touched = time.monotonic()
        return s

    async def prefs(self, key: str) -> dict:
        return await self.ctx.store.get_prefs(key) or {}

    async def handle(self, msg: dict, profile_name: str = "") -> None:
        phone = msg.get("from", "")
        allowed = self.ctx.settings.wa_allowed
        if allowed and phone not in allowed:
            log.info("ignoring message from a number not on WA_ALLOWED_NUMBERS")
            return
        if not phone or phone in self._active:
            return  # one conversation turn at a time; do not race language, reply and approval state
        self._active.add(phone)
        ui = "en"
        try:
            key, device = device_for(phone, self.ctx.settings.wa_hash_salt)
            prefs = await self.prefs(key)
            ui = m.ui_lang(prefs.get("my_lang"))
            await self._route(msg, phone, key, device, prefs, ui)
        except KettuError as exc:
            await self._safe_text(phone, m.t(ui, "error", message=exc.message))
        except WhatsAppError:
            log.warning("whatsapp send failed while handling a message")
        except Exception:
            log.exception("bot failure")
            await self._safe_text(phone, m.t(ui, "error", message=KettuError(ErrorCode.INTERNAL).message))
        finally:
            self._active.discard(phone)

    async def _safe_text(self, phone: str, text: str) -> None:
        try:
            await self.wa.send_text(phone, text)
        except Exception:
            log.warning("could not send error message")

    async def _route(self, msg: dict, phone: str, key: str, device: str, prefs: dict, ui: str) -> None:
        kind = msg.get("type")
        mid = msg.get("id", "")
        sess = self.session(phone)
        await self.wa.mark_read(mid)

        if kind in ("audio", "voice") or (kind == "document" and str(msg.get("document", {}).get("mime_type", "")).startswith("audio/")):
            media = msg.get("audio") or msg.get("voice") or msg.get("document") or {}
            if not prefs.get("my_lang"):
                sess.pending_media = (media.get("id", ""), mid)
                await self.ask_language(phone, welcome=True)
                return
            if sess.state == "await_reply":
                await self.reply_from_audio(phone, device, prefs, ui, sess, media)
            else:
                await self.understand(phone, device, prefs, ui, sess, media, mid)
            return

        if kind == "interactive":
            inter = msg.get("interactive", {})
            picked = inter.get("button_reply") or inter.get("list_reply") or {}
            await self.on_choice(phone, key, device, prefs, ui, sess, picked.get("id", ""))
            return

        if kind == "button":  # quick-reply buttons from templates
            await self.on_choice(phone, key, device, prefs, ui, sess, msg.get("button", {}).get("payload", ""))
            return

        if kind == "text":
            await self.on_text(phone, key, device, prefs, ui, sess, msg.get("text", {}).get("body", ""))
            return

        await self.wa.send_text(phone, m.t(ui, "not_audio"))

    # ------------------------------------------------------------ language and settings

    async def ask_language(self, phone: str, welcome: bool = False) -> None:
        if welcome:
            await self.wa.send_text(phone, m.t("en", "welcome"))
        rows = [(f"lang:{l.code}", l.native, l.name) for l in languages.LANGUAGES.values()]
        await self.wa.send_list(phone, m.t("en", "pick_body"), m.t("en", "pick_button"), rows, m.t("en", "pick_section"))

    async def on_text(self, phone, key, device, prefs, ui, sess: Session, body: str) -> None:
        text = body.strip()
        cmd = text.lower().strip("!/. ")
        if not prefs.get("my_lang"):
            await self.ask_language(phone, welcome=True)
            return
        if cmd in {"hi", "hello", "help", "start", "menu", "?", "hai", "namaste", "namaskaram"}:
            left = self.ctx.limits.remaining(device)
            await self.wa.send_text(phone, m.t(ui, "help", lang=m.lang_label(prefs["my_lang"], ui),
                                                notes=left["notes_left"], replies=left["replies_left"]))
            return
        if cmd in {"language", "lang", "bhasha", "ഭാഷ", "भाषा", "ভাষা"}:
            await self.ask_language(phone)
            return
        if cmd in {"orders", "order", "ഓർഡർ", "ऑर्डर", "অর্ডার"}:
            sess.orders_next = True
            await self.wa.send_text(phone, m.t(ui, "orders_on"))
            return
        if cmd in {"voice", "ശബ്ദം", "आवाज़", "কণ্ঠ"}:
            await self.wa.send_buttons(phone, m.t(ui, "voice_q"),
                                       [("voice:female", m.t(ui, "female")), ("voice:male", m.t(ui, "male"))])
            return
        if cmd in {"cancel", "stop", "റദ്ദാക്കുക", "रद्द", "বাতিল"}:
            sess.reset()
            await self.wa.send_text(phone, m.t(ui, "cancelled"))
            return
        if sess.state == "await_reply" and sess.to_lang:
            await self.preview(phone, device, prefs, ui, sess, text=text)
            return
        await self.wa.send_text(phone, m.t(ui, "not_audio"))

    async def on_choice(self, phone, key, device, prefs, ui, sess: Session, choice: str) -> None:
        if choice.startswith("lang:"):
            code = choice.split(":", 1)[1]
            if not languages.is_supported(code):
                return
            prefs = {**prefs, "my_lang": code, "voice": prefs.get("voice", "female")}
            await self.ctx.store.put_prefs(key, {"my_lang": code, "voice": prefs["voice"]})
            ui = m.ui_lang(code)
            await self.wa.send_text(phone, m.t(ui, "lang_set", lang=m.lang_label(code, ui)))
            if sess.pending_media:
                media_id, mid = sess.pending_media
                sess.pending_media = None
                await self.understand(phone, device, prefs, ui, sess, {"id": media_id}, mid)
            return
        if choice.startswith("voice:"):
            voice = "male" if choice == "voice:male" else "female"
            await self.ctx.store.put_prefs(key, {"my_lang": prefs.get("my_lang"), "voice": voice})
            await self.wa.send_text(phone, m.t(ui, "voice_set", voice=m.t(ui, voice)))
            return
        if choice.startswith("reply:"):
            code = choice.split(":", 1)[1]
            if not languages.is_supported(code):
                return
            sess.state, sess.to_lang, sess.target_text = "await_reply", code, ""
            await self.wa.send_text(phone, m.t(ui, "prompt_reply", mine=m.lang_label(prefs.get("my_lang"), ui),
                                               theirs=m.lang_label(code, ui)))
            return
        if choice == "speak":
            await self.speak(phone, device, prefs, ui, sess)
            return
        if choice == "retry":
            if not sess.to_lang:
                await self.wa.send_text(phone, m.t(ui, "expired"))
                return
            sess.state = "await_reply"
            await self.wa.send_text(phone, m.t(ui, "prompt_reply", mine=m.lang_label(prefs.get("my_lang"), ui),
                                               theirs=m.lang_label(sess.to_lang, ui)))
            return
        if choice == "cancel":
            sess.reset()
            await self.wa.send_text(phone, m.t(ui, "cancelled"))
            return
        if choice.startswith("fb:"):
            _, rating, kind = (choice.split(":") + ["", ""])[:3]
            if rating == "up":
                await self.ctx.store.add_feedback({"device_id": device, "kind": kind or "note", "rating": 1,
                                                   "reason": None, "lang": prefs.get("my_lang")})
                await self.wa.send_text(phone, m.t(ui, "thanks_up"))
            else:
                await self.wa.send_buttons(phone, m.t(ui, "reason_q"), [
                    (f"fbr:wrong_language:{kind}", m.t(ui, "r_lang")),
                    (f"fbr:wrong_words:{kind}", m.t(ui, "r_words")),
                    (f"fbr:bad_translation:{kind}", m.t(ui, "r_trans")),
                ])
            return
        if choice.startswith("fbr:"):
            _, reason, kind = (choice.split(":") + ["", ""])[:3]
            await self.ctx.store.add_feedback({"device_id": device, "kind": kind or "note", "rating": -1,
                                               "reason": reason, "lang": prefs.get("my_lang")})
            await self.wa.send_text(phone, m.t(ui, "thanks_down"))
            return

    # ------------------------------------------------------------ the three use cases

    async def _download(self, media: dict) -> Path:
        data, mime = await self.wa.download_media(media.get("id", ""))
        if len(data) > self.ctx.settings.max_upload_mb * 1024 * 1024:
            raise KettuError(ErrorCode.TOO_BIG)
        suffix = MIME_SUFFIX.get(mime.split(";")[0].strip(), ".ogg")
        folder = Path(tempfile.mkdtemp(prefix="kettu_wa_"))
        path = folder / f"note{suffix}"
        try:
            path.write_bytes(data)
        except BaseException:
            discard(path)
            raise
        return path

    async def understand(self, phone, device, prefs, ui, sess: Session, media: dict, mid: str) -> None:
        ctx = self.ctx
        ctx.limits.check_note(device)
        try:
            path = await self._download(media)
        except WhatsAppError:
            raise KettuError(ErrorCode.UNSUPPORTED_FILE, "Could not download that voice note. Please forward it again.")
        mode = "orders" if sess.orders_next else "listen"
        sess.orders_next = False
        try:
            await audio.check_upload(path, ctx.settings.max_note_seconds, ctx.settings.max_upload_mb)
            job = enqueue_note(ctx, path, device, prefs["my_lang"], mode, [], [])
        except BaseException:
            discard(path)
            raise
        ahead = ctx.jobs.position(job) - 1
        await self.wa.send_text(phone, m.t(ui, "queued", n=ahead) if ahead > 0 else m.t(ui, "listening"))
        await job.done_event.wait()
        if job.status != "done":
            raise job.error or KettuError(ErrorCode.INTERNAL)

        result = job.result
        sess.last_job = job.id
        await self.wa.send_text(phone, m.format_note(result, ui), reply_to=mid)
        buttons: list[tuple[str, str]] = []
        if result.detected_lang and not result.same_language:
            buttons.append((f"reply:{result.detected_lang}",
                            m.t(ui, "reply_btn", lang=m.lang_label(result.detected_lang, ui))))
        buttons += [("fb:up:note", "👍"), ("fb:down:note", "👎")]
        body = m.t(ui, "reply_q", lang=m.lang_label(result.detected_lang, ui)) if len(buttons) == 3 else "👍 / 👎"
        await self.wa.send_buttons(phone, body, buttons)

    async def reply_from_audio(self, phone, device, prefs, ui, sess: Session, media: dict) -> None:
        try:
            path = await self._download(media)
        except WhatsAppError:
            raise KettuError(ErrorCode.UNSUPPORTED_FILE, "Could not download that voice note. Please send it again.")
        await self.preview(phone, device, prefs, ui, sess, audio_path=path)

    async def preview(self, phone, device, prefs, ui, sess: Session, text: str | None = None,
                      audio_path: Path | None = None) -> None:
        ctx = self.ctx
        if not sess.to_lang:
            if audio_path:
                discard(audio_path)
            await self.wa.send_text(phone, m.t(ui, "no_reply_target"))
            return
        try:
            if audio_path:
                await audio.check_upload(audio_path, 61, ctx.settings.max_upload_mb)
            with ctx.limits.reserve(device, "reply_preview", stt_seconds=61 if audio_path else 0):
                await self.wa.send_text(phone, m.t(ui, "drafting"))
                draft, _, usage = await ctx.pipeline.preview_reply(prefs["my_lang"], sess.to_lang, text=text,
                                                                   audio_path=audio_path)
                ctx.limits.record(device, "reply_preview", stt_seconds=usage.stt_seconds)
        finally:
            if audio_path:
                discard(audio_path)
        ctx.store.log_usage(device_id=device, kind="reply_preview", audio_seconds=round(usage.stt_seconds, 2),
                            llm_tokens=usage.llm_tokens, my_lang=prefs["my_lang"], detected_lang=sess.to_lang,
                            status="ok")
        sess.state, sess.target_text = "preview", draft.target_text
        mine, theirs = m.lang_label(prefs["my_lang"], ui), m.lang_label(sess.to_lang, ui)
        await self.wa.send_text(phone, m.t(ui, "preview", theirs=theirs, mine=mine,
                                           target=draft.target_text, back=draft.back_translation))
        await self.wa.send_buttons(phone, m.t(ui, "preview_q"), [
            ("speak", m.t(ui, "btn_speak")), ("retry", m.t(ui, "btn_retry")), ("cancel", m.t(ui, "btn_cancel")),
        ])

    async def speak(self, phone, device, prefs, ui, sess: Session) -> None:
        ctx = self.ctx
        if sess.state != "preview" or not sess.target_text or not sess.to_lang:
            await self.wa.send_text(phone, m.t(ui, "expired"))
            return
        with ctx.limits.reserve(device, "reply_speak", tts_chars=len(sess.target_text)):
            await self.wa.send_text(phone, m.t(ui, "speaking"))
            ogg, usage = await ctx.pipeline.speak_reply(sess.target_text, sess.to_lang, prefs.get("voice", "female"), "ogg")
            ctx.limits.record(device, "reply_speak", tts_chars=usage.tts_chars)
        ctx.store.log_usage(device_id=device, kind="reply_speak", tts_chars=usage.tts_chars,
                            detected_lang=sess.to_lang, status="ok")
        await self.wa.send_voice(phone, ogg)
        await self.wa.send_text(phone, m.t(ui, "forward_hint"))
        sess.reset()

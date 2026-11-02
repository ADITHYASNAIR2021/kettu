"""FastAPI app. Run: uvicorn kettu.main:app --app-dir src"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from kettu.api.routes import router as api_router
from kettu.api.guard import RequestGuard
from kettu.config import Settings, get_settings
from kettu.container import Context, build_context
from kettu.domain.errors import ErrorCode, KettuError
from kettu.services.limits import ist_midnight
from kettu.whatsapp.twilio import router as twilio_router
from kettu.whatsapp.webhook import router as wa_router

log = logging.getLogger("kettu")


def create_app(settings: Settings | None = None, ctx: Context | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request drowns everything else

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        context = ctx or build_context(settings)
        if settings.require_live_models and (not getattr(context.speech, "live", True) or not context.llm.live):
            raise RuntimeError("Live speech and translation providers are required. Check the model API keys.")
        app.state.ctx = context
        context.limits.restore(await context.store.today_usage(ist_midnight()))
        context.jobs.start()
        if settings.whatsapp_enabled:
            from kettu.whatsapp.bot import Bot
            from kettu.whatsapp.client import WhatsAppClient

            app.state.bot = Bot(context, WhatsAppClient(settings))
            log.info("WhatsApp bot enabled on phone number id %s", settings.wa_phone_number_id)
        if settings.twilio_enabled:
            from kettu.whatsapp.bot import Bot
            from kettu.whatsapp.twilio import MediaStore, TwilioClient, TwilioPoller

            app.state.media = MediaStore()
            app.state.twilio_bot = Bot(context, TwilioClient(settings, app.state.media))
            if not settings.public_api_url:
                log.warning("Twilio enabled but PUBLIC_API_URL is empty: webhooks and voice replies will fail")
            if settings.twilio_mode == "poll":
                poller = TwilioPoller(app.state.twilio_bot, settings)
                app.state.twilio_poller = asyncio.create_task(poller.run())
            log.info("WhatsApp bot enabled via Twilio (%s) from %s", settings.twilio_mode, settings.twilio_whatsapp_from)
        log.info("kettu ready: speech=%s llm=%s supabase=%s",
                 type(context.speech).__name__, type(context.llm).__name__, context.store.enabled)

        async def sweep_private_state():
            while True:
                await asyncio.sleep(30)
                for name in ("bot", "twilio_bot"):
                    bot = getattr(app.state, name, None)
                    if bot:
                        bot.sweep()
                media = getattr(app.state, "media", None)
                if media:
                    media._sweep()

        sweeper = asyncio.create_task(sweep_private_state())
        try:
            yield
        finally:
            tasks = [sweeper]
            poll_task = getattr(app.state, "twilio_poller", None)
            if poll_task:
                tasks.append(poll_task)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await context.jobs.stop()
            await context.store.close()

    app = FastAPI(title="Kettu API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestGuard, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        max_age=600,
    )

    @app.exception_handler(KettuError)
    async def kettu_error(_: Request, exc: KettuError):
        return JSONResponse({"error": exc.to_dict()}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse({"error": KettuError(ErrorCode.BAD_REQUEST).to_dict()}, status_code=400)

    app.include_router(api_router)
    app.include_router(wa_router)
    app.include_router(twilio_router)
    return app


app = create_app()

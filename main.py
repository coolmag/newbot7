import logging
import asyncio
from contextlib import asynccontextmanager
import time
from datetime import timedelta

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update
from telegram.ext import Application

from dependencies import (
    get_settings_dep,
    get_cache_service_dep,
    get_downloader_dep,
    get_radio_manager_dep,
    get_genre_voting_service_dep,
)
from config import Settings
from logging_setup import setup_logging
from radio import RadioManager
from youtube import YouTubeDownloader
from handlers import setup_handlers
from cache_service import CacheService

logger = logging.getLogger(__name__)
_start_time = time.time()

def get_uptime():
    uptime_seconds = time.time() - _start_time
    return str(timedelta(seconds=int(uptime_seconds)))

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    setup_logging()
    logger.info("⚡ Application starting up...")
    
    settings: Settings = get_settings_dep()
    cache: CacheService = get_cache_service_dep()
    downloader: YouTubeDownloader = get_downloader_dep()
    radio_manager: RadioManager = get_radio_manager_dep()
    voting_service: GenreVotingService = get_genre_voting_service_dep()

    settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    await cache.initialize()

    tg_app = Application.builder().token(settings.BOT_TOKEN).build()
    app.state.tg_app = tg_app
    
    # Pass all required dependencies to handlers
    setup_handlers(
        app=tg_app,
        radio=radio_manager,
        settings=settings,
        downloader=downloader,
        voting_service=voting_service,
        cache_service=cache
    )
    
    await tg_app.initialize()
    await tg_app.bot.set_my_commands([
        ("start", "🚀 Меню"), ("play", "🎵 Найти трек"),
        ("radio", "📻 Радио по жанру"), ("stop", "⏹️ Стоп"), ("skip", "⏭️ Пропустить")
    ])
    await tg_app.start()
    
    webhook_url = f"{settings.WEBHOOK_URL.rstrip('/')}/telegram"
    await tg_app.bot.set_webhook(url=webhook_url)
    
    logger.info(f"✅ Bot started. Webhook: {webhook_url}")
    yield
    
    # --- Shutdown ---
    logger.info("🛑 Application shutting down...")
    await radio_manager.stop_all()
    await tg_app.stop()
    await tg_app.shutdown()
    await cache.close()
    logger.info("✅ Application shutdown complete.")

app = FastAPI(lifespan=lifespan)

@app.get("/api/health")
async def health():
    return {"status": "ok", "uptime": get_uptime()}

@app.post("/telegram")
async def telegram_webhook(request: Request):
    tg_app = request.app.state.tg_app
    try:
        update = Update.de_json(await request.json(), tg_app.bot)
        await tg_app.process_update(update)
    except Exception as e:
        logger.error("Error processing webhook: %s", e, exc_info=True)
    return {"ok": True}

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/webapp")

app.mount("/webapp", StaticFiles(directory="webapp", html=True), name="webapp")
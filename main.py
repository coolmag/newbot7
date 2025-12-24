import logging
import asyncio
import httpx
import time
from contextlib import asynccontextmanager
from datetime import datetime
import os

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telegram import Update
from telegram.ext import Application

from dependencies import (
    get_settings_dep,
    get_cache_service_dep,
    get_downloader_dep,
    get_radio_manager_dep,
    get_genre_voting_service_dep
)
from auth import get_validated_user, WebAppUser
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
    return str(datetime.timedelta(seconds=int(uptime_seconds)))

async def keep_alive_task():
    health_url = "http://127.0.0.1:8080/api/health"
    await asyncio.sleep(20) # Initial delay
    while True:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.get(health_url)
        except Exception:
            pass # Errors are not critical for a keep-alive
        await asyncio.sleep(60) # Ping every minute

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

    # Create directories
    settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    settings.TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    await cache.initialize()

    # Setup Telegram
    tg_app = Application.builder().token(settings.BOT_TOKEN).build()
    app.state.tg_app = tg_app
    
    setup_handlers(app=tg_app, radio=radio_manager, settings=settings, downloader=downloader, voting_service=voting_service, cache_service=cache)
    
    await tg_app.initialize()
    await tg_app.bot.set_my_commands([
        ("start", "🚀 Меню"), ("play", "🎵 Найти трек"),
        ("radio", "📻 Радио по жанру"), ("stop", "⏹️ Стоп"), ("skip", "⏭️ Пропустить")
    ])
    await tg_app.start()
    
    webhook_url = f"{settings.WEBHOOK_URL.rstrip('/')}/telegram"
    await tg_app.bot.set_webhook(url=webhook_url)
    
    logger.info(f"✅ Bot started. Webhook: {webhook_url}")
    
    # --- App is running ---
    yield
    
    # --- Shutdown ---
    logger.info("🛑 Application shutting down...")
    await radio_manager.stop_all()
    await tg_app.stop()
    await tg_app.shutdown()
    await cache.close()
    logger.info("✅ Application shutdown complete.")

app = FastAPI(lifespan=lifespan)

# --- API Routes ---
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

# --- Static files ---
@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/webapp")

app.mount("/webapp", StaticFiles(directory="webapp", html=True), name="webapp")

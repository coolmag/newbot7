import logging
import asyncio
from contextlib import asynccontextmanager
import time
from datetime import timedelta

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from telegram import Update
from telegram.ext import Application

from config import get_settings, Settings
from logging_setup import setup_logging
from radio import RadioManager
from youtube import YouTubeDownloader
from handlers import setup_handlers
from cache_service import CacheService

logger = logging.getLogger(__name__)
_start_time = time.time()

def get_uptime():
    return str(timedelta(seconds=int(time.time() - _start_time)))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения."""
    setup_logging()
    logger.info("⚡ Application starting up...")
    
    # 1. Загружаем настройки
    settings: Settings = get_settings()
    
    # 2. Создаём директории
    settings.DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    settings.TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    
    # 3. Инициализируем кэш
    cache = CacheService(settings.CACHE_DB_PATH)
    await cache.initialize()
    
    # 4. Создаём загрузчик
    downloader = YouTubeDownloader(settings, cache)
    
    # 5. Создаём Telegram Application (с Bot'ом внутри)
    tg_app = Application.builder().token(settings.BOT_TOKEN).build()
    
    # 6. Создаём RadioManager с Bot'ом из Application (ВАЖНО!)
    radio_manager = RadioManager(
        bot=tg_app.bot,  # Используем тот же Bot!
        settings=settings,
        downloader=downloader
    )
    
    # 7. Регистрируем хендлеры
    setup_handlers(
        app=tg_app,
        radio=radio_manager,
        settings=settings,
        downloader=downloader
    )
    
    # 8. Инициализируем и запускаем бота
    await tg_app.initialize()
    await tg_app.bot.set_my_commands([
        ("start", "🚀 Открыть меню"),
        ("play", "🎲 Случайное радио"),
        ("radio", "📻 Выбрать жанр"),
        ("stop", "⏹️ Остановить"),
        ("skip", "⏭️ Пропустить трек")
    ])
    await tg_app.start()
    
    # 9. Устанавливаем вебхук
    webhook_url = settings.WEBHOOK_URL
    await tg_app.bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Bot started. Webhook: {webhook_url}")
    
    # Сохраняем в state
    app.state.tg_app = tg_app
    app.state.radio_manager = radio_manager
    app.state.cache = cache
    
    yield
    
    # --- Shutdown ---
    logger.info("🛑 Shutting down...")
    await radio_manager.stop_all()
    await tg_app.stop()
    await tg_app.shutdown()
    await cache.close()
    logger.info("✅ Shutdown complete.")

app = FastAPI(lifespan=lifespan)

@app.get("/api/health")
async def health():
    return {"status": "ok", "uptime": get_uptime()}

@app.post("/telegram")
async def telegram_webhook(request: Request):
    tg_app = request.app.state.tg_app
    try:
        data = await request.json()
        update = Update.de_json(data, tg_app.bot)
        await tg_app.process_update(update)
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
    return {"ok": True}

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/webapp")

# Статика (если есть папка webapp)
try:
    app.mount("/webapp", StaticFiles(directory="webapp", html=True), name="webapp")
except Exception:
    pass  # Папки нет — пропускаем
from functools import lru_cache
from typing import TYPE_CHECKING

from telegram.ext import Application
from config import get_settings, Settings
from cache_service import CacheService
from youtube import YouTubeDownloader
from radio import RadioManager

if TYPE_CHECKING:
    from telegram import Bot

@lru_cache()
def get_settings_dep() -> Settings:
    """Dependency to get the application settings."""
    return get_settings()

@lru_cache()
def get_cache_service_dep() -> CacheService:
    """Dependency to get the CacheService."""
    return CacheService(settings=get_settings_dep())

@lru_cache()
def get_downloader_dep() -> YouTubeDownloader:
    """Dependency to get the YouTubeDownloader."""
    return YouTubeDownloader(
        settings=get_settings_dep(),
        cache_service=get_cache_service_dep()
    )

@lru_cache()
def get_telegram_bot_dep() -> "Bot":
    """Dependency to get the Telegram Bot instance."""
    return Application.builder().token(get_settings_dep().BOT_TOKEN).build().bot

@lru_cache()
def get_radio_manager_dep() -> RadioManager:
    """Dependency to get the RadioManager."""
    return RadioManager(
        bot=get_telegram_bot_dep(),
        settings=get_settings_dep(),
        downloader=get_downloader_dep(),
        cache=get_cache_service_dep()
    )

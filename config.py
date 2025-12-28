from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

# ===========================
# ГЛОБАЛЬНЫЙ КАТАЛОГ ЖАНРОВ
# ===========================
MUSIC_CATALOG = {
    "🔥 Топ-чарты": {
        "Global Top 50": "top 50 global official playlist -mix",
        "Viral Hits": "tiktok viral hits -playlist -mix",
    },
    "🎶 По настроению": {
        "🏃‍♂️ Тренировка": "gym workout music motivational -mix -playlist",
        "☕️ Чилаут": "chill lofi hip hop beats to relax -mix -playlist",
        "🎉 Вечеринка": "party hits pop dance -mix -playlist",
        "❤️ Романтика": "romantic love songs -mix -playlist",
        "😢 Грусть": "sad songs for broken hearts -mix -playlist",
    },
    "📅 По десятилетиям": {
        "🕺 80-е": "80s greatest hits -mix -playlist",
        "🎸 90-е": "90s greatest hits -mix -playlist",
        "✨ 00-е": "2000s greatest hits -mix -playlist",
        "📱 10-е": "2010s greatest hits -mix -playlist",
    },
    "🎸 Рок": {
        "Classic Rock": {
            "🦰 70-е": "70s classic rock anthems",
            "👨‍🎤 80-е": "80s classic rock anthems",
        },
        "Alternative & Indie": {
            "🤘 Все подряд": "90s 2000s alternative rock indie -mix -playlist",
            "🎸 90-е": "90s alternative rock indie",
            "✨ 00-е": "2000s alternative rock indie",
        },
        "Hard Rock & Metal": "hard rock heavy metal -mix -playlist",
        "Punk Rock": "punk rock classics ramones misfits -mix -playlist",
    },
    "🎤 Хип-хоп": {
        "Old-School 80s & 90s": "old school hip hop 80s 90s -mix -playlist",
        "Golden Age": "90s boom bap hip hop wu-tang nas -mix -playlist",
        "Modern Trap": "trap music -mix -playlist",
        "R&B Classics": "90s 2000s r&b classics -mix -playlist",
    },
    "🎧 Электроника": {
        "House": "deep house -mix -playlist",
        "Techno": "techno club -mix -playlist",
        "Trance": "vocal trance anthems -mix -playlist",
        "Drum & Bass": "liquid drum & bass -mix -playlist",
    },
    "✨ Поп": {
        "80s Synth-Pop": "synth-pop 80s hits -mix -playlist",
        "90s Pop": {
             "💖 Все подряд": "90s pop hits",
             "🇷🇺 Русская": "русская поп-музыка 90-х",
             "🌍 Зарубежная": "90s foreign pop hits",
        },
        "00s Pop": {
             "🔥 Все подряд": "2000s pop hits",
             "🇷🇺 Русская": "русская поп-музыка 2000-х",
             "🌍 Зарубежная": "foreign pop hits 2000s",
        },
        "Modern Pop": "today's top pop hits -mix -playlist",
    },
}

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    
    # --- Mandatory Settings (Переменные окружения) ---
    BOT_TOKEN: str 
    WEBHOOK_URL: str 
    BASE_URL: str = ""
    ADMIN_IDS: str = ""
    COOKIES_CONTENT: str = ""
    PROXY_URL: Optional[str] = None
    BASE_DIR: Path = Path(__file__).resolve().parent
    DOWNLOADS_DIR: Path = BASE_DIR / "downloads"
    TEMP_AUDIO_DIR: Path = BASE_DIR / "temp_audio"
    CACHE_DB_PATH: Path = BASE_DIR / "cache.db"
    COOKIES_FILE: Path = BASE_DIR / "cookies.txt"
    LOG_LEVEL: str = "INFO"
    MAX_FILE_SIZE_MB: int = 49
    RADIO_MIN_DURATION_S: int = 60    
    RADIO_MAX_DURATION_S: int = 900   
    GENRE_SEARCH_MIN_DURATION_S: int = 120   
    GENRE_SEARCH_MAX_DURATION_S: int = 600 
    ADMIN_ID_LIST: List[int] = []

    @field_validator("ADMIN_ID_LIST", mode="before")
    @classmethod
    def _assemble_admin_ids(cls, v, info) -> List[int]:
        admin_ids_str = info.data.get("ADMIN_IDS", "")
        if not admin_ids_str: return []
        try:
            return [int(i.strip()) for i in admin_ids_str.split(",") if i.strip()]
        except ValueError as e:
            print(f"⚠️ Ошибка парсинга ADMIN_IDS: {e}")
            return []

@lru_cache()
def get_settings() -> Settings:
    return Settings()

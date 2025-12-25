from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache
import json

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    
    # --- Mandatory Settings ---
    BOT_TOKEN: str
    WEBHOOK_URL: str
    BASE_URL: str

    # --- Optional Settings ---
    ADMIN_IDS: str = ""
    COOKIES_CONTENT: str = ""
    PROXY_URL: Optional[str] = None
    
    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent
    DOWNLOADS_DIR: Path = BASE_DIR / "downloads"
    TEMP_AUDIO_DIR: Path = BASE_DIR / "temp_audio"
    CACHE_DB_PATH: Path = BASE_DIR / "cache.db"
    COOKIES_FILE: Path = BASE_DIR / "cookies.txt"
    
    # --- App Logic ---
    LOG_LEVEL: str = "INFO"
    MAX_FILE_SIZE_MB: int = 49  # Telegram limit is 50MB
    
    # --- Radio & Search ---
    RADIO_MIN_DURATION_S: int = 60    # 1 minute, for single tracks
    RADIO_MAX_DURATION_S: int = 900   # 15 minutes, for single tracks
    GENRE_SEARCH_MIN_DURATION_S: int = 300   # 5 minutes, for genre playlists/mixes
    GENRE_SEARCH_MAX_DURATION_S: int = 18000 # 5 hours, for genre playlists/mixes
    
    # --- Fields populated by validators ---
    ADMIN_ID_LIST: List[int] = []
    GENRE_DATA: Dict[str, Any] = {}

    @field_validator("ADMIN_ID_LIST", mode="before")
    @classmethod
    def _assemble_admin_ids(cls, v, info) -> List[int]:
        admin_ids_str = info.data.get("ADMIN_IDS", "")
        if not admin_ids_str: return []
        try:
            return [int(i.strip()) for i in admin_ids_str.split(",") if i.strip()]
        except ValueError as e:
            raise ValueError(f"Invalid ADMIN_IDS format: {e}") from e

    @model_validator(mode='after')
    def _load_genre_data(self) -> "Settings":
        genres_path = self.BASE_DIR / "genres.json"
        if not genres_path.is_file():
            raise FileNotFoundError(f"Critical file not found: {genres_path}")
        try:
            with open(genres_path, "r", encoding="utf-8") as f:
                self.GENRE_DATA = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error decoding JSON from {genres_path}: {e}") from e
        return self



@lru_cache()
def get_settings() -> Settings:
    return Settings()

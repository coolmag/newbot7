import aiosqlite
import asyncio
import logging
from typing import Optional, Any
from pathlib import Path
from config import Settings
from models import DownloadResult, Source

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, settings: Settings):
        self._db_path = settings.CACHE_DB_PATH
        self._is_initialized = False
        self._init_lock = asyncio.Lock()

    async def initialize(self):
        async with self._init_lock:
            if not self._is_initialized:
                try:
                    async with aiosqlite.connect(self._db_path) as db:
                        await db.execute("""
                            CREATE TABLE IF NOT EXISTS download_cache (
                                key TEXT PRIMARY KEY,
                                source TEXT NOT NULL,
                                file_path TEXT NOT NULL,
                                title TEXT,
                                artist TEXT,
                                duration INTEGER,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        await db.execute("CREATE INDEX IF NOT EXISTS idx_source ON download_cache(source)")
                        await db.commit()
                    self._is_initialized = True
                    logger.info("Cache database initialized.")
                except Exception as e:
                    logger.error(f"Failed to initialize cache database: {e}", exc_info=True)

    async def get(self, key: str) -> Optional[DownloadResult]:
        if not self._is_initialized: await self.initialize()
        try:
            async with aiosqlite.connect(self._db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT * FROM download_cache WHERE key = ?", (key,))
                row = await cursor.fetchone()
                if row:
                    file_path = Path(row["file_path"])
                    if file_path.exists():
                        from models import TrackInfo
                        track_info = TrackInfo(
                            title=row["title"], artist=row["artist"], duration=row["duration"],
                            source=Source(row["source"]), identifier=key.split(":")[-1]
                        )
                        return DownloadResult(success=True, file_path=file_path, track_info=track_info)
                    else:
                        # File missing, delete stale cache entry
                        await db.execute("DELETE FROM download_cache WHERE key = ?", (key,))
                        await db.commit()
        except Exception as e:
            logger.error(f"Cache GET error for key '{key}': {e}", exc_info=True)
        return None

    async def set(self, key: str, result: DownloadResult):
        if not self._is_initialized or not result.success or not result.file_path:
            return
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO download_cache (key, source, file_path, title, artist, duration)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key, result.track_info.source, str(result.file_path),
                        result.track_info.title, result.track_info.artist, result.track_info.duration
                    )
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Cache SET error for key '{key}': {e}", exc_info=True)

    async def close(self):
        # In aiosqlite, connections are pooled and closed automatically.
        # This method is for interface consistency.
        pass

    async def blacklist_track_id(self, video_id: str):
        # This method could be expanded to add to a blacklist table if needed
        logger.warning(f"Blacklisting track {video_id} (not implemented, deleting from cache).")
        await self.delete(f"yt:{video_id}")

    async def delete(self, key: str):
        if not self._is_initialized: return
        try:
            async with aiosqlite.connect(self._db_path) as db:
                await db.execute("DELETE FROM download_cache WHERE key = ?", (key,))
                await db.commit()
        except Exception as e:
            logger.error(f"Cache DELETE error for key '{key}': {e}", exc_info=True)


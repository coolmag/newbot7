import asyncio
import logging
import pickle
from pathlib import Path
from typing import Optional, Any
import aiosqlite

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Инициализация базы данных"""
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.commit()
        logger.info(f"Cache initialized at {self._db_path}")

    async def close(self):
        """Закрытие соединения"""
        if self._db:
            await self._db.close()
            self._db = None

    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        if not self._db:
            return None
        
        try:
            async with self._lock:
                cursor = await self._db.execute(
                    "SELECT value FROM cache WHERE key = ?", (key,)
                )
                row = await cursor.fetchone()
                if row:
                    return pickle.loads(row[0])
                return None
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Сохранение значения в кэш"""
        if not self._db:
            return False
        
        try:
            async with self._lock:
                serialized = pickle.dumps(value)
                await self._db.execute(
                    "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                    (key, serialized)
                )
                await self._db.commit()
                return True
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Удаление значения из кэша"""
        if not self._db:
            return False
        
        try:
            async with self._lock:
                await self._db.execute("DELETE FROM cache WHERE key = ?", (key,))
                await self._db.commit()
                return True
        except Exception as e:
            logger.error(f"Cache delete error for {key}: {e}")
            return False

    async def clear(self) -> bool:
        """Очистка всего кэша"""
        if not self._db:
            return False
        
        try:
            async with self._lock:
                await self._db.execute("DELETE FROM cache")
                await self._db.commit()
                return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False
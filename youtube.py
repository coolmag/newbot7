from __future__ import annotations
import asyncio
import logging
import os
import glob
from pathlib import Path
from typing import Any, Dict, List, Optional

import yt_dlp
from ytmusicapi import YTMusic

from config import Settings
from models import DownloadResult, Source, TrackInfo
from cache_service import CacheService

logger = logging.getLogger(__name__)

class SilentLogger:
    def debug(self, msg: str):
        if "rate limit" in msg.lower() or "http error 429" in msg.lower():
            logger.warning(f"[yt-dlp] {msg}")
    def warning(self, msg: str):
        pass
    def error(self, msg: str):
        logger.error(f"[yt-dlp] {msg}")

class YouTubeDownloader:
    FORBIDDEN_WORDS = [
        'how to', 'tutorial', 'making of', 'fl studio', 'lesson', 'course', 'mix', 
        'playlist', 'live', 'concert', 'full album', 'dj set', 'remix', 'bootleg',
        'mashup', 'megamix', 'continuous mix', 'non-stop', 'podcast'
    ]

    def __init__(self, settings: Settings, cache_service: CacheService):
        self._settings = settings
        self._cache = cache_service
        self._settings.DOWNLOADS_DIR.mkdir(exist_ok=True)
        
        self._ytmusic = YTMusic()
        self.semaphore = asyncio.Semaphore(3)  # для скачиваний
        self.search_semaphore = asyncio.Semaphore(5)  # для поиска
        
        logger.info("YouTubeDownloader initialized with ytmusicapi and caching")

    def _get_dl_opts(self) -> Dict[str, Any]:
        return {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": "bestaudio/best",
            "logger": SilentLogger(),
            "postprocessors": [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
            "outtmpl": str(self._settings.DOWNLOADS_DIR / "%(id)s.%(ext)s"),
            "extractor_args": {"youtube": {"player_client": ["android", "ios"]}},
            "user_agent": "com.google.android.youtube/19.29.37 (Linux; U; Android 11; en_US; Pixel 5) gzip",
        }

    def _is_track_valid(self, entry: Dict, decade: Optional[str] = None) -> bool:
        """Проверяет, является ли результат поиска валидным треком."""
        if not entry or entry.get('resultType') not in ['song', 'video']:
            return False

        title = entry.get('title', '').lower()
        if any(word in title for word in self.FORBIDDEN_WORDS):
            logger.debug(f"Filtered out '{title}' due to forbidden words.")
            return False
        
        duration_sec = entry.get('duration_seconds', 0)
        if not duration_sec or not (60 < duration_sec < 720): # 12 минут max
            logger.debug(f"Filtered out '{title}' due to duration: {duration_sec}s.")
            return False
            
        if decade:
            year_str = entry.get('year')
            if not year_str or not year_str.isdigit():
                logger.debug(f"Filtered out '{title}' as it has no year for decade filtering.")
                return False # У трека нет года, а мы фильтруем по нему
            
            try:
                year = int(year_str)
                start_year = int(decade[:4])
                end_year = start_year + 9
                if not (start_year <= year <= end_year):
                    logger.debug(f"Filtered out '{title}' ({year}) as it's outside decade {decade}.")
                    return False
            except (ValueError, IndexError):
                logger.warning(f"Could not parse decade: {decade}")
                return False # Невалидный формат десятилетия

        return True

    async def search(self, query: str, decade: Optional[str] = None, limit: int = 20) -> List[TrackInfo]:
        """Поиск треков с использованием YTMusic, фильтрацией и кэшированием."""
        async with self.search_semaphore:
            refined_query = f"{query} {decade}" if decade else query
            cache_key = f"ytmusic_search_v3:{refined_query.lower().strip()}"
            
            cached_tracks = await self._cache.get(cache_key)
            if cached_tracks is not None:
                logger.info(f"[Search] Cache hit for query: '{refined_query}'")
                return cached_tracks

            logger.info(f"[Search] Cache miss. Querying YTMusic API for: '{refined_query}'")
            
            loop = asyncio.get_running_loop()
            
            def do_search() -> List[Dict]:
                try:
                    # Ищем с запасом, чтобы после фильтрации что-то осталось
                    return self._ytmusic.search(refined_query, filter="songs", limit=limit * 2)
                except Exception as e:
                    logger.error(f"YTMusic search failed: {e}", exc_info=True)
                    return []

            search_results = await loop.run_in_executor(None, do_search)
            
            # Фильтруем результаты перед парсингом и кэшированием
            valid_entries = [entry for entry in search_results if self._is_track_valid(entry, decade=decade)]
            
            tracks = [self._parse_ytmusic_entry(entry) for entry in valid_entries][:limit]
            
            # Кэшируем отфильтрованный результат на 1 час
            await self._cache.set(cache_key, tracks, ttl=3600)
            
            logger.info(f"[Search] Found and filtered {len(tracks)} tracks for query '{refined_query}'")
            return tracks

    def _parse_ytmusic_entry(self, entry: Dict) -> TrackInfo:
        """Парсит результат поиска из YTMusic."""
        artists = ", ".join([artist['name'] for artist in entry.get('artists', [])])
        return TrackInfo(
            identifier=entry['videoId'],
            title=entry['title'],
            artist=artists,
            duration=int(entry.get('duration_seconds', 0)),
            source=Source.YOUTUBE,
            thumbnail_url=entry['thumbnails'][-1]['url'] if entry.get('thumbnails') else None
        )

    async def get_track_info(self, video_id: str) -> Optional[TrackInfo]:
        """Получение информации о треке с помощью yt-dlp и кэшированием."""
        cache_key = f"track_info:{video_id}"
        cached_info = await self._cache.get(cache_key)
        if cached_info:
            logger.debug(f"[TrackInfo] Cache hit for {video_id}")
            return cached_info

        logger.info(f"[TrackInfo] Cache miss. Fetching info for {video_id}")
        
        loop = asyncio.get_running_loop()
        
        def do_extract_info():
            try:
                opts = self._get_dl_opts()
                opts['skip_download'] = True
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(video_id, download=False)
            except Exception as e:
                logger.error(f"[TrackInfo] Failed to extract info for {video_id}: {e}")
                return None
        
        info = await loop.run_in_executor(None, do_extract_info)
        
        if not info:
            return None
        
        track_info = TrackInfo.from_yt_info(info)
        await self._cache.set(cache_key, track_info, ttl=86400) # Кэш на 24 часа
        return track_info

    async def download(self, video_id: str) -> DownloadResult:
        """Скачивание трека с проверкой кэша file_id."""
        async with self.semaphore:
            # 1. Получаем актуальную информацию о треке
            track_info = await self.get_track_info(video_id)
            if not track_info:
                return DownloadResult(success=False, error="Failed to get track info")
            
            # 2. Проверяем кэш file_id
            file_id_cache_key = f"file_id:{video_id}"
            cached_file_id = await self._cache.get(file_id_cache_key)
            if cached_file_id:
                logger.info(f"[Download] file_id cache hit for {video_id}")
                return DownloadResult(
                    success=True,
                    file_id=cached_file_id,
                    track_info=track_info
                )
            
            # 3. Если в кэше нет - скачиваем
            logger.info(f"[Download] Starting download: {video_id}")
            
            loop = asyncio.get_running_loop()
            
            def do_download():
                try:
                    with yt_dlp.YoutubeDL(self._get_dl_opts()) as ydl:
                        ydl.download([video_id])
                    return True
                except Exception as e:
                    logger.error(f"[Download] yt-dlp internal error for {video_id}: {e}", exc_info=True)
                    return False
            
            try:
                success = await asyncio.wait_for(loop.run_in_executor(None, do_download), timeout=300.0)
                if not success:
                    return DownloadResult(success=False, error="Download failed internally", track_info=track_info)
            except asyncio.TimeoutError:
                logger.error(f"[Download] Timeout: {video_id}")
                self._cleanup_partial(video_id)
                return DownloadResult(success=False, error="Timeout", track_info=track_info)

            final_path = self._find_downloaded_file(video_id)
            if not final_path:
                return DownloadResult(success=False, error="File not found after download", track_info=track_info)
            
            logger.info(f"[Download] Success: {video_id}")
            return DownloadResult(success=True, file_path=final_path, track_info=track_info)

    async def cache_file_id(self, video_id: str, file_id: str):
        """Сохраняет Telegram file_id в кэш навсегда."""
        cache_key = f"file_id:{video_id}"
        await self._cache.set(cache_key, file_id, ttl=0) # 0 = вечно
        logger.info(f"Cached file_id for {video_id}")

    def _find_downloaded_file(self, video_id: str) -> Optional[Path]:
        """Поиск скачанного файла."""
        pattern = str(self._settings.DOWNLOADS_DIR / f"{video_id}.mp3")
        files = glob.glob(pattern)
        if files:
            path = Path(files[0])
            if path.exists() and path.stat().st_size > 0:
                return path
        return None

    def _cleanup_partial(self, video_id: str):
        """Очистка временных файлов после неудачной загрузки."""
        pattern = str(self._settings.DOWNLOADS_DIR / f"{video_id}.*")
        for f in glob.glob(pattern):
            try:
                os.unlink(f)
            except Exception:
                pass
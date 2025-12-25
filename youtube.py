from __future__ import annotations
import asyncio
import logging
import re
import os
import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import yt_dlp

from config import Settings
from models import DownloadResult, Source, TrackInfo
from cache_service import CacheService

logger = logging.getLogger(__name__)

SearchMode = Literal['track', 'artist', 'genre']


class SilentLogger:
    def debug(self, msg): 
        if "ERROR" in str(msg).upper():
            logger.debug(f"[yt-dlp] {msg}")
    def warning(self, msg): 
        logger.warning(f"[yt-dlp] {msg}")
    def error(self, msg): 
        logger.error(f"[yt-dlp] {msg}")


class YouTubeDownloader:
    YT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

    def __init__(self, settings: Settings, cache_service: CacheService):
        self._settings = settings
        self._cache = cache_service
        self._settings.DOWNLOADS_DIR.mkdir(exist_ok=True)
        self.semaphore = asyncio.Semaphore(3)
        self.search_semaphore = asyncio.Semaphore(2)
        
        # Проверяем cookies
        if self._settings.COOKIES_FILE.exists():
            size = self._settings.COOKIES_FILE.stat().st_size
            logger.info(f"Cookies file found: {size} bytes")
        else:
            logger.warning("No cookies file - YouTube may block requests!")

    def _get_dl_opts(self, mode: str = "info") -> Dict[str, Any]:
        """Опции для yt-dlp"""
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_progress": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 30,
            "source_address": "0.0.0.0",
            "logger": SilentLogger(),
            "retries": 5,
            "fragment_retries": 5,
            "file_access_retries": 3,
            "extractor_retries": 3,
            "ignoreerrors": False,
            "geo_bypass": True,
            "geo_bypass_country": "US",
            # Формат - предпочитаем аудио
            "format": "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
            "outtmpl": str(self._settings.DOWNLOADS_DIR / "%(id)s.%(ext)s"),
            "max_filesize": self._settings.MAX_FILE_SIZE_MB * 1024 * 1024,
            # Важные опции для обхода блокировок
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                    "player_skip": ["webpage", "configs"],
                }
            },
        }
        
        # Cookies
        if self._settings.COOKIES_FILE.exists() and self._settings.COOKIES_FILE.stat().st_size > 0:
            opts['cookiefile'] = str(self._settings.COOKIES_FILE)
        
        # Proxy
        if self._settings.PROXY_URL:
            opts['proxy'] = self._settings.PROXY_URL
        
        if mode == "info":
            opts["skip_download"] = True
        
        return opts

    async def search(self, query: str, search_mode: SearchMode = 'genre', limit: int = 30) -> List[TrackInfo]:
        """Поиск треков"""
        async with self.search_semaphore:
            logger.info(f"[Search] Query: '{query}' | Mode: {search_mode} | Limit: {limit}")
            
            # Формируем поисковый запрос
            if search_mode == 'genre':
                search_query = f"ytsearch{limit}:{query} music mix playlist"
            elif search_mode == 'artist':
                search_query = f"ytsearch{limit}:{query} official audio"
            else:
                search_query = f"ytsearch{limit}:{query}"
            
            try:
                opts = self._get_dl_opts("info")
                opts["extract_flat"] = "in_playlist"
                opts["playlistend"] = limit
                
                loop = asyncio.get_running_loop()
                
                def do_search():
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(search_query, download=False)
                
                info = await asyncio.wait_for(
                    loop.run_in_executor(None, do_search),
                    timeout=60.0
                )
                
                if not info:
                    logger.warning(f"[Search] No info returned for '{query}'")
                    return []
                
                entries = info.get("entries", [])
                if not entries:
                    logger.warning(f"[Search] No entries for '{query}'")
                    return []
                
                tracks = []
                for entry in entries:
                    if not entry:
                        continue
                    
                    try:
                        video_id = entry.get('id') or entry.get('url', '').split('=')[-1]
                        if not video_id or len(video_id) != 11:
                            continue
                        
                        duration = entry.get('duration', 0) or 0
                        
                        # Фильтр по длительности
                        min_dur = self._settings.RADIO_MIN_DURATION_S
                        max_dur = self._settings.RADIO_MAX_DURATION_S
                        
                        if duration > 0 and not (min_dur <= duration <= max_dur):
                            continue
                        
                        title = entry.get('title', 'Unknown')
                        artist = entry.get('uploader') or entry.get('channel') or 'Unknown'
                        
                        # Пытаемся извлечь артиста из названия
                        if ' - ' in title:
                            parts = title.split(' - ', 1)
                            artist = parts[0].strip()
                            title = parts[1].strip()
                        
                        track = TrackInfo(
                            identifier=video_id,
                            title=title[:100],
                            artist=artist[:50],
                            duration=int(duration) if duration else 180,
                            source=Source.YOUTUBE,
                            thumbnail_url=entry.get('thumbnail')
                        )
                        tracks.append(track)
                        
                    except Exception as e:
                        logger.debug(f"[Search] Error parsing entry: {e}")
                        continue
                
                logger.info(f"[Search] Found {len(tracks)} valid tracks for '{query}'")
                return tracks
                
            except asyncio.TimeoutError:
                logger.error(f"[Search] Timeout for '{query}'")
                return []
            except Exception as e:
                logger.error(f"[Search] Error for '{query}': {e}", exc_info=True)
                return []

    async def download(self, video_id: str) -> DownloadResult:
        """Скачивание трека"""
        async with self.semaphore:
            logger.info(f"[Download] Starting: {video_id}")
            
            try:
                # Проверяем кэш
                cache_key = f"dl:{video_id}"
                cached = await self._cache.get(cache_key)
                if cached:
                    if isinstance(cached, DownloadResult) and cached.file_path:
                        if Path(cached.file_path).exists():
                            logger.info(f"[Download] Cache hit: {video_id}")
                            return cached
                
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                download_opts = self._get_dl_opts("download")
                
                loop = asyncio.get_running_loop()
                
                def do_download():
                    with yt_dlp.YoutubeDL(download_opts) as ydl:
                        return ydl.extract_info(video_url, download=True)
                
                info = await asyncio.wait_for(
                    loop.run_in_executor(None, do_download),
                    timeout=120.0
                )
                
                if not info:
                    return DownloadResult(success=False, error="No info returned")
                
                # Ищем файл
                final_path = self._find_downloaded_file(video_id)
                if not final_path:
                    # Пробуем альтернативные расширения
                    for ext in ["m4a", "webm", "mp3", "opus", "ogg", "mp4"]:
                        check_path = self._settings.DOWNLOADS_DIR / f"{video_id}.{ext}"
                        if check_path.exists() and check_path.stat().st_size > 0:
                            final_path = check_path
                            break
                
                if not final_path:
                    logger.error(f"[Download] File not found after download: {video_id}")
                    return DownloadResult(success=False, error="File not created")
                
                track_info = TrackInfo.from_yt_info(info)
                result = DownloadResult(
                    success=True, 
                    file_path=final_path, 
                    track_info=track_info
                )
                
                # Сохраняем в кэш (без файла, только метаданные)
                # await self._cache.set(cache_key, result)
                
                logger.info(f"[Download] Success: {video_id} -> {final_path.name}")
                return result
                
            except asyncio.TimeoutError:
                logger.error(f"[Download] Timeout: {video_id}")
                self._cleanup_partial(video_id)
                return DownloadResult(success=False, error="Download timeout")
                
            except Exception as e:
                error_msg = str(e)[:200]
                logger.error(f"[Download] Failed {video_id}: {error_msg}")
                self._cleanup_partial(video_id)
                
                # Специфичные ошибки
                if "Sign in" in error_msg or "bot" in error_msg.lower():
                    return DownloadResult(success=False, error="YouTube требует авторизацию")
                elif "unavailable" in error_msg.lower():
                    return DownloadResult(success=False, error="Видео недоступно")
                elif "private" in error_msg.lower():
                    return DownloadResult(success=False, error="Приватное видео")
                
                return DownloadResult(success=False, error=error_msg)

    def _find_downloaded_file(self, video_id: str) -> Optional[Path]:
        """Поиск скачанного файла"""
        for ext in ["m4a", "webm", "mp3", "opus", "ogg", "mp4", "mkv"]:
            file_path = self._settings.DOWNLOADS_DIR / f"{video_id}.{ext}"
            if file_path.exists() and file_path.stat().st_size > 0:
                return file_path
        
        # Поиск по паттерну
        pattern = str(self._settings.DOWNLOADS_DIR / f"{video_id}.*")
        for f in glob.glob(pattern):
            path = Path(f)
            if path.exists() and path.stat().st_size > 0 and not path.suffix == '.part':
                return path
        
        return None

    def _cleanup_partial(self, video_id: str):
        """Очистка частичных файлов"""
        pattern = str(self._settings.DOWNLOADS_DIR / f"{video_id}.*")
        for f in glob.glob(pattern):
            try:
                os.unlink(f)
            except:
                pass
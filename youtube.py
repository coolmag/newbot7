from __future__ import annotations
import asyncio
import logging
import os
import glob  # Added glob
import re
from pathlib import Path
from typing import Optional, List, Dict, Any, Literal

import yt_dlp
# import aiohttp # Not used in the provided YouTubeDownloader example

from config import Settings
from models import DownloadResult, Source, TrackInfo # Removed StreamInfoResult, StreamInfo
# from database import DatabaseService # Removed DatabaseService

logger = logging.getLogger(__name__)

# Define SilentLogger
class SilentLogger:
    """A silent logger that discards all messages."""
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


class YouTubeDownloader:
    """YouTube downloader with proper audio conversion for Telegram."""
    
    def __init__(self, settings: Settings):
        self._settings = settings
        self._temp_dir = settings.TEMP_DIR
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        common_opts = {
            'quiet': True,
            'no_warnings': True,
            'logger': SilentLogger(),
            'retries': 3,
            'fragment_retries': 3,
            "geo_bypass": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

        # --- Cookie Configuration (Priority: Browser > File) ---
        if self._settings.YT_COOKIES_BROWSER:
            profile = self._settings.YT_COOKIES_BROWSER_PROFILE or None
            common_opts['cookiesfrombrowser'] = (self._settings.YT_COOKIES_BROWSER, profile)
            logger.info(f"Using cookies from browser: {self._settings.YT_COOKIES_BROWSER}" + (f"/{profile}" if profile else ""))
        elif self._settings.COOKIES_FILE and self._settings.COOKIES_FILE.exists():
            common_opts['cookiefile'] = str(self._settings.COOKIES_FILE)
            logger.info(f"Using cookies from file: {self._settings.COOKIES_FILE}")
        else:
            logger.warning("No cookies configured. Downloads may fail due to bot detection.")

        self._search_opts = {
            **common_opts,
            'extract_flat': True,
            'skip_download': True,
        }
        
        self._download_opts = {
            **common_opts,
            'format': 'bestaudio/best',
            'outtmpl': str(self._temp_dir / '%(id)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'max_filesize': self._settings.PLAY_MAX_FILE_SIZE_MB * 1024 * 1024,
            'socket_timeout': 30,
        }

    async def search(
        self,
        query: str,
        limit: int = 30,
        search_mode: Literal['track', 'artist', 'genre'] = 'genre', # Used Literal directly
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
    ) -> List[TrackInfo]:
        """Search for tracks on YouTube."""
        logger.info(f"[Search] Запуск поиска для: '{query}' (режим: {search_mode})")
        
        ydl_opts = self._search_opts.copy()
        if search_mode == 'genre':
            # Для жанров ищем "official audio" для лучшего качества
            query += " official audio"
        
        try:
            loop = asyncio.get_event_loop()
            search_url = f"ytsearch{limit}:{query}"
            
            def extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(search_url, download=False)
            
            info = await loop.run_in_executor(None, extract)
            
            if not info or 'entries' not in info:
                logger.warning(f"[Search] Поиск для '{query}' не вернул результатов")
                return []
            
            tracks = []
            for entry in info['entries']:
                if not entry:
                    continue
                
                # Фильтрация по длительности
                duration = entry.get('duration', 0)
                if min_duration and duration < min_duration:
                    continue
                if max_duration and duration > max_duration:
                    continue
                
                track = TrackInfo(
                    title=entry.get('title', 'Unknown'),
                    artist=entry.get('uploader', 'Unknown'),
                    duration=duration,
                    source=Source.YOUTUBE.value,
                    identifier=entry.get('id'),
                    view_count=entry.get('view_count'),
                    like_count=entry.get('like_count'),
                )
                tracks.append(track)
            
            logger.info(f"[Search] Найдено и отфильтровано: {len(tracks)} треков.")
            return tracks
            
        except Exception as e:
            logger.error(f"[Search] Ошибка поиска для '{query}': {e}", exc_info=True)
            return []

    async def download(self, video_id: str) -> DownloadResult:
        """Download and convert video to MP3 for Telegram."""
        logger.info(f"[Download] Starting download for {video_id} to {self._temp_dir}")
        
        try:
            loop = asyncio.get_event_loop()
            ydl_opts = self._download_opts.copy()
            
            def download_sync(): # Renamed to avoid confusion with async
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # Сначала получаем метаданные
                    info = ydl.extract_info(video_id, download=False)
                    
                    # Скачиваем и конвертируем
                    ydl.download([video_id])
                    
                    return info
            
            info = await loop.run_in_executor(None, download_sync) # Used renamed function
            
            if not info:
                return DownloadResult(
                    success=False,
                    error="Could not get video info"
                )
            
            # Ищем созданный файл
            pattern = str(self._temp_dir / f"{video_id}.*")
            files = glob.glob(pattern)
            
            if not files:
                return DownloadResult(
                    success=False,
                    error="File not found after download"
                )
            
            # Находим MP3 файл
            mp3_file = None
            for file in files:
                if file.endswith('.mp3'):
                    mp3_file = file
                    break
            
            if not mp3_file:
                # If no MP3, fail
                logger.error(f"[Download] No MP3 file found for {video_id} after download.")
                return DownloadResult(
                    success=False,
                    error="No MP3 file found after conversion."
                )
            
            # Создаем TrackInfo
            track_info = TrackInfo(
                title=info.get('title', 'Unknown'),
                artist=info.get('uploader', 'Unknown'),
                duration=info.get('duration', 0),
                source=Source.YOUTUBE.value,
                identifier=video_id,
                view_count=info.get('view_count'),
                like_count=info.get('like_count'),
            )
            
            # Проверяем размер файла
            file_size = os.path.getsize(mp3_file)
            logger.info(f"[Download] File downloaded: {mp3_file}, size: {file_size} bytes")
            
            return DownloadResult(
                success=True,
                file_path=Path(mp3_file), # Converted to Path object
                track_info=track_info
            )
            
        except yt_dlp.utils.DownloadError as e:
            logger.error(f"[Download] Download error for {video_id}: {e}")
            return DownloadResult(
                success=False,
                error=str(e)
            )
        except Exception as e:
            logger.error(f"[Download] Unexpected error for {video_id}: {e}", exc_info=True)
            return DownloadResult(
                success=False,
                error=f"Download error: {str(e)}"
            )

    async def download_with_retry(self, query_or_id: str, max_retries: int = 3) -> DownloadResult:
        """
        Finds a video ID from a query if necessary, then attempts to download 
        the resolved video ID with a retry loop.
        """
        logger.info(f"[Downloader] Starting download/search for '{query_or_id}'.")
        video_id = None
        try:
            # --- Step 1: Resolve query_or_id to a concrete video_id ---
            if re.match(r'^[a-zA-Z0-9_-]{11}$', query_or_id):
                video_id = query_or_id
                logger.info(f"[Downloader] Provided query is already a video ID: {video_id}")
            else:
                logger.info(f"[Downloader] Provided query is a search term. Searching for best match...")
                tracks = await self.search(query_or_id, limit=1, search_mode='track')
                if not tracks:
                    return DownloadResult(success=False, error=f"No tracks found for search query: '{query_or_id}'")
                video_id = tracks[0].identifier
                logger.info(f"[Downloader] Search found best match: {video_id} for query '{query_or_id}'")

            if not video_id:
                return DownloadResult(success=False, error="Could not determine a video ID to download.")

            # --- Step 2: Attempt to download the video_id with retries ---
            for attempt in range(max_retries):
                logger.info(f"[Downloader] Attempt {attempt + 1}/{max_retries} to download {video_id}.")
                result = await self.download(video_id)
                
                if result.success:
                    logger.info(f"[Downloader] Successfully downloaded {video_id}.")
                    return result
                else:
                    logger.warning(f"[Downloader] Attempt {attempt + 1} failed for {video_id}: {result.error}")
                    if attempt < max_retries - 1:
                        sleep_time = 2 * (attempt + 1)
                        logger.info(f"[Downloader] Retrying in {sleep_time} seconds...")
                        await asyncio.sleep(sleep_time)

            return DownloadResult(success=False, error=f"Failed to download {video_id} after {max_retries} attempts.")

        except Exception as e:
            logger.error(f"[Downloader] Unhandled exception in download_with_retry for '{query_or_id}': {e}", exc_info=True)
            return DownloadResult(success=False, error=f"An unexpected error occurred: {e}")
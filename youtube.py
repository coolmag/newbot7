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

        # A full, modern User-Agent and Accept-Language header are less likely to be flagged.
        modern_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }

        common_opts = {
            'quiet': True,
            'no_warnings': True,
            'logger': SilentLogger(),
            'retries': 3,
            'fragment_retries': 3,
            "geo_bypass": True,
            "http_headers": modern_headers, # Use a full header set
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
        search_mode: Literal['track', 'artist', 'genre'] = 'genre',
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
    ) -> List[TrackInfo]:
        """Search for tracks on YouTube with enhanced multilingual support."""
        logger.info(f"[Search] Starting for: '{query}' (mode: {search_mode})")
        
        try:
            is_russian = self._is_russian_query(query)
            enhanced_query = self._enhance_search_query(query, is_russian, search_mode)
            
            loop = asyncio.get_event_loop()
            search_url = f"ytsearch{limit}:{enhanced_query}"
            
            def extract():
                with yt_dlp.YoutubeDL(self._search_opts) as ydl:
                    return ydl.extract_info(search_url, download=False)
            
            info = await loop.run_in_executor(None, extract)
            
            if not info or not info.get('entries'):
                logger.warning(f"[Search] No results for '{enhanced_query}'. Trying without enhancements.")
                search_url = f"ytsearch{limit}:{query}"
                info = await loop.run_in_executor(None, extract)
                if not info or not info.get('entries'):
                    logger.warning(f"[Search] Still no results for plain query '{query}'")
                    return []

            tracks = []
            for entry in info.get('entries', []):
                if not entry: continue
                
                duration = entry.get('duration') or 0
                if (min_duration and duration < min_duration) or \
                   (max_duration and duration > max_duration):
                    continue
                
                # Skip live streams which have no duration
                if entry.get('is_live'):
                    continue

                tracks.append(TrackInfo.from_yt_info(entry))
            
            logger.info(f"[Search] Found and filtered: {len(tracks)} tracks for '{query}'.")
            return tracks
            
        except Exception as e:
            logger.error(f"[Search] Critical error for '{query}': {e}", exc_info=True)
            return []

    def _is_russian_query(self, query: str) -> bool:
        """Checks if the query contains Cyrillic characters."""
        return bool(re.search('[а-яА-ЯёЁ]', query))

    def _enhance_search_query(self, query: str, is_russian: bool, search_mode: str) -> str:
        """Enhances the search query based on language and mode."""
        if search_mode != 'genre':
            return query
        
        if is_russian:
            return f'{query} сборник'
        else:
            return f'{query} playlist'


    async def download(self, video_id: str) -> DownloadResult:
        """
        Supervising download method that applies a timeout to the internal download logic.
        This prevents the entire application from hanging on a stalled yt-dlp process.
        """
        try:
            return await asyncio.wait_for(
                self._download_internal(video_id),
                timeout=120.0  # 2-minute timeout for the entire download process
            )
        except asyncio.TimeoutError:
            logger.error(f"[Download] Global timeout for {video_id} after 120 seconds.")
            # Clean up any partial junk files that might have been created
            for junk_file in glob.glob(str(self._temp_dir / f"{video_id}.*")):
                try: os.unlink(junk_file)
                except OSError: pass
            return DownloadResult(success=False, error="Download process timed out (120s)")
        except Exception as e:
            logger.error(f"[Download] Unexpected wrapper error for {video_id}: {e}", exc_info=True)
            return DownloadResult(success=False, error=f"Unexpected error: {e}")

    async def _download_internal(self, video_id: str) -> DownloadResult:
        """
        The core internal download logic, designed to be called by the supervising `download` method.
        """
        logger.info(f"[Download] Starting internal download for {video_id} to {self._temp_dir}")
        
        try:
            loop = asyncio.get_event_loop()
            
            def download_sync():
                with yt_dlp.YoutubeDL(self._download_opts) as ydl:
                    info = ydl.extract_info(video_id, download=False)
                    if not info:
                        raise DownloadError(f"Could not extract video info for {video_id}")
                    ydl.download([video_id])
                    return info
            
            info = await loop.run_in_executor(None, download_sync)
            
            pattern = str(self._temp_dir / f"{video_id}.*")
            files = glob.glob(pattern)
            
            if not files:
                return DownloadResult(success=False, error="File not found on disk after download.")

            found_file = None
            preferred_exts = ['.mp3', '.m4a']
            for ext in preferred_exts:
                for file_path in files:
                    if file_path.endswith(ext):
                        found_file = file_path
                        break
                if found_file: break
            
            if not found_file:
                first_file = files[0]
                logger.error(f"[Download] No valid audio file (.mp3, .m4a) found. Found: {first_file}. Check cookies.")
                try: os.unlink(first_file)
                except OSError: pass
                return DownloadResult(success=False, error="Downloaded file is not a valid audio format.")

            track_info = TrackInfo.from_yt_info(info)
            file_size = os.path.getsize(found_file)
            
            if file_size == 0:
                logger.error(f"[Download] Downloaded file {found_file} is empty.")
                try: os.unlink(found_file)
                except OSError: pass
                return DownloadResult(success=False, error="Downloaded file is empty.")

            logger.info(f"[Download] Successfully prepared file: {found_file}, size: {file_size} bytes")
            return DownloadResult(success=True, file_path=Path(found_file), track_info=track_info)
            
        except Exception as e:
            err_msg = str(e)
            logger.error(f"[Download] Internal download process failed for {video_id}: {err_msg}", exc_info=True)
            for junk_file in glob.glob(str(self._temp_dir / f"{video_id}.*")):
                try: os.unlink(junk_file)
                except OSError: pass
            return DownloadResult(success=False, error=f"Download failed: {err_msg[:200]}")

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
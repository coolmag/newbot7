from __future__ import annotations
import asyncio
import glob
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal
import os

import yt_dlp
from config import Settings
from models import DownloadResult, Source, TrackInfo
from cache_service import CacheService

logger = logging.getLogger(__name__)

SearchMode = Literal['track', 'artist', 'genre']

class SilentLogger:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass

class YouTubeDownloader:
    YT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

    def __init__(self, settings: Settings, cache_service: CacheService):
        self._settings = settings
        self._cache = cache_service
        self._settings.DOWNLOADS_DIR.mkdir(exist_ok=True)
        self.semaphore = asyncio.Semaphore(5)
        self.search_semaphore = asyncio.Semaphore(5)

    def _get_opts(self, mode: str = "download") -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_progress": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "source_address": "0.0.0.0",
            "no_check_certificate": True,
            "geo_bypass": True,
            "logger": SilentLogger(),
            "retries": 5,
            "fragment_retries": 5,
            "ignoreerrors": True,
        }
        
        modern_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        opts["http_headers"] = modern_headers

        if self._settings.COOKIES_FILE.exists() and self._settings.COOKIES_FILE.stat().st_size > 0:
            opts['cookiefile'] = str(self._settings.COOKIES_FILE)
        
        if self._settings.PROXY_URL:
            opts['proxy'] = self._settings.PROXY_URL

        if mode == "search":
            opts.update({
                "extract_flat": "in_playlist", 
                "skip_download": True,
            })
        elif mode == "download":
            opts.update({
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": str(self._settings.DOWNLOADS_DIR / "%(id)s.%(ext)s"),
                "max_filesize": self._settings.MAX_FILE_SIZE_MB * 1024 * 1024,
                "keepvideo": False,
                "nooverwrites": True,
            })
        return opts

    async def _extract_info(self, query: str, opts: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(opts).extract_info(query, download=False)),
                timeout=25.0
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout extracting info for '{query}'")
            raise

    def _find_downloaded_file(self, video_id: str) -> Optional[Path]:
        base_path = self._settings.DOWNLOADS_DIR / video_id
        for ext in ["m4a", "mp3", "webm", "opus", "ogg"]:
            file_path = base_path.with_suffix(f".{ext}")
            if file_path.exists() and file_path.stat().st_size > 0:
                return file_path
        return None

    async def search(self, query: str, search_mode: SearchMode = 'genre', limit: int = 20) -> List[TrackInfo]:
        async with self.search_semaphore:
            logger.info(f"[Search] Starting for: '{query}' (mode: {search_mode})")
            try:
                def filter_entry(entry: Dict[str, Any]) -> bool:
                    if not (entry and entry.get("id") and self.YT_ID_RE.match(entry.get("id")) and entry.get("title")): return False
                    
                    duration = int(entry.get('duration') or 0)
                    
                    # Use different duration limits based on search mode
                    if search_mode == 'genre':
                        min_dur, max_dur = self._settings.GENRE_SEARCH_MIN_DURATION_S, self._settings.GENRE_SEARCH_MAX_DURATION_S
                    else: # for 'track' or 'artist'
                        min_dur, max_dur = self._settings.RADIO_MIN_DURATION_S, self._settings.RADIO_MAX_DURATION_S

                    if not (min_dur <= duration <= max_dur): return False
                    
                    BANNED_KEYWORDS = ['karaoke', 'vlog', 'parody', 'reaction', 'tutorial', 'commentary', 'live', 'concert', 'shorts', 'подкаст']
                    if any(keyword in entry.get('title', '').lower() for keyword in BANNED_KEYWORDS): return False
                    
                    return True

                opts = self._get_opts("search")
                opts['match_filter'] = yt_dlp.utils.match_filter_func("!is_live")
                
                search_query = f"ytsearch{limit}:{query} playlist" if search_mode == 'genre' else f"ytsearch{limit}:{query}"
                info = await self._extract_info(search_query, opts)
                
                if not info or not info.get("entries"):
                    logger.warning(f"[Search] No results for '{search_query}'")
                    return []

                seen_ids, unique_results = set(), []
                for entry in info["entries"]:
                    if filter_entry(entry) and entry['id'] not in seen_ids:
                        seen_ids.add(entry['id'])
                        unique_results.append(TrackInfo.from_yt_info(entry))
                
                logger.info(f"[Search] Found and filtered {len(unique_results)} unique tracks.")
                return unique_results[:limit]
            except Exception as e:
                logger.error(f"[Search] Critical search error for '{query}': {e}", exc_info=True)
                return []

    async def download(self, video_id: str) -> DownloadResult:
        async with self.semaphore:
            try:
                cache_key = f"yt:{video_id}"
                cached = await self._cache.get(cache_key)
                if cached and cached.file_path and Path(cached.file_path).exists():
                    logger.debug(f"[Download] Using cache for {video_id}")
                    return cached
                
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                info_opts = self._get_opts("search")
                info = await self._extract_info(video_url, info_opts)
                track_info = TrackInfo.from_yt_info(info)

                download_opts = self._get_opts("download")
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(download_opts).download([video_url])),
                    timeout=120.0
                )
                
                final_path = self._find_downloaded_file(video_id)
                if not final_path:
                    raise FileNotFoundError(f"File not created after download attempt for {video_id}")

                result = DownloadResult(success=True, file_path=final_path, track_info=track_info)
                await self._cache.set(cache_key, result)
                logger.info(f"[Download] Successfully downloaded {video_id}")
                return result
            except Exception as e:
                logger.error(f"[Download] Download process failed for {video_id}: {e}", exc_info=True)
                for junk_file in glob.glob(str(self._settings.DOWNLOADS_DIR / f"{video_id}.*")):
                    try: os.unlink(junk_file)
                    except OSError: pass
                return DownloadResult(success=False, error=str(e)[:200])

    async def download_with_retry(self, query_or_id: str, max_retries: int = 1) -> DownloadResult:
        logger.info(f"[Downloader] Starting download/search for '{query_or_id}'.")
        try:
            if self.YT_ID_RE.match(query_or_id):
                return await self.download(query_or_id)
            
            tracks = await self.search(query_or_id, search_mode='track', limit=1)
            if not tracks:
                return DownloadResult(success=False, error="No tracks found")
            
            return await self.download(tracks[0].identifier)
        except Exception as e:
            logger.error(f"Unhandled exception in download_with_retry for '{query_or_id}': {e}", exc_info=True)
            return DownloadResult(success=False, error="An unexpected error occurred")
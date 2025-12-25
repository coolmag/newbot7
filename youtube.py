from __future__ import annotations
import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal

import yt_dlp
from ytmusicapi import YTMusic
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
        self.search_semaphore = asyncio.Semaphore(3)
        try:
            self._ytmusic = YTMusic()
        except Exception as e:
            logger.error(f"Failed to initialize YTMusic API: {e}")
            self._ytmusic = None

    def _get_dl_opts(self) -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            "quiet": True,
            "no_progress": True,
            "no_warnings": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "source_address": "0.0.0.0",
            "logger": SilentLogger(),
            "retries": 3,
            "fragment_retries": 3,
            "ignoreerrors": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": str(self._settings.DOWNLOADS_DIR / "%(id)s.%(ext)s"),
            "max_filesize": self._settings.MAX_FILE_SIZE_MB * 1024 * 1024,
        }
        if self._settings.COOKIES_FILE.exists() and self._settings.COOKIES_FILE.stat().st_size > 0:
            opts['cookiefile'] = str(self._settings.COOKIES_FILE)
        if self._settings.PROXY_URL:
            opts['proxy'] = self._settings.PROXY_URL
        return opts

    async def search(self, query: str, search_mode: SearchMode = 'genre', limit: int = 50) -> List[TrackInfo]:
        if search_mode != 'genre' or not self._ytmusic:
            return await self._search_youtube_direct(query, limit)
        
        logger.info(f"[YTMusic] Searching for genre: '{query}'")
        try:
            loop = asyncio.get_running_loop()
            # Search for playlists on YouTube Music
            search_results = await loop.run_in_executor(None, lambda: self._ytmusic.search(query, filter="playlists", limit=5))
            if not search_results:
                logger.warning(f"[YTMusic] No playlists found for '{query}'. Falling back to direct search.")
                return await self._search_youtube_direct(query, limit)

            all_video_ids = set()
            for playlist in search_results:
                playlist_id = playlist.get('playlistId')
                if not playlist_id: continue
                
                logger.debug(f"[YTMusic] Fetching tracks from playlist: {playlist.get('title')}")
                playlist_tracks = await loop.run_in_executor(None, lambda: self._ytmusic.get_playlist(playlist_id, limit=50))
                
                for track in playlist_tracks.get('tracks', []):
                    if track.get('videoId') and track.get('duration_seconds'):
                        all_video_ids.add(track['videoId'])
            
            if not all_video_ids:
                logger.warning(f"[YTMusic] Playlists found but they are empty. Falling back to direct search.")
                return await self._search_youtube_direct(query, limit)

            # Now, get metadata for these curated IDs using yt-dlp
            return await self._get_track_info_for_ids(list(all_video_ids), limit)

        except Exception as e:
            logger.error(f"[YTMusic] Critical search error for '{query}': {e}", exc_info=True)
            return []

    async def _search_youtube_direct(self, query: str, limit: int) -> List[TrackInfo]:
        logger.info(f"[YTDirect] Searching YouTube directly for: '{query}'")
        search_query = f"ytsearch{limit}:{query} music"
        try:
            opts = self._get_dl_opts()
            opts["extract_flat"] = "in_playlist"
            opts["skip_download"] = True

            loop = asyncio.get_running_loop()
            info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(opts).extract_info(search_query, download=False))
            
            if not info or not info.get("entries"):
                return []
            
            tracks = [TrackInfo.from_yt_info(entry) for entry in info["entries"] if entry]
            return tracks
        except Exception as e:
            logger.error(f"[YTDirect] Direct search failed: {e}", exc_info=True)
            return []

    async def _get_track_info_for_ids(self, video_ids: List[str], limit: int) -> List[TrackInfo]:
        logger.info(f"[YTInfo] Getting metadata for {len(video_ids)} curated IDs.")
        tracks = []
        opts = self._get_dl_opts()
        opts["skip_download"] = True
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            for video_id in video_ids:
                if len(tracks) >= limit: break
                try:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                    if info and (self._settings.RADIO_MIN_DURATION_S <= info.get('duration', 0) <= self._settings.RADIO_MAX_DURATION_S):
                        tracks.append(TrackInfo.from_yt_info(info))
                except Exception:
                    continue
        logger.info(f"[YTInfo] Successfully got metadata for {len(tracks)} tracks.")
        return tracks

    async def download(self, video_id: str) -> DownloadResult:
        async with self.semaphore:
            try:
                cache_key = f"yt:{video_id}"
                cached = await self._cache.get(cache_key)
                if cached and cached.file_path and Path(cached.file_path).exists():
                    return cached
                
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                download_opts = self._get_dl_opts("download")
                loop = asyncio.get_running_loop()
                
                info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(download_opts).extract_info(video_url, download=True))
                
                final_path = self._find_downloaded_file(video_id)
                if not final_path:
                    raise FileNotFoundError(f"File not created after download for {video_id}")

                track_info = TrackInfo.from_yt_info(info)
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

    def _find_downloaded_file(self, video_id: str) -> Optional[Path]:
        for ext in ["m4a", "mp3", "webm", "opus", "ogg"]:
            file_path = self._settings.DOWNLOADS_DIR / f"{video_id}.{ext}"
            if file_path.exists() and file_path.stat().st_size > 0:
                return file_path
        return None

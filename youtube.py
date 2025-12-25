from __future__ import annotations
import asyncio
import logging
import re
import os
import glob
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

    def _get_dl_opts(self, mode: str = "info") -> Dict[str, Any]:
        """
        Возвращает опции для yt-dlp.
        mode: "info" - только информация, "download" - скачивание
        """
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
            "ignoreerrors": False,  # Изменено на False для лучшей диагностики
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": str(self._settings.DOWNLOADS_DIR / "%(id)s.%(ext)s"),
            "max_filesize": self._settings.MAX_FILE_SIZE_MB * 1024 * 1024,
        }
        
        # Добавляем cookies если есть
        if self._settings.COOKIES_FILE.exists() and self._settings.COOKIES_FILE.stat().st_size > 0:
            opts['cookiefile'] = str(self._settings.COOKIES_FILE)
            logger.debug("Using cookies file for yt-dlp")
        
        # Добавляем прокси если есть
        if self._settings.PROXY_URL:
            opts['proxy'] = self._settings.PROXY_URL
            logger.debug(f"Using proxy: {self._settings.PROXY_URL}")
        
        # Для режима только информации
        if mode == "info":
            opts["skip_download"] = True
            opts["extract_flat"] = False
        
        return opts

    async def search(self, query: str, search_mode: SearchMode = 'genre', limit: int = 50) -> List[TrackInfo]:
        """Поиск треков по запросу"""
        async with self.search_semaphore:
            if search_mode == 'genre' and self._ytmusic:
                tracks = await self._search_ytmusic(query, limit)
                if tracks:
                    return tracks
            
            # Fallback на прямой поиск YouTube
            return await self._search_youtube_direct(query, limit)

    async def _search_ytmusic(self, query: str, limit: int) -> List[TrackInfo]:
        """Поиск через YouTube Music API"""
        logger.info(f"[YTMusic] Searching for: '{query}'")
        try:
            loop = asyncio.get_running_loop()
            
            # Сначала ищем песни напрямую
            search_results = await loop.run_in_executor(
                None, 
                lambda: self._ytmusic.search(query, filter="songs", limit=limit)
            )
            
            if search_results:
                tracks = []
                for item in search_results:
                    try:
                        video_id = item.get('videoId')
                        if not video_id:
                            continue
                        
                        duration = item.get('duration_seconds', 0)
                        if not duration:
                            # Попытка распарсить duration из строки
                            duration_str = item.get('duration', '0:00')
                            parts = duration_str.split(':')
                            if len(parts) == 2:
                                duration = int(parts[0]) * 60 + int(parts[1])
                            elif len(parts) == 3:
                                duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        
                        # Фильтр по длительности
                        if not (self._settings.RADIO_MIN_DURATION_S <= duration <= self._settings.RADIO_MAX_DURATION_S):
                            continue
                        
                        title = item.get('title', 'Unknown')
                        artists = item.get('artists', [])
                        artist = artists[0].get('name', 'Unknown') if artists else 'Unknown'
                        
                        track = TrackInfo(
                            identifier=video_id,
                            title=title,
                            artist=artist,
                            duration=duration,
                            source=Source.YOUTUBE
                        )
                        tracks.append(track)
                        
                        if len(tracks) >= limit:
                            break
                    except Exception as e:
                        logger.debug(f"Error parsing track: {e}")
                        continue
                
                if tracks:
                    logger.info(f"[YTMusic] Found {len(tracks)} tracks for '{query}'")
                    return tracks
            
            # Если песни не найдены, ищем плейлисты
            return await self._search_ytmusic_playlists(query, limit)
            
        except Exception as e:
            logger.error(f"[YTMusic] Search error for '{query}': {e}", exc_info=True)
            return []

    async def _search_ytmusic_playlists(self, query: str, limit: int) -> List[TrackInfo]:
        """Поиск плейлистов в YouTube Music"""
        logger.info(f"[YTMusic] Searching playlists for: '{query}'")
        try:
            loop = asyncio.get_running_loop()
            
            search_results = await loop.run_in_executor(
                None, 
                lambda: self._ytmusic.search(query, filter="playlists", limit=5)
            )
            
            if not search_results:
                logger.warning(f"[YTMusic] No playlists found for '{query}'")
                return []

            all_tracks = []
            for playlist in search_results:
                playlist_id = playlist.get('browseId') or playlist.get('playlistId')
                if not playlist_id:
                    continue
                
                try:
                    logger.debug(f"[YTMusic] Fetching playlist: {playlist.get('title')}")
                    playlist_data = await loop.run_in_executor(
                        None, 
                        lambda pid=playlist_id: self._ytmusic.get_playlist(pid, limit=50)
                    )
                    
                    for track in playlist_data.get('tracks', []):
                        video_id = track.get('videoId')
                        if not video_id:
                            continue
                        
                        duration = track.get('duration_seconds', 0)
                        if not (self._settings.RADIO_MIN_DURATION_S <= duration <= self._settings.RADIO_MAX_DURATION_S):
                            continue
                        
                        title = track.get('title', 'Unknown')
                        artists = track.get('artists', [])
                        artist = artists[0].get('name', 'Unknown') if artists else 'Unknown'
                        
                        track_info = TrackInfo(
                            identifier=video_id,
                            title=title,
                            artist=artist,
                            duration=duration,
                            source=Source.YOUTUBE
                        )
                        all_tracks.append(track_info)
                        
                        if len(all_tracks) >= limit:
                            break
                            
                except Exception as e:
                    logger.debug(f"[YTMusic] Error fetching playlist: {e}")
                    continue
                
                if len(all_tracks) >= limit:
                    break
            
            logger.info(f"[YTMusic] Found {len(all_tracks)} tracks from playlists")
            return all_tracks
            
        except Exception as e:
            logger.error(f"[YTMusic] Playlist search error: {e}", exc_info=True)
            return []

    async def _search_youtube_direct(self, query: str, limit: int) -> List[TrackInfo]:
        """Прямой поиск на YouTube через yt-dlp"""
        logger.info(f"[YTDirect] Searching YouTube for: '{query}'")
        search_query = f"ytsearch{limit}:{query} music"
        
        try:
            opts = self._get_dl_opts("info")
            opts["extract_flat"] = "in_playlist"
            opts["skip_download"] = True

            loop = asyncio.get_running_loop()
            
            def do_search():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(search_query, download=False)
            
            info = await loop.run_in_executor(None, do_search)
            
            if not info or not info.get("entries"):
                logger.warning(f"[YTDirect] No results for '{query}'")
                return []
            
            tracks = []
            for entry in info["entries"]:
                if not entry:
                    continue
                try:
                    track = TrackInfo.from_yt_info(entry)
                    if track and self._is_valid_duration(track.duration):
                        tracks.append(track)
                except Exception as e:
                    logger.debug(f"Error parsing entry: {e}")
                    continue
            
            logger.info(f"[YTDirect] Found {len(tracks)} valid tracks")
            return tracks
            
        except Exception as e:
            logger.error(f"[YTDirect] Search failed: {e}", exc_info=True)
            return []

    def _is_valid_duration(self, duration: int) -> bool:
        """Проверка валидности длительности трека"""
        return self._settings.RADIO_MIN_DURATION_S <= duration <= self._settings.RADIO_MAX_DURATION_S

    async def download(self, video_id: str) -> DownloadResult:
        """Скачивание трека по video_id"""
        async with self.semaphore:
            try:
                # Проверяем кэш
                cache_key = f"yt:{video_id}"
                cached = await self._cache.get(cache_key)
                if cached and cached.file_path and Path(cached.file_path).exists():
                    logger.debug(f"[Download] Using cached file for {video_id}")
                    return cached
                
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                download_opts = self._get_dl_opts("download")
                
                loop = asyncio.get_running_loop()
                
                def do_download():
                    with yt_dlp.YoutubeDL(download_opts) as ydl:
                        return ydl.extract_info(video_url, download=True)
                
                logger.info(f"[Download] Starting download for {video_id}")
                info = await loop.run_in_executor(None, do_download)
                
                if not info:
                    raise Exception("No info returned from yt-dlp")
                
                # Ищем скачанный файл
                final_path = self._find_downloaded_file(video_id)
                if not final_path:
                    raise FileNotFoundError(f"File not created after download for {video_id}")

                track_info = TrackInfo.from_yt_info(info)
                result = DownloadResult(success=True, file_path=final_path, track_info=track_info)
                
                # Сохраняем в кэш
                await self._cache.set(cache_key, result)
                logger.info(f"[Download] Successfully downloaded {video_id} -> {final_path}")
                return result
                
            except Exception as e:
                logger.error(f"[Download] Failed for {video_id}: {e}", exc_info=True)
                
                # Очистка неудачных загрузок
                self._cleanup_partial_download(video_id)
                
                return DownloadResult(success=False, error=str(e)[:200])

    def _find_downloaded_file(self, video_id: str) -> Optional[Path]:
        """Поиск скачанного файла по video_id"""
        for ext in ["m4a", "mp3", "webm", "opus", "ogg", "mp4", "mkv"]:
            file_path = self._settings.DOWNLOADS_DIR / f"{video_id}.{ext}"
            if file_path.exists() and file_path.stat().st_size > 0:
                return file_path
        
        # Поиск по паттерну
        pattern = str(self._settings.DOWNLOADS_DIR / f"{video_id}.*")
        files = glob.glob(pattern)
        for f in files:
            path = Path(f)
            if path.exists() and path.stat().st_size > 0:
                return path
        
        return None

    def _cleanup_partial_download(self, video_id: str):
        """Очистка частично скачанных файлов"""
        pattern = str(self._settings.DOWNLOADS_DIR / f"{video_id}.*")
        for junk_file in glob.glob(pattern):
            try:
                os.unlink(junk_file)
                logger.debug(f"Cleaned up partial file: {junk_file}")
            except OSError as e:
                logger.warning(f"Failed to clean up {junk_file}: {e}")

    async def get_track_info(self, video_id: str) -> Optional[TrackInfo]:
        """Получение информации о треке без скачивания"""
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            opts = self._get_dl_opts("info")
            
            loop = asyncio.get_running_loop()
            
            def do_extract():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(video_url, download=False)
            
            info = await loop.run_in_executor(None, do_extract)
            
            if info:
                return TrackInfo.from_yt_info(info)
            return None
            
        except Exception as e:
            logger.error(f"[Info] Failed to get info for {video_id}: {e}")
            return None
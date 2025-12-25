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
        pass
    def warning(self, msg): 
        pass  # Игнорируем все предупреждения
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
        
        # Удаляем старые cookies если они вызывают проблемы
        if self._settings.COOKIES_FILE.exists():
            try:
                self._settings.COOKIES_FILE.unlink()
                logger.info("Removed old cookies file")
            except Exception:
                pass
        
        logger.info("YouTubeDownloader initialized")

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
            "ignoreerrors": True,
            "geo_bypass": True,
            "geo_bypass_country": "US",
            
            "format": "bestaudio/best",
            "extractaudio": True,
            "postprocessors": [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }],
            
            "outtmpl": str(self._settings.DOWNLOADS_DIR / "%(id)s.%(ext)s"),
            
            # Используем web клиент без cookies
            "extractor_args": {
                "youtube": {
                    "player_client": ["web", "mweb"],
                    "player_skip": ["webpage", "configs"],
                }
            },
            
            # Заголовки браузера
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
        }
        
        # НЕ используем cookies!
        # Proxy если есть
        if self._settings.PROXY_URL:
            opts['proxy'] = self._settings.PROXY_URL
        
        if mode == "info":
            opts["skip_download"] = True
        
        return opts

    async def search(self, query: str, search_mode: SearchMode = 'genre', limit: int = 30) -> List[TrackInfo]:
        """Поиск треков"""
        async with self.search_semaphore:
            logger.info(f"[Search] Query: '{query}' | Mode: {search_mode}")
            
            # Формируем поисковые запросы
            if search_mode == 'genre':
                search_queries = [
                    f"ytsearch{limit}:{query} songs",
                    f"ytsearch{limit}:{query} music",
                    f"ytsearch{limit}:{query} audio",
                ]
            else:
                search_queries = [
                    f"ytsearch{limit}:{query}",
                ]
            
            for sq in search_queries:
                tracks = await self._execute_search_query(sq, search_mode)
                if tracks:
                    return tracks
            
            return []

    async def _execute_search_query(self, search_query: str, search_mode: SearchMode) -> List[TrackInfo]:
        """Выполняет поиск по одному запросу с учётом режима поиска"""
        try:
            opts = self._get_dl_opts("info")
            opts["extract_flat"] = "in_playlist"
            
            loop = asyncio.get_running_loop()
            
            def do_search():
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(search_query, download=False)
                except Exception as e:
                    logger.debug(f"Search error: {e}")
                    return None
            
            info = await asyncio.wait_for(
                loop.run_in_executor(None, do_search),
                timeout=30.0
            )
            
            if not info:
                return []
            
            entries = info.get("entries", [])
            if not entries:
                return []
            
            tracks = []
            
            # Определяем лимиты длительности в зависимости от режима поиска
            if search_mode == 'genre':
                min_dur = self._settings.GENRE_SEARCH_MIN_DURATION_S
                max_dur = self._settings.GENRE_SEARCH_MAX_DURATION_S
            else:
                min_dur = self._settings.RADIO_MIN_DURATION_S
                max_dur = self._settings.RADIO_MAX_DURATION_S
            
            for entry in entries:
                if not entry:
                    continue
                
                track = self._parse_entry(entry, min_dur, max_dur)
                if track:
                    tracks.append(track)
            
            logger.info(f"[Search] Found {len(tracks)} tracks for query '{search_query}' (mode: {search_mode})")
            return tracks
            
        except asyncio.TimeoutError:
            logger.warning(f"[Search] Timeout for '{search_query}'")
            return []
        except Exception as e:
            logger.error(f"[Search] Error for '{search_query}': {e}", exc_info=True)
            return []

    def _parse_entry(self, entry: dict, min_dur: int, max_dur: int) -> Optional[TrackInfo]:
        """Парсит запись"""
        video_id = entry.get('id')
        if not video_id:
            url = entry.get('url', '')
            if 'watch?v=' in url:
                video_id = url.split('watch?v=')[-1].split('&')[0]
            elif len(url) == 11:
                video_id = url
        
        if not video_id or len(video_id) != 11:
            return None
        
        duration = entry.get('duration', 0) or 0
        
        # Пропускаем слишком длинные/короткие
        if duration > 0:
            if duration < min_dur or duration > max_dur:
                return None
        
        title = entry.get('title', 'Unknown')
        
        # Пропускаем стримы
        if 'live' in title.lower() and duration == 0:
            return None
        if '24/7' in title:
            return None
        
        artist = (
            entry.get('artist') or 
            entry.get('uploader') or 
            entry.get('channel') or 
            'Unknown'
        )
        
        # Парсим артиста из названия
        if ' - ' in title:
            parts = title.split(' - ', 1)
            artist = parts[0].strip()[:50]
            title = parts[1].strip()
        
        # Чистим название
        for suffix in ['(Official Audio)', '(Official Video)', '[Official]', 
                       '(Lyrics)', '(Official Music Video)', '| Official']:
            title = title.replace(suffix, '').strip()
        
        return TrackInfo(
            identifier=video_id,
            title=title[:100],
            artist=artist[:50],
            duration=int(duration) if duration else 200,
            source=Source.YOUTUBE,
            thumbnail_url=entry.get('thumbnail')
        )

    async def download(self, video_id: str) -> DownloadResult:
        """Скачивание трека"""
        async with self.semaphore:
            logger.info(f"[Download] Starting: {video_id}")
            
            try:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                download_opts = self._get_dl_opts("download")
                
                loop = asyncio.get_running_loop()
                
                def do_download():
                    try:
                        with yt_dlp.YoutubeDL(download_opts) as ydl:
                            return ydl.extract_info(video_url, download=True)
                    except Exception as e:
                        logger.error(f"Download error: {e}")
                        return None
                
                info = await asyncio.wait_for(
                    loop.run_in_executor(None, do_download),
                    timeout=300.0
                )
                
                if not info:
                    return DownloadResult(success=False, error="Download failed")
                
                # Ищем файл
                final_path = self._find_downloaded_file(video_id)
                if not final_path:
                    return DownloadResult(success=False, error="File not found")
                
                track_info = TrackInfo.from_yt_info(info)
                
                logger.info(f"[Download] Success: {video_id}")
                return DownloadResult(
                    success=True, 
                    file_path=final_path, 
                    track_info=track_info
                )
                
            except asyncio.TimeoutError:
                logger.error(f"[Download] Timeout: {video_id}")
                self._cleanup_partial(video_id)
                return DownloadResult(success=False, error="Timeout")
                
            except Exception as e:
                logger.error(f"[Download] Error: {e}")
                self._cleanup_partial(video_id)
                return DownloadResult(success=False, error=str(e)[:100])

    def _find_downloaded_file(self, video_id: str) -> Optional[Path]:
        """Поиск скачанного файла"""
        for ext in ["m4a", "webm", "mp3", "opus", "ogg", "mp4"]:
            file_path = self._settings.DOWNLOADS_DIR / f"{video_id}.{ext}"
            if file_path.exists() and file_path.stat().st_size > 0:
                return file_path
        
        pattern = str(self._settings.DOWNLOADS_DIR / f"{video_id}.*")
        for f in glob.glob(pattern):
            path = Path(f)
            if path.exists() and path.stat().st_size > 0 and '.part' not in str(path):
                return path
        
        return None

    def _cleanup_partial(self, video_id: str):
        """Очистка"""
        pattern = str(self._settings.DOWNLOADS_DIR / f"{video_id}.*")
        for f in glob.glob(pattern):
            try:
                os.unlink(f)
            except Exception:
                pass
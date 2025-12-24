import asyncio
import logging
import random
import re
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError, BadRequest

from config import Settings
from models import TrackInfo, DownloadResult
from youtube import YouTubeDownloader, SearchMode
from keyboards import get_dashboard_keyboard
from radio_voting import GenreVotingService

logger = logging.getLogger("radio")

@dataclass
class RadioSession:
    chat_id: int
    bot: Bot
    downloader: YouTubeDownloader
    settings: Settings
    query: str
    search_mode: SearchMode
    display_name: Optional[str] = None
    
    # State
    is_running: bool = field(init=False, default=False)
    playlist: List[TrackInfo] = field(default_factory=list)
    played_ids: Set[str] = field(default_factory=set)
    current_task: Optional[asyncio.Task] = None
    skip_event: asyncio.Event = field(default_factory=asyncio.Event)
    
    async def start(self):
        if self.is_running:
            return
        
        logger.info(f"[{self.chat_id}] Starting radio session for query: {self.query}")
        await self.bot.send_message(
            self.chat_id,
            f"🎧 Запускаю радио: **{self.display_name or self.query}**...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        self.is_running = True
        self.current_task = asyncio.create_task(self._radio_loop())

    async def stop(self):
        if not self.is_running:
            return
        
        self.is_running = False
        if self.current_task:
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass # Expected
        logger.info(f"[{self.chat_id}] Stopped radio session.")

    async def skip(self):
        self.skip_event.set()

    async def _fill_playlist(self):
        try:
            tracks = await self.downloader.search(
                self._query, 
                search_mode=self._search_mode,
                limit=30
            )
            new_tracks = [t for t in tracks if t.identifier not in self.played_ids]
            if new_tracks:
                random.shuffle(new_tracks)
                self.playlist.extend(new_tracks)
                logger.info(f"[{self.chat_id}] Added {len(new_tracks)} new tracks to playlist.")
            else:
                logger.warning(f"[{self.chat_id}] No new tracks found for '{self._query}'.")
        except Exception as e:
            logger.error(f"[{self.chat_id}] Error filling playlist: {e}", exc_info=True)

    async def _radio_loop(self):
        error_count = 0
        while self.is_running:
            try:
                if len(self.playlist) < 5:
                    await self._fill_playlist()
                
                if not self.playlist:
                    logger.warning(f"[{self.chat_id}] Playlist is empty. Waiting...")
                    await asyncio.sleep(10)
                    continue
                
                track = self.playlist.pop(0)
                self.played_ids.add(track.identifier)
                if len(self.played_ids) > 200:
                    self.played_ids.pop()

                await self._play_track(track)
                
                try:
                    # Wait for 90 seconds or until skip event is set
                    await asyncio.wait_for(self.skip_event.wait(), timeout=90.0)
                except asyncio.TimeoutError:
                    pass # Normal flow
                finally:
                    self.skip_event.clear()
                
                error_count = 0
            except asyncio.CancelledError:
                logger.info(f"[{self.chat_id}] Radio loop cancelled.")
                break
            except Exception as e:
                logger.error(f"[{self.chat_id}] Error in radio loop: {e}", exc_info=True)
                error_count += 1
                if error_count >= 3:
                    await self.bot.send_message(self.chat_id, "⚠️ Радио остановлено из-за множественных ошибок.")
                    break
                await asyncio.sleep(5)
        self.is_running = False

    async def _play_track(self, track: TrackInfo):
        result = None
        try:
            logger.info(f"[{self.chat_id}] Processing track: {track.title}")
            result = await self.downloader.download(track.identifier)
            if not result or not result.success:
                logger.error(f"[{self.chat_id}] Download failed for {track.identifier}: {result.error if result else 'Unknown'}")
                return

            with open(result.file_path, 'rb') as audio_file:
                await self.bot.send_audio(
                    chat_id=self._chat_id,
                    audio=audio_file,
                    title=track.title,
                    performer=track.artist,
                    duration=track.duration
                )
        except Exception as e:
            logger.error(f"[{self.chat_id}] Failed to play track {track.identifier}: {e}", exc_info=True)
        finally:
            if result and result.file_path and result.file_path.exists():
                try:
                    result.file_path.unlink()
                except OSError as e:
                    logger.error(f"[{self.chat_id}] Failed to clean up file {result.file_path}: {e}")

class RadioManager:
    def __init__(self, bot: Bot, settings: Settings, downloader: YouTubeDownloader, voting_service: GenreVotingService):
        self._bot = bot
        self._settings = settings
        self._downloader = downloader
        self._voting_service = voting_service
        self._sessions: Dict[int, RadioSession] = {}
        self._locks: Dict[int, asyncio.Lock] = {}

    def _get_lock(self, chat_id: int) -> asyncio.Lock:
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    async def start(self, chat_id: int, query: str, chat_type: str, search_mode: SearchMode, display_name: Optional[str] = None):
        async with self._get_lock(chat_id):
            if chat_id in self._sessions:
                await self._sessions[chat_id].stop()
            
            if query == "random":
                query, display_name = self._get_random_style_query()
            
            session = RadioSession(
                chat_id=chat_id, bot=self._bot, downloader=self._downloader,
                settings=self._settings, query=query, search_mode=search_mode,
                display_name=display_name or query
            )
            self._sessions[chat_id] = session
            await session.start()

    async def stop(self, chat_id: int):
        async with self._get_lock(chat_id):
            if session := self._sessions.pop(chat_id, None):
                await session.stop()

    async def skip(self, chat_id: int):
        if session := self._sessions.get(chat_id):
            await session.skip()

    async def stop_all(self):
        for chat_id in list(self._sessions.keys()):
            await self.stop(chat_id)
            
    def _get_random_style_query(self) -> tuple[str, str]:
        # ... implementation from previous version
        return "lofi beats", "Lo-Fi"

import asyncio
import logging
import random
import os
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field

from telegram import Bot, Message
from telegram.constants import ParseMode
from telegram.error import BadRequest

from config import Settings
from models import TrackInfo, DownloadResult
from youtube import YouTubeDownloader

logger = logging.getLogger("radio")

def format_duration(seconds: int) -> str:
    mins, secs = divmod(seconds, 60)
    return f"{mins}:{secs:02d}"

def get_now_playing_message(track: TrackInfo, genre_name: str, decade: Optional[str] = None) -> str:
    icon = random.choice(["🎧", "🎵", "🎶", "📻", "💿"])
    title = track.title[:40].strip()
    artist = track.artist[:30].strip()
    era_info = f" ({decade})" if decade else ""
    return f"{icon} *{title}*\n👤 {artist}\n⏱ {format_duration(track.duration)} | 📻 _{genre_name.strip()}{era_info}_"

@dataclass
class RadioSession:
    chat_id: int
    bot: Bot
    downloader: YouTubeDownloader
    settings: Settings
    query: str
    display_name: str
    decade: Optional[str] = None
    
    is_running: bool = field(init=False, default=False)
    playlist: List[TrackInfo] = field(default_factory=list)
    played_ids: Set[str] = field(default_factory=set)
    current_task: Optional[asyncio.Task] = None
    skip_event: asyncio.Event = field(default_factory=asyncio.Event)
    status_message: Optional[Message] = None
    tracks_played: int = field(init=False, default=0)
    
    async def start(self):
        if self.is_running: return
        self.is_running = True
        self.current_task = asyncio.create_task(self._radio_loop())
        logger.info(f"[{self.chat_id}] 🚀 Radio started: '{self.query}' decade: {self.decade}")

    async def stop(self):
        if not self.is_running: return
        self.is_running = False
        if self.current_task: self.current_task.cancel()
        await self._delete_status()
        logger.info(f"[{self.chat_id}] 🛑 Radio stopped. Played {self.tracks_played} tracks.")

    async def skip(self):
        self.skip_event.set()

    async def _update_status(self, text: str):
        try:
            if self.status_message:
                await self.status_message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
                return
            self.status_message = await self.bot.send_message(self.chat_id, text, parse_mode=ParseMode.MARKDOWN)
        except BadRequest: self.status_message = None
        except Exception as e: logger.warning(f"[{self.chat_id}] Status update error: {e}")

    async def _delete_status(self):
        if self.status_message:
            try: await self.status_message.delete()
            except Exception: pass
            self.status_message = None

    async def _fill_playlist(self):
        await self._update_status(f"🌌 Поиск новой музыки...\n\nПоток: _{self.display_name}_")
        logger.info(f"[{self.chat_id}] 🔍 Searching for '{self.query}', decade: {self.decade}")
        try:
            tracks = await self.downloader.search(self.query, decade=self.decade, limit=20)
            new_tracks = [t for t in tracks if t.identifier not in self.played_ids]
            if new_tracks:
                random.shuffle(new_tracks)
                self.playlist.extend(new_tracks)
                logger.info(f"[{self.chat_id}] ✅ Added {len(new_tracks)} new tracks.")
            else:
                logger.warning(f"[{self.chat_id}] ⚠️ No new tracks found for query '{self.query}'.")
        except Exception as e:
            logger.error(f"[{self.chat_id}] ❌ Playlist fill error: {e}", exc_info=True)

    async def _radio_loop(self):
        await self._update_status(f"📻 *Запуск радио...*\n\nВолна: _{self.display_name}_")
        error_streak = 0
        while self.is_running:
            try:
                if len(self.playlist) < 5:
                    await self._fill_playlist()
                
                if not self.playlist:
                    logger.warning(f"[{self.chat_id}] Playlist empty, trying one more time.")
                    await self._fill_playlist() # Try one more time
                    if not self.playlist:
                        logger.error(f"[{self.chat_id}] ❌ Playlist is empty after all retries. Stopping.")
                        await self._update_status(f"❌ Не удалось найти музыку для потока _{self.display_name}_. Радио остановлено.")
                        break

                track = self.playlist.pop(0)
                self.played_ids.add(track.identifier)
                if len(self.played_ids) > 200: self.played_ids = set(list(self.played_ids)[100:])

                try:
                    success = await asyncio.wait_for(self._play_track(track), timeout=150.0)
                    if success:
                        error_streak = 0
                        self.tracks_played += 1
                        await asyncio.wait_for(self.skip_event.wait(), timeout=float(track.duration))
                    else: raise Exception("Play track failed")
                except Exception as e:
                    error_streak += 1
                    logger.warning(f"[{self.chat_id}] Track error ({error_streak}/5): {e}")
                    if error_streak >= 5:
                        await self._update_status("❌ Слишком много ошибок подряд. Радио временно остановлено.")
                        break
                    continue
                finally:
                    self.skip_event.clear()
            except asyncio.CancelledError: break
            except Exception as e:
                logger.error(f"[{self.chat_id}] ❌ Unhandled error in radio loop: {e}", exc_info=True)
                break
        self.is_running = False

    async def _play_track(self, track: TrackInfo) -> bool:
        await self._update_status(f"📡 Загрузка аудиопотока...\n\nТрек: _{track.title}_")
        result: Optional[DownloadResult] = None
        try:
            result = await self.downloader.download(track.identifier)
            if not result or not result.success:
                logger.error(f"[{self.chat_id}] ❌ Download failed: {result.error if result else 'Unknown'}")
                return False
            caption = get_now_playing_message(track, self.display_name, self.decade)
            if result.file_id:
                await self.bot.send_audio(self.chat_id, audio=result.file_id, caption=caption, parse_mode=ParseMode.MARKDOWN)
            elif result.file_path and os.path.exists(result.file_path):
                with open(result.file_path, 'rb') as f:
                    sent_message = await self.bot.send_audio(self.chat_id, audio=f, caption=caption, parse_mode=ParseMode.MARKDOWN)
                    if sent_message.audio: await self.downloader.cache_file_id(track.identifier, sent_message.audio.file_id)
            else: return False
            await self._delete_status()
            logger.info(f"[{self.chat_id}] ✅ Sent: {track.title}")
            return True
        except Exception as e:
            logger.error(f"[{self.chat_id}] ❌ Critical error in _play_track: {e}", exc_info=True)
            return False
        finally:
            if result and result.file_path and os.path.exists(result.file_path):
                try: os.unlink(result.file_path)
                except OSError: pass

class RadioManager:
    def __init__(self, bot: Bot, settings: Settings, downloader: YouTubeDownloader):
        self._bot, self._settings, self._downloader = bot, settings, downloader
        self._sessions: Dict[int, RadioSession] = {}
        self._locks: Dict[int, asyncio.Lock] = {}

    def _get_lock(self, chat_id: int) -> asyncio.Lock:
        self._locks.setdefault(chat_id, asyncio.Lock())
        return self._locks[chat_id]

    async def start(self, chat_id: int, query: str, display_name: Optional[str] = None, decade: Optional[str] = None):
        async with self._get_lock(chat_id):
            if chat_id in self._sessions:
                await self._sessions[chat_id].stop()
            
            if query == "random":
                query, decade, display_name = self._get_random_query()

            display_name = display_name or query
            await self._bot.send_message(chat_id, f"🛰️ Настраиваюсь на волну: *{display_name}*", parse_mode=ParseMode.MARKDOWN)
            
            session = RadioSession(
                chat_id=chat_id, bot=self._bot, downloader=self._downloader, settings=self._settings,
                query=query, display_name=display_name, decade=decade
            )
            self._sessions[chat_id] = session
            await session.start()

    async def stop(self, chat_id: int):
        async with self._get_lock(chat_id):
            if session := self._sessions.pop(chat_id, None): await session.stop()

    async def skip(self, chat_id: int):
        if session := self._sessions.get(chat_id): await session.skip()

    async def stop_all(self):
        for chat_id in list(self._sessions.keys()): await self.stop(chat_id)

    def _get_random_query(self) -> tuple[str, str, str]:
        """Gets a random query from the entire 3-level genre structure."""
        try:
            era_key = random.choice(list(self._settings.GENRE_DATA.keys()))
            era_data = self._settings.GENRE_DATA[era_key]
            
            subgenre_key = random.choice(list(era_data["subgenres"].keys()))
            subgenre_data = era_data["subgenres"][subgenre_key]

            decade_key = random.choice(list(subgenre_data["decades"].keys()))
            decade_data = subgenre_data["decades"][decade_key]
            
            query = decade_data["query"]
            display_name = f"{subgenre_data['name']} ({decade_data['name']})"
            
            return (query, decade_key, display_name)
        except Exception:
            logger.error("Failed to get random genre, using fallback.", exc_info=True)
            return ("80s synth pop", "1980s", "🎹 Synth-Pop (80-е)")
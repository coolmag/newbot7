import asyncio
import logging
import random
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field

from telegram import Bot
from telegram.constants import ParseMode

from config import Settings
from models import TrackInfo
from youtube import YouTubeDownloader, SearchMode

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
    
    # Internal State
    is_running: bool = field(init=False, default=False)
    playlist: List[TrackInfo] = field(default_factory=list)
    played_ids: Set[str] = field(default_factory=set)
    current_task: Optional[asyncio.Task] = None
    skip_event: asyncio.Event = field(default_factory=asyncio.Event)
    
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.current_task = asyncio.create_task(self._radio_loop())
        logger.info(f"[{self.chat_id}] Radio session started for query: '{self.query}'")

    async def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        if self.current_task:
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
        logger.info(f"[{self.chat_id}] Radio session stopped.")

    async def skip(self):
        self.skip_event.set()

    async def _fill_playlist(self):
        logger.info(f"[{self.chat_id}] Filling playlist for '{self.query}'...")
        try:
            tracks = await self.downloader.search(
                self.query, 
                search_mode=self.search_mode, 
                limit=50
            )
            new_tracks = [t for t in tracks if t.identifier not in self.played_ids]
            if new_tracks:
                random.shuffle(new_tracks)
                self.playlist.extend(new_tracks)
                logger.info(f"[{self.chat_id}] Added {len(new_tracks)} new tracks to playlist.")
            else:
                logger.warning(f"[{self.chat_id}] No new tracks found for '{self.query}'.")
        except Exception as e:
            logger.error(f"[{self.chat_id}] Error filling playlist: {e}", exc_info=True)

    async def _radio_loop(self):
        error_count = 0
        max_errors = 5
        
        while self.is_running:
            try:
                # Заполняем плейлист если мало треков
                if len(self.playlist) < 5:
                    await self._fill_playlist()
                
                if not self.playlist:
                    logger.warning(f"[{self.chat_id}] Playlist is empty. Stopping radio.")
                    try:
                        await self.bot.send_message(
                            self.chat_id, 
                            f"❌ Не удалось найти музыку по запросу '{self.query}'. Радио остановлено."
                        )
                    except Exception:
                        pass
                    break
                
                track = self.playlist.pop(0)
                self.played_ids.add(track.identifier)
                
                # Очищаем историю если слишком большая
                if len(self.played_ids) > 500:
                    self.played_ids.clear()

                success = await self._play_track(track)
                
                if success:
                    error_count = 0
                    # Ждём пропуск или таймаут
                    try:
                        await asyncio.wait_for(self.skip_event.wait(), timeout=90.0)
                        self.skip_event.clear()
                        logger.info(f"[{self.chat_id}] Track skipped by user.")
                    except asyncio.TimeoutError:
                        pass  # Нормальная ротация через 90 сек
                else:
                    error_count += 1
                    if error_count >= max_errors:
                        try:
                            await self.bot.send_message(
                                self.chat_id, 
                                "⚠️ Радио остановлено из-за множественных ошибок загрузки."
                            )
                        except Exception:
                            pass
                        break
                    await asyncio.sleep(2)
                
            except asyncio.CancelledError:
                logger.info(f"[{self.chat_id}] Radio loop cancelled.")
                break
            except Exception as e:
                logger.error(f"[{self.chat_id}] Unhandled error in radio loop: {e}", exc_info=True)
                error_count += 1
                if error_count >= max_errors:
                    try:
                        await self.bot.send_message(
                            self.chat_id, 
                            "⚠️ Радио остановлено из-за ошибок."
                        )
                    except Exception:
                        pass
                    break
                await asyncio.sleep(5)
        
        self.is_running = False
        logger.info(f"[{self.chat_id}] Radio loop finished.")

    async def _play_track(self, track: TrackInfo) -> bool:
        """Воспроизведение трека. Возвращает True при успехе."""
        result = None
        try:
            logger.info(f"[{self.chat_id}] Processing: {track.artist} - {track.title}")
            result = await self.downloader.download(track.identifier)
            
            if not result or not result.success:
                error_msg = result.error if result else 'Unknown error'
                logger.error(f"[{self.chat_id}] Download failed: {error_msg}")
                return False

            if not result.file_path or not result.file_path.exists():
                logger.error(f"[{self.chat_id}] Downloaded file not found")
                return False

            # Отправляем аудио
            with open(result.file_path, 'rb') as audio_file:
                await self.bot.send_audio(
                    chat_id=self.chat_id,
                    audio=audio_file,
                    title=track.title,
                    performer=track.artist,
                    duration=track.duration
                )
            
            logger.info(f"[{self.chat_id}] Successfully sent: {track.title}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.chat_id}] Failed to play {track.identifier}: {e}", exc_info=True)
            return False
        finally:
            # Очистка файла
            if result and result.file_path:
                try:
                    if result.file_path.exists():
                        result.file_path.unlink()
                except OSError as e:
                    logger.warning(f"[{self.chat_id}] Cleanup failed: {e}")


class RadioManager:
    def __init__(self, bot: Bot, settings: Settings, downloader: YouTubeDownloader):
        self._bot = bot
        self._settings = settings
        self._downloader = downloader
        self._sessions: Dict[int, RadioSession] = {}
        self._locks: Dict[int, asyncio.Lock] = {}

    def _get_lock(self, chat_id: int) -> asyncio.Lock:
        if chat_id not in self._locks:
            self._locks[chat_id] = asyncio.Lock()
        return self._locks[chat_id]

    async def start(self, chat_id: int, query: str, search_mode: SearchMode = 'genre', display_name: Optional[str] = None):
        async with self._get_lock(chat_id):
            # Останавливаем предыдущую сессию
            if chat_id in self._sessions:
                await self._sessions[chat_id].stop()
            
            # Обработка случайного жанра
            if query == "random":
                query, display_name = self._get_random_style_query()
            
            session = RadioSession(
                chat_id=chat_id,
                bot=self._bot,
                downloader=self._downloader,
                settings=self._settings,
                query=query,
                search_mode=search_mode,
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
        """Остановка всех сессий"""
        for chat_id in list(self._sessions.keys()):
            try:
                await self.stop(chat_id)
            except Exception as e:
                logger.error(f"Error stopping session {chat_id}: {e}")

    def is_playing(self, chat_id: int) -> bool:
        session = self._sessions.get(chat_id)
        return session is not None and session.is_running

    def _get_random_style_query(self) -> tuple[str, str]:
        """Получение случайного жанра"""
        try:
            genres_data = self._settings.GENRE_DATA
            if not genres_data:
                return "lofi hip hop beats", "Lo-Fi"
            
            # Выбираем случайный основной жанр
            main_key = random.choice(list(genres_data.keys()))
            main_genre = genres_data[main_key]
            
            # Выбираем случайный поджанр
            subgenres = main_genre.get("subgenres", {})
            if subgenres:
                sub_key = random.choice(list(subgenres.keys()))
                sub_genre = subgenres[sub_key]
                query = sub_genre.get("query", f"{main_key} {sub_key}")
                display_name = f"{sub_genre.get('icon', '')} {sub_genre.get('name', sub_key)}"
            else:
                query = main_genre.get("query", main_key)
                display_name = f"{main_genre.get('icon', '')} {main_genre.get('name', main_key)}"
            
            return query, display_name
        except Exception as e:
            logger.error(f"Error getting random genre: {e}")
            return "lofi hip hop beats", "Lo-Fi"

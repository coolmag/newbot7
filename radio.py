import asyncio
import logging
import random
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field
from datetime import datetime

from telegram import Bot, Message
from telegram.constants import ParseMode
from telegram.error import BadRequest

from config import Settings
from models import TrackInfo
from youtube import YouTubeDownloader, SearchMode

logger = logging.getLogger("radio")


# ═══════════════════════════════════════════════════════════════
# 🌌 КОСМИЧЕСКИЕ ТЕМЫ ДЛЯ СТАТУС-БАРА
# ═══════════════════════════════════════════════════════════════

COSMIC_THEMES = {
    "search": [
        "🛸 Сканирую галактику...",
        "🌌 Исследую туманности...",
        "✨ Ловлю космические волны...",
        "🔭 Настраиваю антенны...",
        "💫 Синхронизация с орбитой...",
        "🌠 Перехватываю сигналы...",
        "🚀 Запуск поисковых зондов...",
        "⚡ Активация гиперпривода...",
    ],
    "loading": [
        "📡 Загрузка аудиопотока...",
        "🌍 Приём данных с орбиты...",
        "💿 Декодирование сигнала...",
        "🎛️ Калибровка частот...",
        "🔊 Усиление сигнала...",
    ],
    "playing": [
        "🎧", "🎵", "🎶", "🔊", "📻", "💿", "🎹", "🎸"
    ]
}


def get_progress_bar(percent: int, length: int = 15) -> str:
    """Создаёт космический прогресс-бар"""
    filled = int(length * percent / 100)
    empty = length - filled
    
    styles = [
        ("▓", "░"),
        ("█", "░"),
        ("◉", "○"),
        ("●", "○"),
    ]
    fill_char, empty_char = random.choice(styles)
    
    bar = fill_char * filled + empty_char * empty
    return f"[{bar}]"


def format_duration(seconds: int) -> str:
    """Форматирует длительность"""
    mins, secs = divmod(seconds, 60)
    return f"{mins}:{secs:02d}"


def get_now_playing_message(track: TrackInfo, genre_name: str = "") -> str:
    """Компактное сообщение о текущем треке"""
    icon = random.choice(["🎧", "🎵", "🎶", "📻", "💿"])
    stars = "".join(random.choices(["✧", "✦", "⋆", "·"], k=5))
    
    title = track.title[:40] if len(track.title) > 40 else track.title
    artist = track.artist[:30] if len(track.artist) > 30 else track.artist
    duration = format_duration(track.duration)
    wave = genre_name if genre_name else "Cosmic Waves"
    
    return (
        f"{stars} {icon} NOW PLAYING {icon} {stars}\n\n"
        f"🎵 *{title}*\n"
        f"👤 {artist}\n"
        f"⏱ {duration}\n\n"
        f"📻 _{wave}_"
    )


# ═══════════════════════════════════════════════════════════════
# 🎛️ РАДИО СЕССИЯ
# ═══════════════════════════════════════════════════════════════

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
    status_message: Optional[Message] = None
    tracks_played: int = field(init=False, default=0)
    
    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.tracks_played = 0
        self.current_task = asyncio.create_task(self._radio_loop())
        logger.info(f"[{self.chat_id}] 🚀 Radio started: '{self.query}'")

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
        await self._delete_status()
        logger.info(f"[{self.chat_id}] 🛑 Radio stopped. Played {self.tracks_played} tracks.")

    async def skip(self):
        self.skip_event.set()

    async def _update_status(self, text: str, parse_mode: str = None):
        """Обновляет или создаёт статус-сообщение"""
        try:
            if self.status_message:
                try:
                    await self.status_message.edit_text(text, parse_mode=parse_mode)
                    return
                except BadRequest:
                    self.status_message = None
            
            self.status_message = await self.bot.send_message(
                self.chat_id, text, parse_mode=parse_mode
            )
        except Exception as e:
            logger.warning(f"[{self.chat_id}] Status update error: {e}")

    async def _delete_status(self):
        """Удаляет статус-сообщение"""
        if self.status_message:
            try:
                await self.status_message.delete()
            except Exception:
                pass
            self.status_message = None

    async def _fill_playlist(self):
        """Заполняет плейлист"""
        search_msg = random.choice(COSMIC_THEMES["search"])
        status_text = f"{search_msg}\n\n🔍 Запрос: _{self.query}_ "
        await self._update_status(status_text, ParseMode.MARKDOWN)
        
        logger.info(f"[{self.chat_id}] 🔍 Searching: '{self.query}'")
        
        try:
            tracks = await self.downloader.search(
                self.query, 
                search_mode=self.search_mode, 
                limit=30
            )
            
            new_tracks = [t for t in tracks if t.identifier not in self.played_ids]
            
            if new_tracks:
                random.shuffle(new_tracks)
                self.playlist.extend(new_tracks)
                logger.info(f"[{self.chat_id}] ✅ Added {len(new_tracks)} tracks")
                await self._update_status(
                    f"✅ Найдено {len(new_tracks)} треков!\n\n🎵 Запускаю воспроизведение..."
                )
            else:
                logger.warning(f"[{self.chat_id}] ⚠️ No new tracks for '{self.query}'")
                
                # Fallback с упрощённым запросом
                if " " in self.query:
                    simple_query = self.query.split()[0] + " music"
                    logger.info(f"[{self.chat_id}] 🔄 Trying fallback: '{simple_query}'")
                    
                    tracks = await self.downloader.search(simple_query, 'genre', 20)
                    new_tracks = [t for t in tracks if t.identifier not in self.played_ids]
                    
                    if new_tracks:
                        random.shuffle(new_tracks)
                        self.playlist.extend(new_tracks)
                        logger.info(f"[{self.chat_id}] ✅ Fallback found {len(new_tracks)} tracks")
                        
        except Exception as e:
            logger.error(f"[{self.chat_id}] ❌ Search error: {e}", exc_info=True)

    async def _radio_loop(self):
        """Основной цикл радио"""
        error_count = 0
        max_errors = 5
        
        # Начальное сообщение
        start_text = (
            f"📻 *Запускаю радио*\n\n"
            f"🎵 Волна: _{self.display_name or self.query}_\n"
            f"🌌 Настройка частоты..."
        )
        await self._update_status(start_text, ParseMode.MARKDOWN)
        
        while self.is_running:
            try:
                # Заполняем плейлист
                if len(self.playlist) < 3:
                    await self._fill_playlist()
                
                if not self.playlist:
                    logger.error(f"[{self.chat_id}] ❌ Empty playlist")
                    error_text = (
                        f"❌ *Не удалось найти музыку*\n\n"
                        f"Запрос: _{self.query}_\n"
                        f"Попробуйте другой жанр."
                    )
                    await self._update_status(error_text, ParseMode.MARKDOWN)
                    break
                
                # Берём следующий трек
                track = self.playlist.pop(0)
                self.played_ids.add(track.identifier)
                
                # Чистим историю
                if len(self.played_ids) > 200:
                    oldest = list(self.played_ids)[:100]
                    for old_id in oldest:
                        self.played_ids.discard(old_id)

                # Проигрываем трек
                success = await self._play_track(track)
                
                if success:
                    error_count = 0
                    self.tracks_played += 1
                    
                    # Ждём skip или таймаут
                    try:
                        wait_time = float(track.duration + 10) if track.duration > 0 else 180.0
                        await asyncio.wait_for(self.skip_event.wait(), timeout=wait_time)
                        self.skip_event.clear()
                        logger.info(f"[{self.chat_id}] ⏭️ Skipped by user")
                    except asyncio.TimeoutError:
                        pass
                else:
                    error_count += 1
                    logger.warning(f"[{self.chat_id}] ⚠️ Error count: {error_count}/{max_errors}")
                    
                    if error_count >= max_errors:
                        stop_text = (
                            "❌ *Радио остановлено*\n\n"
                            "Слишком много ошибок загрузки.\n"
                            "Попробуйте позже или выберите другой жанр.",
                            ParseMode.MARKDOWN
                        )
                        await self._update_status(stop_text, ParseMode.MARKDOWN)
                        break
                    
                    await asyncio.sleep(2)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.chat_id}] ❌ Loop error: {e}", exc_info=True)
                error_count += 1
                if error_count >= max_errors:
                    break
                await asyncio.sleep(3)
        
        self.is_running = False
        logger.info(f"[{self.chat_id}] 🏁 Radio loop finished")

    async def _play_track(self, track: TrackInfo) -> bool:
        """Воспроизводит один трек"""
        result = None
        
        try:
            # Статус загрузки
            loading_msg = random.choice(COSMIC_THEMES["loading"])
            title_short = track.title[:35] + "..." if len(track.title) > 35 else track.title
            
            loading_text = f"{loading_msg}\n\n🎵 _{title_short}_\n👤 {track.artist}"
            await self._update_status(loading_text, ParseMode.MARKDOWN)
            
            logger.info(f"[{self.chat_id}] 📥 Downloading: {track.title}")
            
            # Скачиваем
            result = await self.downloader.download(track.identifier)
            
            if not result or not result.success:
                error = result.error if result else "Unknown"
                logger.error(f"[{self.chat_id}] ❌ Download failed: {error}")
                return False
            
            if not result.file_path or not result.file_path.exists():
                logger.error(f"[{self.chat_id}] ❌ File not found")
                return False
            
            # Отправляем аудио
            logger.info(f"[{self.chat_id}] 📤 Sending: {track.title}")
            
            caption = get_now_playing_message(track, self.display_name)
            
            with open(result.file_path, 'rb') as audio_file:
                await self.bot.send_audio(
                    chat_id=self.chat_id,
                    audio=audio_file,
                    title=track.title,
                    performer=track.artist,
                    duration=track.duration,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Удаляем статус после успешной отправки
            await self._delete_status()
            
            logger.info(f"[{self.chat_id}] ✅ Sent: {track.title}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.chat_id}] ❌ Play error: {e}", exc_info=True)
            return False
            
        finally:
            # Чистим файл
            if result and result.file_path:
                try:
                    if result.file_path.exists():
                        result.file_path.unlink()
                except Exception as e:
                    logger.warning(f"Cleanup error: {e}")


# ═══════════════════════════════════════════════════════════════
# 📻 МЕНЕДЖЕР РАДИО
# ═══════════════════════════════════════════════════════════════

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

    async def start(
        self, 
        chat_id: int, 
        query: str, 
        search_mode: SearchMode = 'genre', 
        display_name: Optional[str] = None
    ):
        async with self._get_lock(chat_id):
            # Стоп предыдущей сессии
            if chat_id in self._sessions:
                await self._sessions[chat_id].stop()
            
            # Random жанр
            if query == "random":
                query, display_name = self._get_random_style_query()
            
            # Стартовое сообщение
            start_msg = random.choice(COSMIC_THEMES["search"])
            wave_name = display_name if display_name else query
            await self._bot.send_message(
                chat_id,
                f"{start_msg}\n\n🎧 Волна: *{wave_name}*",
                parse_mode=ParseMode.MARKDOWN
            )
            
            session = RadioSession(
                chat_id=chat_id,
                bot=self._bot,
                downloader=self._downloader,
                settings=self._settings,
                query=query,
                search_mode=search_mode,
                display_name=display_name if display_name else query
            )
            
            self._sessions[chat_id] = session
            await session.start()

    async def stop(self, chat_id: int):
        async with self._get_lock(chat_id):
            session = self._sessions.pop(chat_id, None)
            if session:
                await session.stop()

    async def skip(self, chat_id: int):
        session = self._sessions.get(chat_id)
        if session:
            await session.skip()

    async def stop_all(self):
        for chat_id in list(self._sessions.keys()):
            try:
                await self.stop(chat_id)
            except Exception as e:
                logger.error(f"Stop error for {chat_id}: {e}")

    def is_playing(self, chat_id: int) -> bool:
        session = self._sessions.get(chat_id)
        return session is not None and session.is_running

    def _get_random_style_query(self) -> tuple:
        """Случайный жанр из конфига"""
        try:
            genres = self._settings.GENRE_DATA
            if not genres:
                return ("lofi hip hop", "Lo-Fi")
            
            main_key = random.choice(list(genres.keys()))
            main = genres[main_key]
            
            subs = main.get("subgenres", {})
            if subs:
                sub_key = random.choice(list(subs.keys()))
                sub = subs[sub_key]
                query = sub.get("query", f"{main_key} {sub_key}")
                icon = sub.get("icon", "🎵")
                name = sub.get("name", sub_key)
                display = f"{icon} {name}"
            else:
                query = main.get("query", main_key)
                icon = main.get("icon", "🎵")
                name = main.get("name", main_key)
                display = f"{icon} {name}"
            
            return (query, display)
            
        except Exception as e:
            logger.error(f"Random genre error: {e}")
            return ("lofi hip hop beats", "🎧 Lo-Fi")
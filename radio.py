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
    
    # Разные стили прогресс-бара
    styles = [
        ("▓", "░"),
        ("█", "░"),
        ("◉", "○"),
        ("⬢", "⬡"),
        ("●", "○"),
    ]
    fill_char, empty_char = random.choice(styles)
    
    bar = fill_char * filled + empty_char * empty
    return f"[{bar}]"

def format_duration(seconds: int) -> str:
    """Форматирует длительность"""
    mins, secs = divmod(seconds, 60)
    return f"{mins}:{secs:02d}"

def get_cosmic_status(track: TrackInfo, genre_name: str = "") -> str:
    """Генерирует космический статус для трека"""
    icon = random.choice(COSMIC_THEMES["playing"])
    
    # Случайные эффекты
    effects = ["✧", "✦", "⋆", "★", "☆", "·", "•", "◦"]
    left_effect = "".join(random.choices(effects, k=3))
    right_effect = "".join(random.choices(effects, k=3))
    
    # Случайный прогресс для визуального эффекта
    progress = get_progress_bar(random.randint(20, 80))
    
    status = f"""
{left_effect} {icon} CYBER RADIO {icon} {right_effect}

╔══════════════════════════════════╗
║  🎵 {track.title[:30]}{'...' if len(track.title) > 30 else ''}
║  👤 {track.artist[:25]}{'...' if len(track.artist) > 25 else ''}
║  ⏱ {format_duration(track.duration)}
╚══════════════════════════════════╝

{progress}

📻 Волна: {genre_name or "Random Mix"}
🌌 Частота: {random.randint(88, 108)}.{random.randint(0, 9)} MHz
"""
    return status.strip()

def get_now_playing_message(track: TrackInfo, genre_name: str = "") -> str:
    """Компактное сообщение о текущем треке"""
    icon = random.choice(["🎧", "🎵", "🎶", "📻", "💿"])
    stars = "".join(random.choices(["✧", "✦", "⋆", "·"], k=5))
    
    return f"""{stars} {icon} NOW PLAYING {icon} {stars}

🎵 *{track.title}*
👤 {track.artist}
⏱ {format_duration(track.duration)}

📻 _{genre_name or "Cosmic Waves"}_"""


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
                except BadRequest:
                    # Сообщение не изменилось или удалено
                    self.status_message = None
            
            if not self.status_message:
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
            except:
                pass
            self.status_message = None

    async def _fill_playlist(self):
        """Заполняет плейлист"""
        search_msg = random.choice(COSMIC_THEMES["search"])
        await self._update_status(f"{search_msg}\n\n🔍 Запрос: _{self.query}_", ParseMode.MARKDOWN)
        
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
                
                # Пробуем упрощённый запрос
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
        await self._update_status(
            f"📻 *Запускаю радио*\n\n"
            f"🎵 Волна: _{self.display_name or self.query}_\n"
            f"🌌 Настройка частоты...",
            ParseMode.MARKDOWN
        )
        
        while self.is_running:
            try:
                # Заполняем плейлист
                if len(self.playlist) < 3:
                    await self._fill_playlist()
                
                if not self.playlist:
                    logger.error(f"[{self.chat_id}] ❌ Empty playlist")
                    await self._update_status(
                        f"❌ *Не удалось найти музыку*\n\n"
                        f"Запрос: _{self.display_name or self.query}_\n"
                        f"Попробуйте другой жанр.",
                        ParseMode.MARKDOWN
                    )
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
                        await asyncio.wait_for(
                            self.skip_event.wait(), 
                            timeout=float(track.duration + 10)  # длина трека + буфер
                        )
                        self.skip_event.clear()
                        logger.info(f"[{self.chat_id}] ⏭️ Skipped by user")
                    except asyncio.TimeoutError:
                        pass
                else:
                    error_count += 1
                    logger.warning(f"[{self.chat_id}] ⚠️ Error count: {error_count}/{max_errors}")
                    
                    if error_count >= max_errors:
                        await self._update_status(
                            "❌ *Радио остановлено*\n\n"
                            "Слишком много ошибок загрузки.\n"
                            "Попробуйте позже или выберите другой жанр.",
                            ParseMode.MARKDOWN
                        )
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
            await self._update_status(
                f"{loading_msg}\n\n"
                f"🎵 _{track.title}_
"
                f"👤 {track.artist}",
                ParseMode.MARKDOWN
            )
            
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
            
            with open(result.file_path, 'rb') as audio_file:
                await self.bot.send_audio(
                    chat_id=self.chat_id,
                    audio=audio_file,
                    title=track.title,
                    performer=track.artist,
                    duration=track.duration,
                    caption=get_now_playing_message(track, self.display_name),
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Обновляем статус
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
            # Стоп предыдущей
            if chat_id in self._sessions:
                await self._sessions[chat_id].stop()
            
            # Random жанр
            if query == "random":
                query, display_name = self._get_random_style_query()
            
            # Стартовое сообщение
            start_msg = random.choice(COSMIC_THEMES["search"])
            await self._bot.send_message(
                chat_id,
                f"{start_msg}\n\n🎧 Волна: *{display_name or query}*",
                parse_mode=ParseMode.MARKDOWN
            )
            
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
        for chat_id in list(self._sessions.keys()):
            try:
                await self.stop(chat_id)
            except Exception as e:
                logger.error(f"Stop error for {chat_id}: {e}")

    def is_playing(self, chat_id: int) -> bool:
        session = self._sessions.get(chat_id)
        return session is not None and session.is_running

    def _get_random_style_query(self) -> tuple[str, str]:
        """Случайный жанр из конфига"""
        try:
            genres = self._settings.GENRE_DATA
            if not genres:
                return "lofi hip hop", "Lo-Fi"
            
            main_key = random.choice(list(genres.keys()))
            main = genres[main_key]
            
            subs = main.get("subgenres", {})
            if subs:
                sub_key = random.choice(list(subs.keys()))
                sub = subs[sub_key]
                query = sub.get("query", f"{main_key} {sub_key}")
                name = f"{sub.get('icon', '🎵')} {sub.get('name', sub_key)}"
            else:
                query = main.get("query", main_key)
                name = f"{main.get('icon', '🎵')} {main.get('name', main_key)}"
            
            logger.debug(f"Random genre selected: '{name}' with query '{query}'")
            return query, name
            
        except Exception as e:
            logger.error(f"Random genre error: {e}")
            return "lofi hip hop beats", "🎧 Lo-Fi"

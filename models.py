from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Dict


class Source(Enum):
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"


class CallbackAction:
    """Константы для callback actions"""
    PLAY = "play"
    DOWNLOAD = "dl"
    SKIP = "skip"
    STOP = "stop"
    VOTE = "vote"
    PAGE = "page"
    SELECT = "sel"
    SEARCH = "search"
    CANCEL = "cancel"
    CONFIRM = "confirm"
    
    # New actions for Era -> Subgenre -> Decade flow
    ERA = "era"
    SUBGENRE = "sub"
    DECADE = "dec"


@dataclass
class VoteCallback:
    """Callback data для кнопок. Упрощенная и надежная версия."""
    action: str
    value: str
    
    SEP: str = field(default=":", init=False, repr=False)
    
    def to_callback_data(self) -> str:
        """Сериализация в строку для callback_data (max 64 bytes)"""
        data = f"{self.action}{self.SEP}{self.value}"
        
        # Обрезаем если слишком длинно (Telegram limit = 64 bytes)
        if len(data.encode('utf-8')) > 64:
            # Укорачиваем value до максимально возможной длины
            value_bytes = self.value.encode('utf-8')
            max_value_bytes = 64 - len(self.action.encode('utf-8')) - len(self.SEP.encode('utf-8'))
            
            if max_value_bytes < 0:
                max_value_bytes = 0

            # Find the largest possible string that fits
            end = len(value_bytes)
            while len(value_bytes[:end]) > max_value_bytes:
                end -= 1
            
            value_truncated = value_bytes[:end].decode('utf-8', 'ignore')
            data = f"{self.action}{self.SEP}{value_truncated}"
        
        return data
    
    @classmethod
    def from_callback_data(cls, data: str) -> Optional["VoteCallback"]:
        """Десериализация из callback_data. Разделяет только по первому ':'."""
        if not data:
            return None
        
        parts = data.split(cls.SEP, 1)
        if len(parts) != 2:
            return None
        
        return cls(action=parts[0], value=parts[1])
    
    def __str__(self) -> str:
        return self.to_callback_data()


@dataclass
class TrackInfo:
    identifier: str
    title: str
    artist: str
    duration: int
    source: Source = Source.YOUTUBE
    thumbnail_url: Optional[str] = None
    
    @classmethod
    def from_yt_info(cls, info: Dict[str, Any]) -> Optional["TrackInfo"]:
        """Создание TrackInfo из информации yt-dlp"""
        if not info:
            return None
        
        # Получаем video_id
        video_id = info.get('id')
        if not video_id:
            url = info.get('url', '')
            if 'watch?v=' in url:
                video_id = url.split('watch?v=')[-1].split('&')[0]
            elif 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[-1].split('?')[0]
        
        if not video_id:
            return None
        
        title = info.get('title', 'Unknown')
        
        # Получаем артиста (пробуем разные поля)
        artist = (
            info.get('artist') or 
            info.get('creator') or
            info.get('uploader') or 
            info.get('channel') or 
            'Unknown'
        )
        
        # Получаем длительность
        duration = info.get('duration') or 0
        if duration is None:
            duration = 0
        
        # Получаем миниатюру
        thumbnail = info.get('thumbnail')
        
        # Парсим исполнителя и название из заголовка, если нужно
        if " - " in title and artist in ["Unknown", "Various Artists"]:
            try:
                parts = title.split(" - ", 1)
                artist_candidate = parts[0].strip()
                title_candidate = parts[1].strip()
                # Простая эвристика, чтобы не парсить неверно
                if 0 < len(artist_candidate) < 50:
                    artist = artist_candidate
                    title = title_candidate
            except Exception:
                pass # Оставляем как есть в случае ошибки
        
        return cls(
            identifier=video_id,
            title=title,
            artist=artist,
            duration=int(duration),
            source=Source.YOUTUBE,
            thumbnail_url=thumbnail
        )


@dataclass
class DownloadResult:
    success: bool
    file_path: Optional[Path] = None
    file_id: Optional[str] = None
    track_info: Optional[TrackInfo] = None
    error: Optional[str] = None


@dataclass
class SearchResult:
    """Результат поиска"""
    query: str
    tracks: list  # List[TrackInfo]
    total: int = 0
    page: int = 1
    has_more: bool = False


@dataclass 
class RadioState:
    """Состояние радио для чата"""
    chat_id: int
    genre: str
    is_playing: bool = False
    current_track: Optional[TrackInfo] = None
    queue_size: int = 0
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Dict

class Source(Enum):
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"

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
        
        video_id = info.get('id') or info.get('url', '').split('=')[-1]
        if not video_id:
            return None
        
        title = info.get('title', 'Unknown')
        
        # Получаем артиста
        artist = info.get('artist') or info.get('uploader') or info.get('channel') or 'Unknown'
        
        # Получаем длительность
        duration = info.get('duration', 0)
        if duration is None:
            duration = 0
        
        # Получаем миниатюру
        thumbnail = info.get('thumbnail')
        
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
    track_info: Optional[TrackInfo] = None
    error: Optional[str] = None


@dataclass
class VoteCallback:
    """Callback data для кнопок голосования/выбора"""
    action: str  # Тип действия: "vote", "select", "genre", "play", "skip", etc.
    value: str   # Значение: ID трека, название жанра и т.д.
    extra: Optional[str] = None  # Дополнительные данные
    
    # Разделитель для сериализации
    SEP: str = field(default=":", init=False, repr=False)
    
    def to_callback_data(self) -> str:
        """Сериализация в строку для callback_data"""
        if self.extra:
            return f"{self.action}{self.SEP}{self.value}{self.SEP}{self.extra}"
        return f"{self.action}{self.SEP}{self.value}"
    
    @classmethod
    def from_callback_data(cls, data: str) -> Optional["VoteCallback"]:
        """Десериализация из callback_data"""
        if not data:
            return None
        
        parts = data.split(":")
        if len(parts) < 2:
            return None
        
        action = parts[0]
        value = parts[1]
        extra = parts[2] if len(parts) > 2 else None
        
        return cls(action=action, value=value, extra=extra)
    
    def __str__(self) -> str:
        return self.to_callback_data()


# Предопределённые actions для удобства
class CallbackAction:
    PLAY = "play"
    DOWNLOAD = "dl"
    SKIP = "skip"
    STOP = "stop"
    VOTE = "vote"
    GENRE = "genre"
    PAGE = "page"
    SELECT = "sel"
    RADIO = "radio"
    SEARCH = "search"
    CANCEL = "cancel"
    CONFIRM = "confirm"


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
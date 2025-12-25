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
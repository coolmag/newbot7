from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Any, Dict


class Source(Enum):
    YOUTUBE = "youtube"
    SPOTIFY = "spotify"
    SOUNDCLOUD = "soundcloud"


class CallbackAction:
    NAVIGATE = "nav"
    START_RADIO = "radio"
    SEARCH_ARTIST = "s_art"
    SEARCH_TRACK = "s_trk"
    
    PLAY = "play"
    DOWNLOAD = "dl"
    SKIP = "skip"
    STOP = "stop"
    
    PAGE = "page"
    SELECT = "sel"
    CANCEL = "cancel"
    CONFIRM = "confirm"


@dataclass
class VoteCallback:
    action: str
    value: str
    SEP: str = field(default=":", init=False, repr=False)
    
    def to_callback_data(self) -> str:
        data = f"{self.action}{self.SEP}{self.value}"
        if len(data.encode('utf-8')) > 64:
            value_bytes = self.value.encode('utf-8')
            max_value_bytes = 64 - len(self.action.encode('utf-8')) - len(self.SEP.encode('utf-8'))
            if max_value_bytes < 0: max_value_bytes = 0
            end = len(value_bytes)
            while len(value_bytes[:end]) > max_value_bytes: end -= 1
            value_truncated = value_bytes[:end].decode('utf-8', 'ignore')
            data = f"{self.action}{self.SEP}{value_truncated}"
        return data
    
    @classmethod
    def from_callback_data(cls, data: str) -> Optional["VoteCallback"]:
        if not data: return None
        parts = data.split(cls.SEP, 1)
        if len(parts) != 2: return None
        return cls(action=parts[0], value=parts[1])


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
        if not info: return None
        video_id = info.get('id')
        if not video_id:
            url = info.get('url', '')
            if 'watch?v=' in url: video_id = url.split('watch?v=')[-1].split('&')[0]
            elif 'youtu.be/' in url: video_id = url.split('youtu.be/')[-1].split('?')[0]
        if not video_id: return None
        title = info.get('title', 'Unknown')
        artist = (info.get('artist') or info.get('creator') or info.get('uploader') or info.get('channel') or 'Unknown')
        duration = info.get('duration') or 0
        if duration is None: duration = 0
        thumbnail = info.get('thumbnail')
        if " - " in title and artist in ["Unknown", "Various Artists"]:
            try:
                parts = title.split(" - ", 1)
                artist, title = parts[0].strip(), parts[1].strip()
            except Exception: pass
        return cls(identifier=video_id, title=title, artist=artist, duration=int(duration), source=Source.YOUTUBE, thumbnail_url=thumbnail)


@dataclass
class DownloadResult:
    success: bool
    file_path: Optional[Path] = None
    file_id: Optional[str] = None
    track_info: Optional[TrackInfo] = None
    error_message: Optional[str] = None


@dataclass
class SearchResult:
    query: str
    tracks: list
    total: int = 0
    page: int = 1
    has_more: bool = False

@dataclass 
class RadioState:
    chat_id: int
    genre: str
    is_playing: bool = False
    current_track: Optional[TrackInfo] = None
    queue_size: int = 0
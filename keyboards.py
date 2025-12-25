from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.constants import ChatType
import logging
from typing import List, Dict
from models import VoteCallback, TrackInfo, CallbackAction


logger = logging.getLogger(__name__)

def get_track_search_keyboard(tracks: List[TrackInfo]) -> InlineKeyboardMarkup:
    """
    Creates a keyboard with a list of tracks for the user to choose from.
    Uses VoteCallback for consistent callback data.
    """
    if not tracks:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data=VoteCallback(action=CallbackAction.CANCEL, value="search").to_callback_data())
        ]])
    
    buttons = []
    for i, track in enumerate(tracks[:10], 1):
        callback_data = VoteCallback(action=CallbackAction.SELECT, value=track.identifier).to_callback_data()
        if len(callback_data.encode('utf-8')) <= 64:
            buttons.append(InlineKeyboardButton(text=str(i), callback_data=callback_data))
        else:
            logger.warning(f"Skipped track with long ID: {track.identifier}")
    
    if not buttons:
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Ошибка", callback_data=VoteCallback(action=CallbackAction.CANCEL, value="search").to_callback_data())
        ]])
    
    keyboard = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data=VoteCallback(action=CallbackAction.CANCEL, value="search").to_callback_data())])
    
    return InlineKeyboardMarkup(keyboard)

def get_dashboard_keyboard(base_url: str, chat_type: str, chat_id: int) -> InlineKeyboardMarkup:
    """Creates the main dashboard keyboard with webapp and controls."""
    webapp_url = f"{base_url}/webapp/?chat_id={chat_id}"
    
    if chat_type == ChatType.PRIVATE:
        webapp_btn = InlineKeyboardButton("✨ ОТКРЫТЬ WINAMP ✨", web_app=WebAppInfo(url=webapp_url))
    else:
        webapp_btn = InlineKeyboardButton("✨ ОТКРЫТЬ WINAMP ✨", url=webapp_url)

    keyboard = [
        [webapp_btn],
        [
            InlineKeyboardButton("⏹️ Стоп", callback_data=VoteCallback(action=CallbackAction.STOP, value="radio").to_callback_data()),
            InlineKeyboardButton("⏭️ Скип", callback_data=VoteCallback(action=CallbackAction.SKIP, value="track").to_callback_data()),
        ],
        [
            InlineKeyboardButton("📂 Каталог жанров", callback_data=VoteCallback(action=CallbackAction.GENRE, value="main_menu").to_callback_data()),
            InlineKeyboardButton("🗳️ Голосование", callback_data=VoteCallback(action=CallbackAction.VOTE, value="show").to_callback_data())
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_track_keyboard(base_url: str, chat_id: int) -> InlineKeyboardMarkup:
    """Creates a simple keyboard to open the web player."""
    webapp_url = f"{base_url}/webapp/?chat_id={chat_id}"
    btn = InlineKeyboardButton("🎧 Открыть плеер", url=webapp_url)
    return InlineKeyboardMarkup([[btn]])

def get_genre_voting_keyboard(genres_for_voting: List[str], votes: Dict[str, set] = None) -> InlineKeyboardMarkup:
    """
    Creates the keyboard for genre voting.
    Shows the vote count for each genre.
    """
    if votes is None:
        votes = {}

    buttons = []
    for genre in genres_for_voting:
        vote_count = len(votes.get(genre, []))
        text = f"{genre.capitalize()}"
        if vote_count > 0:
            text += f" [{vote_count}]"
        
        callback_data = VoteCallback(action=CallbackAction.VOTE, value=genre).to_callback_data()
        buttons.append(InlineKeyboardButton(text=text, callback_data=callback_data))

    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(keyboard)

from typing import List, Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from models import TrackInfo, VoteCallback, CallbackAction


def get_track_search_keyboard(tracks: List[TrackInfo], page: int = 1) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с результатами поиска треков.
    Каждая кнопка позволяет выбрать трек для воспроизведения.
    """
    buttons = []
    
    for i, track in enumerate(tracks, 1):
        # Формируем текст кнопки (укороченный если слишком длинный)
        title = track.title[:30] + "..." if len(track.title) > 30 else track.title
        artist = track.artist[:20] + "..." if len(track.artist) > 20 else track.artist
        duration_str = f"{track.duration // 60}:{track.duration % 60:02d}"
        
        button_text = f"{i}. {artist} - {title} ({duration_str})"
        
        # Callback data для выбора трека
        callback = VoteCallback(
            action=CallbackAction.SELECT,
            value=track.identifier
        )
        
        buttons.append([
            InlineKeyboardButton(button_text, callback_data=callback.to_callback_data())
        ])
    
    # Добавляем кнопку отмены
    cancel_callback = VoteCallback(action=CallbackAction.CANCEL, value="search")
    buttons.append([
        InlineKeyboardButton("❌ Закрыть", callback_data=cancel_callback.to_callback_data())
    ])
    
    return InlineKeyboardMarkup(buttons)


def get_genre_voting_keyboard(genres: List[dict]) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для голосования за жанры.
    """
    buttons = []
    
    for genre in genres:
        genre_id = genre.get('id', genre.get('key', ''))
        genre_name = genre.get('name', genre_id)
        genre_icon = genre.get('icon', '🎵')
        
        callback = VoteCallback(
            action=CallbackAction.VOTE,
            value=genre_id
        )
        
        buttons.append(
            InlineKeyboardButton(
                f"{genre_icon} {genre_name}",
                callback_data=callback.to_callback_data()
            )
        )
    
    # Располагаем кнопки по 2 в ряд
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    
    # Добавляем кнопку случайного выбора
    random_callback = VoteCallback(action=CallbackAction.RADIO, value="random:mix")
    keyboard.append([
        InlineKeyboardButton("🎲 Случайный жанр", callback_data=random_callback.to_callback_data())
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_radio_control_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру управления радио.
    """
    skip_callback = VoteCallback(action=CallbackAction.SKIP, value=str(chat_id))
    stop_callback = VoteCallback(action=CallbackAction.STOP, value=str(chat_id))
    
    keyboard = [
        [
            InlineKeyboardButton("⏭️ Пропустить", callback_data=skip_callback.to_callback_data()),
            InlineKeyboardButton("⏹️ Стоп", callback_data=stop_callback.to_callback_data()),
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_now_playing_keyboard(track: TrackInfo) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру для текущего трека.
    """
    skip_callback = VoteCallback(action=CallbackAction.SKIP, value=track.identifier)
    stop_callback = VoteCallback(action=CallbackAction.STOP, value="radio")
    
    keyboard = [
        [
            InlineKeyboardButton("⏭️ Пропустить", callback_data=skip_callback.to_callback_data()),
            InlineKeyboardButton("⏹️ Остановить", callback_data=stop_callback.to_callback_data()),
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_confirmation_keyboard(action: str, value: str) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру подтверждения действия.
    """
    confirm_callback = VoteCallback(action=CallbackAction.CONFIRM, value=value, extra=action)
    cancel_callback = VoteCallback(action=CallbackAction.CANCEL, value=action)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data=confirm_callback.to_callback_data()),
            InlineKeyboardButton("❌ Нет", callback_data=cancel_callback.to_callback_data()),
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_pagination_keyboard(
    current_page: int, 
    total_pages: int, 
    base_action: str,
    base_value: str
) -> List[InlineKeyboardButton]:
    """
    Создаёт кнопки пагинации.
    Возвращает список кнопок для добавления в клавиатуру.
    """
    buttons = []
    
    if current_page > 1:
        prev_callback = VoteCallback(
            action=CallbackAction.PAGE,
            value=base_value,
            extra=str(current_page - 1)
        )
        buttons.append(
            InlineKeyboardButton("◀️ Назад", callback_data=prev_callback.to_callback_data())
        )
    
    buttons.append(
        InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop")
    )
    
    if current_page < total_pages:
        next_callback = VoteCallback(
            action=CallbackAction.PAGE,
            value=base_value,
            extra=str(current_page + 1)
        )
        buttons.append(
            InlineKeyboardButton("▶️ Вперёд", callback_data=next_callback.to_callback_data())
        )
    
    return buttons
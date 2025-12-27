from typing import List, Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from models import TrackInfo, VoteCallback, CallbackAction

def get_track_search_keyboard(tracks: List[TrackInfo], page: int = 1) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с результатами поиска треков."""
    buttons = []
    for i, track in enumerate(tracks, 1):
        # Форматируем длительность (мин:сек)
        duration_str = f"{track.duration // 60}:{track.duration % 60:02d}"
        
        # Формируем текст кнопки: "1. Artist - Title (3:45)"
        # Обрезаем, чтобы вместить полезную информацию и не выйти за лимиты
        artist = track.artist[:15].strip()
        title = track.title[:20].strip()
        
        button_text = f"{i}. {artist} - {title} ({duration_str})"
        
        # Создаем callback с ID трека (action=sel)
        callback = VoteCallback(action=CallbackAction.SELECT, value=track.identifier)
        
        buttons.append([InlineKeyboardButton(button_text, callback_data=callback.to_callback_data())])

    # Кнопка отмены
    cancel_cb = VoteCallback(action=CallbackAction.CANCEL, value="search")
    buttons.append([InlineKeyboardButton("❌ Закрыть поиск", callback_data=cancel_cb.to_callback_data())])
    
    return InlineKeyboardMarkup(buttons)

def get_radio_control_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления радио для текущего чата (Кнопки под плеером)."""
    skip_cb = VoteCallback(action=CallbackAction.SKIP, value=str(chat_id))
    stop_cb = VoteCallback(action=CallbackAction.STOP, value=str(chat_id))
    
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("⏭️ Пропустить", callback_data=skip_cb.to_callback_data()),
        InlineKeyboardButton("⏹️ Стоп", callback_data=stop_cb.to_callback_data())
    ]])

def get_confirmation_keyboard(action: str, value: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения."""
    # Формат value: "action_type:original_value"
    confirm_val = f"{action}:{value}"
    
    confirm_cb = VoteCallback(action=CallbackAction.CONFIRM, value=confirm_val)
    cancel_cb = VoteCallback(action=CallbackAction.CANCEL, value=action)
    
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Да", callback_data=confirm_cb.to_callback_data()),
        InlineKeyboardButton("❌ Нет", callback_data=cancel_cb.to_callback_data())
    ]])

def get_pagination_keyboard(current_page: int, total_pages: int, base_value: str) -> InlineKeyboardMarkup:
    """Создаёт кнопки пагинации."""
    buttons = []
    
    # Кнопка "Назад"
    if current_page > 1:
        prev_cb = VoteCallback(action=CallbackAction.PAGE, value=f"{current_page-1}:{base_value}")
        buttons.append(InlineKeyboardButton("◀️", callback_data=prev_cb.to_callback_data()))
    
    # Индикатор страницы (неактивная кнопка)
    buttons.append(InlineKeyboardButton(f"📄 {current_page}/{total_pages}", callback_data="noop"))
    
    # Кнопка "Вперед"
    if current_page < total_pages:
        next_cb = VoteCallback(action=CallbackAction.PAGE, value=f"{current_page+1}:{base_value}")
        buttons.append(InlineKeyboardButton("▶️", callback_data=next_cb.to_callback_data()))
    
    return InlineKeyboardMarkup([buttons])
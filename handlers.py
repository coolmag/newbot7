from __future__ import annotations
import logging
import os
import asyncio
from math import ceil
from typing import Optional, Dict, Any, List

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

from radio import RadioManager
from config import Settings
from youtube import YouTubeDownloader
from models import VoteCallback, CallbackAction
from keyboards import get_track_search_keyboard, get_pagination_keyboard

logger = logging.getLogger("handlers")

# Constants & Conversation states
PAGE_SIZE = 5
SEARCH_LIMIT = 30
MENU, WAITING_ARTIST, WAITING_TRACK = range(3)

# +++ Main Navigation Logic +++

def _get_node_from_path(path: str, settings: Settings) -> Optional[Dict[str, Any]]:
    """Gets a node from the genres.json structure using a ':' separated path."""
    try:
        keys = path.split(':')
        node = settings.GENRE_DATA
        for key in keys:
            if 'children' in node:
                node = node['children'][key]
            else:
                node = node[key]
        return node
    except KeyError:
        return None

def _generate_keyboard_from_path(path: str, settings: Settings) -> InlineKeyboardMarkup:
    """Generates a keyboard from a node in the genres.json structure."""
    node = _get_node_from_path(path, settings)
    if not node:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Ошибка", callback_data="noop")]])

    buttons = []
    if 'children' in node:
        for key, child in node['children'].items():
            child_path = f"{path}:{key}"
            # If the child has children, it's a navigation button
            if 'children' in child:
                action = CallbackAction.NAVIGATE
                value = child_path
            # If it has a query, it's a radio station button
            elif 'query' in child:
                action = CallbackAction.START_RADIO
                value = child['query']
            # If it has a special action, it's a command button
            elif 'action' in child:
                action = child['action']
                value = child.get('value', key) # Use key as value if not specified
            else:
                continue # Skip misconfigured items
            
            buttons.append(InlineKeyboardButton(child['name'], callback_data=VoteCallback(action, value).to_callback_data()))

    # Create a 2-column layout
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    
    # Add navigation buttons
    nav_buttons = []
    if ':' in path: # Not the top level
        parent_path = ":".join(path.split(':')[:-1])
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(CallbackAction.NAVIGATE, parent_path).to_callback_data()))
    
    if path != "main_menu":
         nav_buttons.append(InlineKeyboardButton("🔝 В главное меню", callback_data=VoteCallback(CallbackAction.NAVIGATE, "main_menu").to_callback_data()))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    return InlineKeyboardMarkup(keyboard)

# +++ State Handlers +++

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the /start command and main menu entry."""
    text = "🎧 *Музыкальный комбайн v14*\n\nВыберите действие:"
    markup = _generate_keyboard_from_path("main_menu", context.application.settings)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    return MENU

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """The main handler for all menu navigation and actions."""
    query = update.callback_query
    await query.answer()
    
    callback = VoteCallback.from_callback_data(query.data)
    if not callback: return MENU
    
    action, value = callback.action, callback.value
    settings: Settings = context.application.settings

    if action == CallbackAction.NAVIGATE:
        node = _get_node_from_path(value, settings)
        if node:
            title = node.get('name', 'Меню')
            markup = _generate_keyboard_from_path(value, settings)
            await query.edit_message_text(f"👇 *{title}*", parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        else:
            await query.edit_message_text("❌ Ошибка навигации.", reply_markup=_generate_keyboard_from_path("main_menu", settings))
        return MENU

    elif action == CallbackAction.START_RADIO:
        await query.edit_message_text(f"🛰️ Настраиваюсь на волну...")
        asyncio.create_task(context.application.radio_manager.start(chat_id=query.message.chat_id, query=value))
        return ConversationHandler.END

    elif action == "random_radio":
        await query.edit_message_text("🎲 Ищу случайную волну...")
        asyncio.create_task(context.application.radio_manager.start(chat_id=query.message.chat_id, query="random"))
        return ConversationHandler.END

    elif action == CallbackAction.SEARCH_ARTIST:
        await query.edit_message_text("👤 Введите имя артиста:")
        return WAITING_ARTIST
        
    elif action == CallbackAction.SEARCH_TRACK:
        await query.edit_message_text("🎵 Введите название трека:")
        return WAITING_TRACK

    elif action == CallbackAction.PAGE:
        try:
            page_num_str, search_query = value.split(":", 1)
            page_num = int(page_num_str)
            await _send_artist_search_results(update, context, query_text=search_query, page=page_num)
        except (ValueError, TypeError) as e:
            logger.error(f"Error handling pagination: {e}")
            await query.answer("❌ Ошибка пагинации")
        return MENU

    elif action == CallbackAction.CANCEL and value == "search":
        await query.edit_message_text("Поиск отменен.")
        return await start(update, context) # Go back to main menu
        
    return MENU

# +++ Search Logic Handlers +++

async def search_artist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query_text = update.message.text
    # Remove the "waiting for input" message
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.reply_to_message.message_id)
    await _send_artist_search_results(update, context, query_text=query_text, page=1)
    return MENU # Return to menu state to allow track selection or cancellation

async def search_track_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query_text = update.message.text
    await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.reply_to_message.message_id)
    msg = await update.message.reply_text(f"🔎 Ищу трек: *{query_text}*...", parse_mode=ParseMode.MARKDOWN)
    
    tracks = await context.application.downloader.search(query=query_text, search_mode='track', limit=1)
    if not tracks:
        await msg.edit_text("😕 Ничего не найдено.")
    else:
        await msg.delete()
        await _send_track(context, update.message.chat_id, tracks[0].identifier)
    return ConversationHandler.END

async def select_track_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    callback = VoteCallback.from_callback_data(query.data)
    if not callback or callback.action != CallbackAction.SELECT: return MENU
    
    await query.edit_message_text("⏳ Готовлю выбранный трек к отправке...")
    await _send_track(context, query.message.chat_id, callback.value)
    return ConversationHandler.END # End conversation after sending a track

# +++ Pagination and Track Sending Helpers +++

async def _send_artist_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str, page: int = 1):
    """Sends a paginated message with artist search results."""
    tracks = await context.application.downloader.search(query=query_text, search_mode='artist', limit=SEARCH_LIMIT)
    
    if not tracks:
        await update.effective_message.reply_text("😕 Не удалось найти треки этого исполнителя.")
        return

    total_pages = ceil(len(tracks) / PAGE_SIZE)
    start_index = (page - 1) * PAGE_SIZE
    tracks_page = tracks[start_index : start_index + PAGE_SIZE]

    if not tracks_page:
        await update.effective_message.reply_text("😕 На этой странице больше ничего нет.")
        return

    track_kb = get_track_search_keyboard(tracks_page)
    pagination_kb = get_pagination_keyboard(page, total_pages, query_text)
    
    final_markup = InlineKeyboardMarkup(track_kb.inline_keyboard + pagination_kb.inline_keyboard)
    text = f"**Лучшие треки {query_text} (Стр. {page}/{total_pages}):**"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=final_markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=final_markup)

async def _send_track(context: ContextTypes.DEFAULT_TYPE, chat_id: int, video_id: str):
    """Downloads and sends a single track."""
    downloader: YouTubeDownloader = context.application.downloader
    file_path = None
    try:
        result = await downloader.download(video_id)
        if not result.success:
            await context.bot.send_message(chat_id, f"❌ Не удалось загрузить трек: {result.error_message}")
            return

        file_path = result.file_path
        track_info = result.track_info
        
        if result.file_id:
            await context.bot.send_audio(chat_id, audio=result.file_id, title=track_info.title, performer=track_info.artist, duration=track_info.duration, thumbnail=track_info.thumbnail_url)
        elif file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                msg = await context.bot.send_audio(chat_id, audio=f, title=track_info.title, performer=track_info.artist, duration=track_info.duration, thumbnail=track_info.thumbnail_url)
                if msg.audio: await downloader.cache_file_id(video_id, msg.audio.file_id)
    finally:
        if file_path and os.path.exists(file_path):
            try: os.unlink(file_path)
            except OSError as e: logger.error(f"Error deleting temp file {file_path}: {e}")

# +++ Application Setup +++

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    app.downloader = downloader
    app.radio_manager = radio
    app.settings = settings
    
    # We use a single state (MENU) for all navigation, and WAITING_* for text input.
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MENU: [CallbackQueryHandler(menu_handler)],
            WAITING_ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_artist_handler)],
            WAITING_TRACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_track_handler)],
        },
        fallbacks=[
            CommandHandler('start', start),
            CallbackQueryHandler(select_track_handler, pattern=f"^{CallbackAction.SELECT}:.*"),
        ],
        per_message=False,
        conversation_timeout=3600 # 1 hour
    )
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("stop", radio.stop))
    app.add_handler(CommandHandler("skip", radio.skip))

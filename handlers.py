from __future__ import annotations
import logging
import os
import asyncio
from math import ceil
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)
from telegram.error import BadRequest

from radio import RadioManager
from config import Settings
from youtube import YouTubeDownloader
from models import VoteCallback, CallbackAction

try:
    from keyboards import get_track_search_keyboard, get_pagination_keyboard
except ImportError:
    def get_track_search_keyboard(tracks) -> InlineKeyboardMarkup:
        buttons = [InlineKeyboardButton(f"{i}. {t.title}", callback_data=VoteCallback(CallbackAction.SELECT, t.identifier).to_callback_data()) for i, t in enumerate(tracks, 1)]
        return InlineKeyboardMarkup([[b] for b in buttons] + [[InlineKeyboardButton("❌ Отмена", callback_data=VoteCallback(CallbackAction.CANCEL, "search").to_callback_data())]])
    def get_pagination_keyboard(current_page, total_pages, base_value) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([[]])

logger = logging.getLogger("handlers")

# Constants
PAGE_SIZE = 5
SEARCH_LIMIT = 30

# Conversation states
MENU, WAITING_ARTIST, WAITING_TRACK = range(3)

# +++ Helper function for sending tracks +++
async def _send_track(context: ContextTypes.DEFAULT_TYPE, chat_id: int, video_id: str):
    downloader: YouTubeDownloader = context.application.downloader
    download_result = None
    try:
        download_result = await downloader.download(video_id)
        if not download_result.success:
            await context.bot.send_message(chat_id, f"❌ Не удалось обработать трек: {download_result.error_message}")
            return
        track_info = download_result.track_info
        if download_result.file_id:
            await context.bot.send_audio(chat_id=chat_id, audio=download_result.file_id, title=track_info.title, performer=track_info.artist, duration=track_info.duration, thumbnail=track_info.thumbnail_url)
        elif download_result.file_path and os.path.exists(download_result.file_path):
            with open(download_result.file_path, 'rb') as f:
                msg = await context.bot.send_audio(chat_id=chat_id, audio=f, title=track_info.title, performer=track_info.artist, duration=track_info.duration, thumbnail=track_info.thumbnail_url)
                if msg.audio: await downloader.cache_file_id(video_id, msg.audio.file_id)
    finally:
        if download_result and download_result.file_path and os.path.exists(download_result.file_path):
            try: os.unlink(download_result.file_path)
            except OSError: pass

# +++ Keyboard Generators (Menu) +++
def _generate_main_menu_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            button["text"],
            callback_data=VoteCallback(action=button["action"], value="go").to_callback_data()
        ) for button in settings.GENRE_DATA["main_menu"]["buttons"]
    ]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])

def _generate_primary_menu_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    """Generates the keyboard for primary genre selection."""
    buttons = [
        InlineKeyboardButton(data["name"], callback_data=VoteCallback(CallbackAction.ERA, key).to_callback_data())
        for key, data in settings.GENRE_DATA.items() if key not in ["main_menu", "search_menu", "moods"]
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ В главное меню", callback_data=VoteCallback(action="main_menu", value="back").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_subgenre_keyboard(settings: Settings, era_key: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(sub_data["name"], callback_data=VoteCallback(CallbackAction.SUBGENRE, f"{era_key}:{sub_key}").to_callback_data())
        for sub_key, sub_data in settings.GENRE_DATA[era_key].get("subgenres", {}).items()
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(action="menu_genres", value="back").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_decade_keyboard(settings: Settings, era_key: str, subgenre_key: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(decade_data["name"], callback_data=VoteCallback(CallbackAction.DECADE, f"{era_key}:{subgenre_key}:{decade_key}").to_callback_data())
        for decade_key, decade_data in settings.GENRE_DATA[era_key]["subgenres"].get(subgenre_key, {}).get("decades", {}).items()
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад к Поджанрам", callback_data=VoteCallback(action=CallbackAction.ERA, value=era_key).to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

# +++ Search result pagination helper +++
async def _send_artist_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str, page: int = 1):
    """Sends a paginated message with artist search results."""
    tracks = await context.application.downloader.search(query=query_text, search_mode='artist', limit=SEARCH_LIMIT)

    if not tracks:
        text = "😕 Не удалось найти треки этого исполнителя."
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return

    total_pages = ceil(len(tracks) / PAGE_SIZE)
    start_index = (page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    tracks_page = tracks[start_index:end_index]

    if not tracks_page:
        text = "😕 На этой странице больше ничего нет."
        await update.effective_message.reply_text(text)
        return

    # Create keyboards
    track_kb = get_track_search_keyboard(tracks_page)
    pagination_kb = get_pagination_keyboard(page, total_pages, query_text)

    # Combine keyboards
    combined_buttons = track_kb.inline_keyboard + pagination_kb.inline_keyboard
    final_markup = InlineKeyboardMarkup(combined_buttons)

    text = f"**Лучшие треки {query_text} (Страница {page}/{total_pages}):**"

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=final_markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=final_markup)

# +++ State Handlers +++
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = "🎧 *Музыкальный комбайн v13*\n\nВыберите действие:"
    markup = _generate_main_menu_keyboard(context.application.settings)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    return MENU

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    callback = VoteCallback.from_callback_data(query.data)
    if not callback: return MENU

    settings = context.application.settings
    action, value = callback.action, callback.value

    if action == "main_menu":
        return await start(update, context)
    elif action == "menu_genres":
        await query.edit_message_text("👇 Выбери жанр:", reply_markup=_generate_primary_menu_keyboard(settings))
        return MENU
    elif action == "menu_search":
        await query.edit_message_text("🔎 Что будем искать?", reply_markup=_generate_subgenre_keyboard(settings, "search_menu"))
        return MENU
    elif action == "menu_moods":
        await query.edit_message_text("🌈 Какое у тебя настроение?", reply_markup=_generate_subgenre_keyboard(settings, "moods"))
        return MENU
    elif action == "search_artist":
        await query.edit_message_text("👤 Введите имя артиста:")
        return WAITING_ARTIST
    elif action == "search_track":
        await query.edit_message_text("🎵 Введите название трека:")
        return WAITING_TRACK
    elif action == "random_radio":
        await query.edit_message_text("🎲 Ищу случайную волну...")
        asyncio.create_task(context.application.radio_manager.start(chat_id=query.message.chat_id, query="random"))
        return ConversationHandler.END
    elif action == CallbackAction.ERA:
        era_name = settings.GENRE_DATA.get(value, {}).get("name", "Музыка")
        await query.edit_message_text(f"🎧 *{era_name}*\n\nВыберите поджанр:", parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_subgenre_keyboard(settings, value))
        return MENU
    elif action == CallbackAction.SUBGENRE:
        try:
            era_key, sub_key = value.split(":")
            sub_data = settings.GENRE_DATA[era_key]["subgenres"][sub_key]

            # Special handler for the search menu
            if era_key == "search_menu":
                if sub_key == "artist":
                    await query.edit_message_text("👤 Введите имя артиста:")
                    return WAITING_ARTIST
                elif sub_key == "track":
                    await query.edit_message_text("🎵 Введите название трека:")
                    return WAITING_TRACK

            # If the subgenre has a direct query (like a mood), start the radio
            if "query" in sub_data:
                search_query, display_name = sub_data["query"], sub_data["name"]
                await query.edit_message_text(f"🛰️ Настраиваюсь на волну: *{display_name}*...")
                asyncio.create_task(context.application.radio_manager.start(chat_id=query.message.chat_id, query=search_query, display_name=display_name))
                return ConversationHandler.END
            
            # Otherwise, show the decades menu
            elif "decades" in sub_data:
                await query.edit_message_text(f"🕰️ *{sub_data['name']}*\n\nВыберите десятилетие:", parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_decade_keyboard(settings, era_key, sub_key))
                return MENU
            
            # Fallback for misconfigured items
            else:
                await query.edit_message_text("❌ Ошибка конфигурации меню.")
                return MENU

        except (ValueError, KeyError) as e:
            logger.error(f"Error in SUBGENRE handler: {e}")
            await query.edit_message_text("❌ Ошибка меню. Пожалуйста, используйте /start.")
            return ConversationHandler.END
    elif action == CallbackAction.DECADE:
        try:
            era_key, sub_key, decade_key = value.split(":")
            sub_data = settings.GENRE_DATA[era_key]["subgenres"].get(sub_key, {})
            decade_data = sub_data.get("decades", {}).get(decade_key, {})
            search_query, display_name = decade_data["query"], f"{sub_data['name']} ({decade_data['name']})"
            await query.edit_message_text(f"🛰️ Настраиваюсь на волну: *{display_name}*...")
            asyncio.create_task(
                context.application.radio_manager.start(
                    chat_id=query.message.chat_id,
                    query=search_query,
                    decade=decade_key,
                    display_name=display_name
                )
            )
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error in DECADE handler: {e}")
            return MENU
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
        return MENU
    return MENU

async def search_artist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query_text = update.message.text
    await update.message.reply_text(f"🔎 Ищу лучшие треки: *{query_text}*...", parse_mode=ParseMode.MARKDOWN)
    await _send_artist_search_results(update, context, query_text=query_text, page=1)
    return ConversationHandler.END

async def search_track_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = await update.message.reply_text(f"🔎 Ищу трек: *{update.message.text}*...", parse_mode=ParseMode.MARKDOWN)
    tracks = await context.application.downloader.search(query=update.message.text, search_mode='track', limit=1)
    if not tracks:
        await msg.edit_text("😕 Ничего не найдено.")
    else:
        await msg.delete()
        await _send_track(context, update.message.chat_id, tracks[0].identifier)
    return ConversationHandler.END

async def select_track_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    callback = VoteCallback.from_callback_data(query.data)
    if not callback or callback.action != CallbackAction.SELECT: return
    await query.edit_message_text("⏳ Готовлю выбранный трек к отправке...")
    asyncio.create_task(_send_track(context, query.message.chat_id, callback.value))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query: await update.callback_query.answer()
    await update.effective_message.reply_text("Действие отменено.")
    return ConversationHandler.END

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    app.downloader, app.radio_manager, app.settings = downloader, radio, settings

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CallbackQueryHandler(start, pattern="^main_menu:.*")],
        states={
            MENU: [CallbackQueryHandler(menu_handler)],
            WAITING_ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_artist_handler)],
            WAITING_TRACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_track_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('start', start)],
        per_message=False,
    )
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(select_track_handler, pattern=f"^{CallbackAction.SELECT}:.*"))
    app.add_handler(CommandHandler("stop", radio.stop))
    app.add_handler(CommandHandler("skip", radio.skip))
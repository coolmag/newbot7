from __future__ import annotations
import logging
import os
import asyncio
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
    from keyboards import get_track_search_keyboard
except ImportError:
    def get_track_search_keyboard(tracks) -> InlineKeyboardMarkup:
        buttons = [InlineKeyboardButton(f"{i}. {t.title}", callback_data=VoteCallback(CallbackAction.SELECT, t.identifier).to_callback_data()) for i, t in enumerate(tracks, 1)]
        return InlineKeyboardMarkup([[b] for b in buttons] + [[InlineKeyboardButton("❌ Отмена", callback_data=VoteCallback(CallbackAction.CANCEL, "search").to_callback_data())]])

logger = logging.getLogger("handlers")

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

# +++ Keyboard Generators +++
def _generate_main_menu_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            button["text"], 
            callback_data=VoteCallback(action=button["action"], value="go").to_callback_data()
        ) for button in settings.GENRE_DATA["main_menu"]["buttons"]
    ]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons) -1)] + [[buttons[-1]]])

def _generate_era_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(data["name"], callback_data=VoteCallback(CallbackAction.ERA, era_key).to_callback_data())
        for era_key, data in settings.GENRE_DATA.items() if era_key not in ["main_menu", "moods"]
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ В главное меню", callback_data=VoteCallback(action="main_menu", value="back").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_subgenre_keyboard(settings: Settings, era_key: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(sub_data["name"], callback_data=VoteCallback(CallbackAction.SUBGENRE, f"{era_key}:{sub_key}").to_callback_data())
        for sub_key, sub_data in settings.GENRE_DATA[era_key].get("subgenres", {{}}).items()
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад к Эпохам", callback_data=VoteCallback(action="menu_eras", value="back").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_decade_keyboard(settings: Settings, era_key: str, subgenre_key: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(decade_data["name"], callback_data=VoteCallback(CallbackAction.DECADE, f"{era_key}:{subgenre_key}:{decade_key}").to_callback_data())
        for decade_key, decade_data in settings.GENRE_DATA[era_key]["subgenres"].get(subgenre_key, {{}}).get("decades", {{}}).items()
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад к Поджанрам", callback_data=VoteCallback(action=CallbackAction.ERA, value=era_key).to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

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
    elif action == "menu_eras":
        await query.edit_message_text("👇 Выбери эпоху:", reply_markup=_generate_era_keyboard(settings))
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
        era_name = settings.GENRE_DATA.get(value, {{}}).get("name", "Музыка")
        await query.edit_message_text(f"🎧 *{era_name}*\n\nВыберите поджанр:", parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_subgenre_keyboard(settings, value))
        return MENU
    elif action == CallbackAction.SUBGENRE:
        try:
            era_key, sub_key = value.split(":")
            sub_data = settings.GENRE_DATA[era_key]["subgenres"][sub_key]
            # If it's a mood or a genre without decades, start it directly
            if "decades" not in sub_data:
                search_query, display_name = sub_data["query"], sub_data["name"]
                await query.edit_message_text(f"🛰️ Настраиваюсь на волну: *{display_name}*...")
                asyncio.create_task(context.application.radio_manager.start(chat_id=query.message.chat_id, query=search_query, display_name=display_name))
                return ConversationHandler.END
            else: # Show decades menu
                await query.edit_message_text(f"🕰️ *{sub_data['name']}*\n\nВыберите десятилетие:", parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_decade_keyboard(settings, era_key, sub_key))
                return MENU
        except (ValueError, KeyError) as e:
            await query.edit_message_text("❌ Ошибка меню. Пожалуйста, используйте /start.")
            return ConversationHandler.END
    elif action == CallbackAction.DECADE:
        try:
            era_key, sub_key, decade_key = value.split(":")
            sub_data = settings.GENRE_DATA[era_key]["subgenres"][sub_key]
            decade_data = sub_data["decades"][decade_key]
            search_query, display_name = decade_data["query"], f"{sub_data['name']} ({decade_data['name']})"
            await query.edit_message_text(f"🛰️ Настраиваюсь на волну: *{display_name}*...")
            asyncio.create_task(context.application.radio_manager.start(chat_id=query.message.chat_id, query=search_query, decade=decade_key, display_name=display_name))
        except (ValueError, KeyError, IndexError):
            await query.edit_message_text("❌ Ошибка меню. Пожалуйста, используйте /start.")
        return ConversationHandler.END
    return MENU

async def search_artist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(f"🔎 Ищу лучшие треки: *{update.message.text}*...", parse_mode=ParseMode.MARKDOWN)
    tracks = await context.application.downloader.search(query=update.message.text, search_mode='artist', limit=10)
    if not tracks:
        await update.message.reply_text("😕 Не удалось найти треки этого исполнителя.")
    else:
        text = f"**Лучшие треки {update.message.text}:**\n\n" + "\n".join([f"{i}. {t.title}" for i, t in enumerate(tracks, 1)])
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_track_search_keyboard(tracks))
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
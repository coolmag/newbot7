from __future__ import annotations
import logging
import os
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

from radio import RadioManager
from config import Settings
from keyboards import get_track_search_keyboard
from youtube import YouTubeDownloader
from models import DownloadResult, VoteCallback, CallbackAction

logger = logging.getLogger("handlers")

# +++ Helper functions +++

async def _send_track(
    context: ContextTypes.DEFAULT_TYPE, 
    chat_id: int, 
    video_id: str, 
    downloader: YouTubeDownloader
) -> bool:
    download_result = None
    try:
        download_result = await downloader.download(video_id)
        if not download_result.success:
            await context.bot.send_message(chat_id, f"❌ Не удалось обработать трек: {download_result.error}")
            return False

        track_info = download_result.track_info
        
        if download_result.file_id:
            await context.bot.send_audio(
                chat_id=chat_id, audio=download_result.file_id,
                title=track_info.title, performer=track_info.artist,
                duration=track_info.duration, thumbnail=track_info.thumbnail_url
            )
            return True
        
        if download_result.file_path:
            with open(download_result.file_path, 'rb') as audio_file:
                sent_message = await context.bot.send_audio(
                    chat_id=chat_id, audio=audio_file,
                    title=track_info.title, performer=track_info.artist,
                    duration=track_info.duration, thumbnail=track_info.thumbnail_url
                )
                if sent_message.audio:
                    await downloader.cache_file_id(video_id, sent_message.audio.file_id)
            return True
        return False
    except Exception as e:
        logger.error(f"Error in _send_track for video_id {video_id}: {e}", exc_info=True)
        await context.bot.send_message(chat_id, f"❌ Произошла критическая ошибка при отправке трека.")
        return False
    finally:
        if download_result and download_result.file_path and download_result.file_path.exists():
            try:
                os.unlink(download_result.file_path)
            except OSError as e:
                logger.warning(f"Failed to clean up file in _send_track: {e}")

# +++ Keyboard Generators +++

def _generate_main_genres_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            f"{data.get('icon', '')} {data.get('name', key)}", 
            callback_data=VoteCallback(action=CallbackAction.GENRE, value=key).to_callback_data()
        ) for key, data in settings.GENRE_DATA.items()
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data=VoteCallback(action=CallbackAction.CANCEL, value="menu").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_subgenres_keyboard(settings: Settings, main_genre_key: str) -> InlineKeyboardMarkup:
    buttons = []
    subgenres = settings.GENRE_DATA[main_genre_key].get("subgenres", {})
    for key, data in subgenres.items():
        # Если есть десятилетия, ведем на следующий уровень меню (GENRE). 
        # Если нет - сразу запускаем радио (RADIO).
        action = CallbackAction.GENRE if "decades" in data else CallbackAction.RADIO
        callback_data = VoteCallback(action=action, value=f"{main_genre_key}:{key}").to_callback_data()
        buttons.append(InlineKeyboardButton(f"{data.get('icon', '')} {data.get('name', key)}", callback_data=callback_data))
    
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(action=CallbackAction.GENRE, value="main_menu").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_decades_keyboard(settings: Settings, main_genre_key: str, subgenre_key: str) -> InlineKeyboardMarkup:
    buttons = []
    subgenre_data = settings.GENRE_DATA[main_genre_key]["subgenres"][subgenre_key]
    decades = subgenre_data.get("decades", [])
    for decade in decades:
        callback_data = VoteCallback(action=CallbackAction.RADIO, value=f"{main_genre_key}:{subgenre_key}:{decade}").to_callback_data()
        buttons.append(InlineKeyboardButton(decade, callback_data=callback_data))

    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(action=CallbackAction.GENRE, value=main_genre_key).to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

# +++ Command and Callback Handlers +++

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    
    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = f"👋 *Привет, {update.effective_user.first_name}!* Я — Cyber Radio v7.\n\n👇 Выбери категорию:"
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=_generate_main_genres_keyboard(settings)
        )

    async def search_or_play_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        command = update.message.text.split()[0].lower()
        query = " ".join(context.args)
        if not query:
            await update.message.reply_text(f"💬 Укажите запрос, например: `{command} Queen`")
            return

        search_msg = await update.message.reply_text(f"🔎 Ищу: `{query}`...", parse_mode=ParseMode.MARKDOWN)
        tracks = await downloader.search(query, limit=10)

        if not tracks:
            await search_msg.edit_text("😕 Ничего не найдено.")
            return

        text = f"**Результаты по запросу \"{query}\":**\n\n" + "\n".join(
            [f"{i}. {t.artist} - {t.title} ({t.duration // 60}:{t.duration % 60:02d})" for i, t in enumerate(tracks, 1)]
        )
        await search_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_track_search_keyboard(tracks))

    async def radio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.start(update.effective_chat.id, " ".join(context.args) or "random")

    async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.stop(update.effective_chat.id)
        await update.effective_message.reply_text("🛑 Радио остановлено.")

    async def skip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.skip(update.effective_chat.id)

    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        callback = VoteCallback.from_callback_data(query.data)
        if not callback:
            logger.warning(f"Could not parse callback data: {query.data}")
            return

        chat_id = query.message.chat.id

        if callback.action == CallbackAction.GENRE:
            parts = callback.value.split(":")
            if callback.value == "main_menu" or len(parts) == 0:
                await query.edit_message_text("👇 Выбери категорию:", reply_markup=_generate_main_genres_keyboard(settings))
            elif len(parts) == 1: # Main genre -> show subgenres
                await query.edit_message_text("🎶 Выбери поджанр:", reply_markup=_generate_subgenres_keyboard(settings, parts[0]))
            elif len(parts) == 2: # Subgenre with decades -> show decades
                await query.edit_message_text("⏳ Выбери десятилетие:", reply_markup=_generate_decades_keyboard(settings, parts[0], parts[1]))

        elif callback.action == CallbackAction.RADIO:
            try:
                parts = callback.value.split(":")
                main_key, sub_key = parts[0], parts[1]
                decade = parts[2] if len(parts) > 2 else None
                
                sub_genre = settings.GENRE_DATA[main_key]["subgenres"][sub_key]
                search_query = sub_genre["query"]
                display_name = f"{sub_genre.get('icon', '')} {sub_genre.get('name', search_query)}"
                if decade:
                    display_name += f" ({decade})"
                
                await query.edit_message_text(f"📻 Запускаю {display_name}...")
                await radio.start(chat_id, search_query, display_name=display_name, decade=decade)
            except (ValueError, KeyError, IndexError) as e:
                logger.error(f"Invalid RADIO callback value: {callback.value} - {e}")
                await query.edit_message_text("❌ Меню устарело. Пожалуйста, используйте /start, чтобы открыть актуальное меню.")

        elif callback.action == CallbackAction.SELECT:
            await radio.stop(chat_id)
            await query.edit_message_text(f"⏳ Готовлю выбранный трек к отправке...")
            if await _send_track(context, chat_id, callback.value, downloader):
                await query.message.delete()
        
        elif callback.action == CallbackAction.CANCEL:
            await query.message.delete()
        elif callback.action == CallbackAction.STOP:
            await radio.stop(chat_id)
            try:
                await query.edit_message_text("🛑 Радио остановлено.")
            except BadRequest: pass
        elif callback.action == CallbackAction.SKIP:
            await radio.skip(chat_id)

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler(["play", "search"], search_or_play_cmd))
    app.add_handler(CommandHandler("radio", radio_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("skip", skip_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
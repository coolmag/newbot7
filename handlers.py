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
    """
    Handles the full logic of downloading, sending, and caching a track.
    Returns True on success, False on failure.
    """
    download_result = None
    try:
        download_result = await downloader.download(video_id)
        if not download_result.success:
            await context.bot.send_message(chat_id, f"❌ Не удалось обработать трек: {download_result.error}")
            return False

        track_info = download_result.track_info
        
        # Если есть file_id в кэше, отправляем по нему
        if download_result.file_id:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=download_result.file_id,
                title=track_info.title,
                performer=track_info.artist,
                duration=track_info.duration,
                thumbnail=track_info.thumbnail_url
            )
            return True
        
        # Если скачан файл, отправляем его и кэшируем file_id
        if download_result.file_path:
            with open(download_result.file_path, 'rb') as audio_file:
                sent_message = await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio_file,
                    title=track_info.title,
                    performer=track_info.artist,
                    duration=track_info.duration,
                    thumbnail=track_info.thumbnail_url
                )
                # Кэшируем file_id для будущих запросов
                if sent_message.audio:
                    await downloader.cache_file_id(video_id, sent_message.audio.file_id)
            return True

    except Exception as e:
        logger.error(f"Error in _send_track for video_id {video_id}: {e}", exc_info=True)
        await context.bot.send_message(chat_id, f"❌ Произошла критическая ошибка при отправке трека.")
        return False
    finally:
        # Очистка файла, если он был скачан
        if download_result and download_result.file_path and download_result.file_path.exists():
            try:
                os.unlink(download_result.file_path)
            except OSError as e:
                logger.warning(f"Failed to clean up file in _send_track: {e}")

def _get_style_search_query(settings: Settings, main_genre_key: str, subgenre_key: str) -> str:
    try:
        return settings.GENRE_DATA[main_genre_key]["subgenres"][subgenre_key]["query"]
    except (KeyError, AttributeError):
        return f"{main_genre_key} {subgenre_key}"

def _generate_main_genres_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    buttons = []
    if not hasattr(settings, 'GENRE_DATA') or not isinstance(settings.GENRE_DATA, dict):
        return InlineKeyboardMarkup([[]])
    for key, data in settings.GENRE_DATA.items():
        callback_data = VoteCallback(action=CallbackAction.GENRE, value=key).to_callback_data()
        buttons.append(InlineKeyboardButton(f"{data.get('icon', '')} {data.get('name', key)}", callback_data=callback_data))
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data=VoteCallback(action=CallbackAction.CANCEL, value="menu").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_subgenres_keyboard(settings: Settings, main_genre_key: str) -> InlineKeyboardMarkup:
    buttons = []
    if not hasattr(settings, 'GENRE_DATA') or main_genre_key not in settings.GENRE_DATA:
         return InlineKeyboardMarkup([[]])
    subgenres = settings.GENRE_DATA[main_genre_key].get("subgenres", {})
    for key, data in subgenres.items():
        callback_data = VoteCallback(action=CallbackAction.RADIO, value=f"{main_genre_key}:{key}").to_callback_data()
        buttons.append(InlineKeyboardButton(f"{data.get('icon', '')} {data.get('name', key)}", callback_data=callback_data))
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(action=CallbackAction.GENRE, value="main_menu").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

# +++ Command and Callback Handlers +++

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    
    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user.first_name
        text = f"👋 *Привет, {user}!* Я — Cyber Radio v7.\n\n👇 Выбери категорию:"
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=_generate_main_genres_keyboard(settings)
        )

    async def search_or_play_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        command = update.message.text.split()[0].lower()
        is_play_cmd = "/play" in command
        
        query = " ".join(context.args)
        if not query:
            await update.message.reply_text(f"💬 Укажите запрос, например: `{command} Queen - Bohemian Rhapsody`")
            return

        search_msg = await update.message.reply_text(f"🔎 Ищу: `{query}`...", parse_mode=ParseMode.MARKDOWN)
        
        tracks = await downloader.search(query, limit=5 if is_play_cmd else 10)

        if not tracks:
            await search_msg.edit_text("😕 Ничего не найдено.")
            return

        text = f"**Результаты по запросу \"{query}\":**\n\n"
        for i, track in enumerate(tracks, 1):
            text += f"{i}. {track.artist} - {track.title} ({track.duration // 60}:{track.duration % 60:02d})\n"
        
        await search_msg.edit_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_track_search_keyboard(tracks)
        )

    async def radio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = " ".join(context.args) if context.args else "random"
        if len(query) > 100:
            await update.message.reply_text("❌ Слишком длинный запрос.")
            return
        await radio.start(update.effective_chat.id, query, display_name=query)

    async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.stop(update.effective_chat.id)
        await update.effective_message.reply_text("🛑 Радио остановлено.")

    async def skip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.skip(update.effective_chat.id)

    # --- Callback Handler ---

    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        chat_id = query.message.chat.id

        callback = VoteCallback.from_callback_data(data)
        if not callback:
            logger.warning(f"Could not parse callback data: {data}")
            return

        # --- Action Dispatcher ---

        if callback.action == CallbackAction.RADIO:
            try:
                main_genre_key, subgenre_key = callback.value.split(":")
                search_query = _get_style_search_query(settings, main_genre_key, subgenre_key)
                sub_genre = settings.GENRE_DATA[main_genre_key]["subgenres"][subgenre_key]
                display_name = f"{sub_genre.get('icon', '')} {sub_genre.get('name', search_query)}"
                await query.edit_message_text(f"📻 Запускаю {display_name}...")
                await radio.start(chat_id, search_query, display_name=display_name)
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid RADIO callback value: {callback.value} - {e}")
                await query.edit_message_text("❌ Меню устарело. Пожалуйста, используйте /start, чтобы открыть актуальное меню.")

        elif callback.action == CallbackAction.GENRE:
            if callback.value == "main_menu":
                await query.edit_message_text("👇 Выбери категорию:", reply_markup=_generate_main_genres_keyboard(settings))
            else: 
                await query.edit_message_text("🎶 Выбери поджанр:", reply_markup=_generate_subgenres_keyboard(settings, callback.value))

        elif callback.action == CallbackAction.STOP:
            await radio.stop(chat_id)
            try:
                await query.edit_message_text("🛑 Радио остановлено.")
            except BadRequest: pass

        elif callback.action == CallbackAction.SKIP:
            await radio.skip(chat_id)
        
        elif callback.action == CallbackAction.CANCEL:
            await query.message.delete()

        elif callback.action == CallbackAction.SELECT:
            video_id = callback.value
            await radio.stop(chat_id)
            await query.edit_message_text(f"⏳ Готовлю выбранный трек к отправке...")
            
            success = await _send_track(context, chat_id, video_id, downloader)
            if success:
                await query.message.delete()
        
    # --- Register Handlers ---
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler(["play", "search"], search_or_play_cmd))
    app.add_handler(CommandHandler("radio", radio_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("skip", skip_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
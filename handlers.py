from __future__ import annotations
import logging
import os
from typing import Optional, Literal

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

from radio import RadioManager
from config import Settings
from keyboards import _generate_main_genres_keyboard, _generate_subgenres_keyboard, _get_style_search_query
from youtube import YouTubeDownloader
from cache_service import CacheService

logger = logging.getLogger("handlers")
SearchMode = Literal['track', 'artist', 'genre']

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader, cache_service: CacheService):
    
    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user.first_name
        text = f"👋 *Привет, {user}!* Я — Cyber Radio v7.\n\n👇 Выбери категорию:"
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=_generate_main_genres_keyboard(settings)
        )

    async def play_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.stop(update.effective_chat.id)
        query = " ".join(context.args)
        if not query:
            await update.message.reply_text("💬 Укажите название трека, например: `/play Queen - Bohemian Rhapsody`")
            return

        search_msg = await update.message.reply_text(f"🔎 Ищу: `{query}`...", parse_mode=ParseMode.MARKDOWN)
        
        download_result = None
        try:
            download_result = await downloader.download_with_retry(query)
            if not download_result or not download_result.success or not download_result.file_path:
                await search_msg.edit_text(f"❌ Не удалось найти или скачать трек: {download_result.error if download_result else 'Unknown error'}")
                return

            track_info = download_result.track_info
            with open(download_result.file_path, 'rb') as audio_file:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id, audio=audio_file, title=track_info.title,
                    performer=track_info.artist, duration=track_info.duration
                )
            await search_msg.delete()
        except Exception as e:
            logger.error(f"Error in /play command: {e}", exc_info=True)
            await search_msg.edit_text(f"❌ Ошибка: {e}")
        finally:
            if download_result and download_result.file_path and download_result.file_path.exists():
                download_result.file_path.unlink()

    async def radio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = " ".join(context.args) if context.args else "random"
        if len(query) > 100:
            await update.message.reply_text("❌ Слишком длинный запрос.")
            return
        await radio.start(update.effective_chat.id, query, search_mode='genre')

    async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.stop(update.effective_chat.id)
        await update.effective_message.reply_text("🛑 Радио остановлено.")

    async def skip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.skip(update.effective_chat.id)

    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        chat_id = query.message.chat.id
        
        if data.startswith("genre_sub:"):
            _, main_genre_key, subgenre_key = data.split(":")
            search_query = _get_style_search_query(settings, main_genre_key, subgenre_key)
            sub_genre = settings.GENRE_DATA[main_genre_key]["subgenres"][subgenre_key]
            display_name = f"{sub_genre.get('icon', '')} {sub_genre.get('name', search_query)}"
            await query.edit_message_text(f"📻 Запускаю {display_name}...", reply_markup=None)
            await radio.start(chat_id, search_query, search_mode='genre', display_name=display_name)
        elif data.startswith("genre_main:"):
            genre_key = data.removeprefix("genre_main:")
            await query.edit_message_text(
                "🎶 Выбери поджанр:",
                reply_markup=_generate_subgenres_keyboard(settings, genre_key)
            )
        elif data == "show_main_genres":
             await query.edit_message_text(
                "👇 Выбери категорию:",
                reply_markup=_generate_main_genres_keyboard(settings)
            )
        elif data == "cancel_menu":
            await query.edit_message_text("❌ Меню закрыто.")

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("play", play_cmd))
    app.add_handler(CommandHandler("radio", radio_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("skip", skip_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))

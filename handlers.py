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
    # This function is self-contained and correct.
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

# +++ Keyboard Generators (2-LEVEL STRUCTURE) +++

def _generate_era_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    """Level 1: Generates the top-level Era selection keyboard."""
    buttons = [
        InlineKeyboardButton(
            data["name"], 
            callback_data=VoteCallback(action=CallbackAction.ERA, value=era_key).to_callback_data()
        ) for era_key, data in settings.GENRE_DATA.items()
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data=VoteCallback(action=CallbackAction.CANCEL, value="menu").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_decade_keyboard(settings: Settings, era_key: str) -> InlineKeyboardMarkup:
    """Level 2: Generates the Decade selection keyboard for a given Era."""
    buttons = []
    decades = settings.GENRE_DATA[era_key].get("decades", {})
    for decade_key, decade_data in decades.items():
        callback_data = VoteCallback(action=CallbackAction.DECADE, value=f"{era_key}:{decade_key}").to_callback_data()
        buttons.append(InlineKeyboardButton(decade_data["name"], callback_data=callback_data))

    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(action=CallbackAction.ERA, value="main_menu").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

# +++ Command and Callback Handlers +++

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    
    async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = f"👋 *Привет, {update.effective_user.first_name}!* Я — музыкальная машина времени.\n\n👇 Выбери эпоху:"
        await update.effective_message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_era_keyboard(settings))

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
        text = f"**Результаты по запросу '{query}':**\n\n" + "\n".join([f"{i}. {t.artist} - {t.title} ({t.duration // 60}:{t.duration % 60:02d})" for i, t in enumerate(tracks, 1)])
        await search_msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_track_search_keyboard(tracks))

    async def radio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.application.create_task(
             radio.start(chat_id=update.effective_chat.id, query="random")
        )

    async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.stop(update.effective_chat.id)
        await update.effective_message.reply_text("🛑 Радио остановлено.")

    async def skip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await radio.skip(update.effective_chat.id)

    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        callback = VoteCallback.from_callback_data(query.data)
        if not callback: return

        chat_id = query.message.chat.id

        if callback.action == CallbackAction.ERA:
            if callback.value == "main_menu":
                await query.edit_message_text("👇 Выбери эпоху:", reply_markup=_generate_era_keyboard(settings))
            else:
                era_key = callback.value
                era_name = settings.GENRE_DATA.get(era_key, {}).get("name", "Музыка")
                await query.edit_message_text(f"🕰️ *{era_name}*\n\nВыберите десятилетие:", parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_decade_keyboard(settings, era_key))

        elif callback.action == CallbackAction.DECADE:
            try:
                era_key, decade_key = callback.value.split(":")
                era_data = settings.GENRE_DATA[era_key]
                decade_data = era_data["decades"][decade_key]
                
                search_query = decade_data["query"]
                display_name = f"{era_data['name']} ({decade_data['name']})"
                
                await query.edit_message_text(f"🛰️ Настраиваюсь на волну: *{display_name}*...", parse_mode=ParseMode.MARKDOWN)
                context.application.create_task(
                    radio.start(chat_id=chat_id, query=search_query, decade=decade_key, display_name=display_name)
                )
            except (ValueError, KeyError, IndexError) as e:
                logger.error(f"Invalid DECADE callback: {callback.value} - {e}")
                await query.edit_message_text("❌ Меню устарело. Пожалуйста, используйте /start.")

        elif callback.action == CallbackAction.SELECT:
            await radio.stop(chat_id)
            await query.edit_message_text(f"⏳ Готовлю выбранный трек к отправке...")
            context.application.create_task(
                _send_track(context, chat_id, callback.value, downloader)
            )
        
        elif callback.action == CallbackAction.CANCEL: await query.message.delete()
        elif callback.action == CallbackAction.STOP:
            await radio.stop(chat_id)
            try: await query.edit_message_text("🛑 Радио остановлено.")
            except BadRequest: pass
        elif callback.action == CallbackAction.SKIP: await radio.skip(chat_id)

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler(["play", "search"], search_or_play_cmd))
    app.add_handler(CommandHandler("radio", radio_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("skip", skip_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
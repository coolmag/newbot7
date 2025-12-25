from __future__ import annotations
import logging
from typing import Optional, Literal

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram.error import BadRequest

from radio import RadioManager
from config import Settings
from keyboards import get_track_search_keyboard, get_genre_voting_keyboard
from youtube import YouTubeDownloader
from cache_service import CacheService
from models import TrackInfo, DownloadResult, VoteCallback, CallbackAction

logger = logging.getLogger("handlers")
SearchMode = Literal['track', 'artist', 'genre']

# +++ Helper functions for genre keyboards +++

def _get_style_search_query(settings: Settings, main_genre_key: str, subgenre_key: str) -> str:
    """Helper to get the search query from genre data."""
    try:
        # Assuming GENRE_DATA structure from user's context
        return settings.GENRE_DATA[main_genre_key]["subgenres"][subgenre_key]["query"]
    except (KeyError, AttributeError):
        # Fallback if structure is not as expected
        return f"{main_genre_key} {subgenre_key}"

def _generate_main_genres_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    """Generates the main genre selection keyboard using VoteCallback."""
    buttons = []
    # Assuming settings.GENRE_DATA is a dict
    if not hasattr(settings, 'GENRE_DATA') or not isinstance(settings.GENRE_DATA, dict):
        return InlineKeyboardMarkup([[]])
        
    for key, data in settings.GENRE_DATA.items():
        callback_data = VoteCallback(action=CallbackAction.GENRE, value=key).to_callback_data()
        buttons.append(InlineKeyboardButton(f"{data.get('icon', '')} {data.get('name', key)}", callback_data=callback_data))
    
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data=VoteCallback(action=CallbackAction.CANCEL, value="menu").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_subgenres_keyboard(settings: Settings, main_genre_key: str) -> InlineKeyboardMarkup:
    """Generates the sub-genre selection keyboard using VoteCallback."""
    buttons = []
    # Assuming settings.GENRE_DATA has the main_genre_key
    if not hasattr(settings, 'GENRE_DATA') or main_genre_key not in settings.GENRE_DATA:
         return InlineKeyboardMarkup([[]])

    subgenres = settings.GENRE_DATA[main_genre_key].get("subgenres", {})
    for key, data in subgenres.items():
        # The value is a composite key for the button_callback to parse
        callback_data = VoteCallback(action=CallbackAction.RADIO, value=f"{main_genre_key}:{key}").to_callback_data()
        buttons.append(InlineKeyboardButton(f"{data.get('icon', '')} {data.get('name', key)}", callback_data=callback_data))

    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(action=CallbackAction.GENRE, value="main_menu").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

# +++ Command and Callback Handlers +++

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader, cache_service: CacheService):
    
    # --- Command Handlers ---

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
            tracks = await downloader.search(query, search_mode='track', limit=1)
            if not tracks:
                await search_msg.edit_text(f"❌ Не удалось найти трек: `{query}`")
                return
            
            track_to_play = tracks[0]
            download_result = await downloader.download(track_to_play.identifier)

            if not download_result.success:
                await search_msg.edit_text(f"❌ Не удалось скачать трек: {download_result.error}")
                return

            with open(download_result.file_path, 'rb') as audio_file:
                await context.bot.send_audio(
                    chat_id=update.effective_chat.id, audio=audio_file,
                    title=download_result.track_info.title,
                    performer=download_result.track_info.artist,
                    duration=download_result.track_info.duration
                )
            await search_msg.delete()
        except Exception as e:
            logger.error(f"Error in /play command: {e}", exc_info=True)
            await search_msg.edit_text(f"❌ Ошибка: {e}")
        finally:
            if download_result and download_result.file_path and download_result.file_path.exists():
                try:
                    download_result.file_path.unlink()
                except OSError as e:
                    logger.warning(f"Failed to clean up file in play_cmd: {e}")

    async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = " ".join(context.args)
        if not query:
            await update.message.reply_text("💬 Укажите запрос для поиска, например: `/search lofi hip hop`")
            return
        
        await update.message.reply_text(f"🔎 Ищу: `{query}`...", parse_mode=ParseMode.MARKDOWN)
        tracks = await downloader.search(query, search_mode='track', limit=10)

        if not tracks:
            await update.message.reply_text("😕 Ничего не найдено.")
            return

        text = f"**Результаты по запросу "{query}":**\n\n"
        for i, track in enumerate(tracks, 1):
            text += f"{i}. {track.artist} - {track.title} ({track.duration // 60}:{track.duration % 60:02d})\n"
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_track_search_keyboard(tracks)
        )

    async def radio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = " ".join(context.args) if context.args else "random"
        if len(query) > 100:
            await update.message.reply_text("❌ Слишком длинный запрос.")
            return
        await radio.start(update.effective_chat.id, query, search_mode='genre', display_name=query)

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
                await radio.start(chat_id, search_query, search_mode='genre', display_name=display_name)
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid RADIO callback value: {callback.value} - {e}")
                await query.edit_message_text("❌ Ошибка выбора жанра.")

        elif callback.action == CallbackAction.GENRE:
            if callback.value == "main_menu":
                await query.edit_message_text(
                    "👇 Выбери категорию:"
                    reply_markup=_generate_main_genres_keyboard(settings)
                )
            else: 
                await query.edit_message_text(
                    "🎶 Выбери поджанр:"
                    reply_markup=_generate_subgenres_keyboard(settings, callback.value)
                )

        elif callback.action == CallbackAction.STOP:
            await radio.stop(chat_id)
            try:
                await query.edit_message_text("🛑 Радио остановлено.")
            except BadRequest: # Message not modified
                pass

        elif callback.action == CallbackAction.SKIP:
            await radio.skip(chat_id)
            # The radio manager sends its own message
        
        elif callback.action == CallbackAction.CANCEL:
            if callback.value in ("menu", "search"):
                await query.edit_message_text(f"❌ {callback.value.capitalize()} отменено.")

        elif callback.action == CallbackAction.SELECT:
            video_id = callback.value
            await radio.stop(chat_id)
            await query.edit_message_text(f"📥 Загружаю выбранный трек...")
            
            download_result = None
            try:
                download_result = await downloader.download(video_id)
                if not download_result.success:
                    await query.edit_message_text(f"❌ Не удалось скачать трек: {download_result.error}")
                    return

                with open(download_result.file_path, 'rb') as audio_file:
                    await context.bot.send_audio(
                        chat_id=chat_id, audio=audio_file,
                        title=download_result.track_info.title,
                        performer=download_result.track_info.artist,
                        duration=download_result.track_info.duration
                    )
                await query.message.delete()
            except Exception as e:
                logger.error(f"Error in SELECT callback: {e}", exc_info=True)
                await query.edit_message_text(f"❌ Ошибка: {e}")
            finally:
                if download_result and download_result.file_path and download_result.file_path.exists():
                    try:
                        download_result.file_path.unlink()
                    except OSError as e:
                        logger.warning(f"Failed to clean up file in SELECT callback: {e}")
        
        elif callback.action == CallbackAction.VOTE:
            # Placeholder for voting logic
            await context.bot.send_message(chat_id, f"🗳️ Голосование пока не реализовано.")

    # --- Register Handlers ---
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("play", play_cmd))
    app.add_handler(CommandHandler("radio", radio_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("skip", skip_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
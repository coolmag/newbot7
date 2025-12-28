from __future__ import annotations
import logging
import os
import asyncio
from math import ceil
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)

from radio import RadioManager
from config import Settings, MUSIC_CATALOG
from youtube import YouTubeDownloader
from keyboards import (
    get_track_search_keyboard, 
    get_pagination_keyboard, 
    get_main_menu_keyboard, 
    get_subcategory_keyboard
)

logger = logging.getLogger("handlers")

# ==================== КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает команду /start, отображая главное меню жанров."""
    text = "🎧 *Музыкальный комбайн*\n\nНажмите кнопку ниже, чтобы открыть меню жанров или воспользуйтесь командами:\n\n/play `<название>` - поиск трека\n/radio - случайная волна"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗂 Открыть меню жанров", callback_data="main_menu_genres")]
    ])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
        )
    elif update.message:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
        )

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Останавливает воспроизведение радио."""
    await context.application.radio_manager.stop(update.effective_chat.id)
    await update.message.reply_text("🛑 Плеер остановлен.")

async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропускает текущий трек в радио."""
    await context.application.radio_manager.skip(update.effective_chat.id)

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ищет и отправляет трек по запросу. /play <название трека>"""
    query_text = " ".join(context.args)
    if not query_text:
        await update.message.reply_text(
            "ℹ️ Укажите название трека после команды.\n\n*Пример:*\n`/play Daft Punk - Get Lucky`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    msg = await update.message.reply_text(f"🔎 Ищу: *{query_text}*...", parse_mode=ParseMode.MARKDOWN)
    
    tracks = await context.application.downloader.search(query=query_text, search_mode='track', limit=1)
    
    if tracks:
        await msg.delete()
        await _send_track(context, update.effective_chat.id, tracks[0].identifier)
    else:
        await msg.edit_text("😕 Ничего не найдено.")

async def radio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /radio — запускает случайное радио."""
    await update.message.reply_text("🎲 Запускаю случайную волну...")
    asyncio.create_task(context.application.radio_manager.start(
        chat_id=update.effective_chat.id, query="random"
    ))

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает неизвестные команды."""
    await update.message.reply_text("🤔 Команда не распознана. Жми /start")

# ==================== ГЛАВНЫЙ ОБРАБОТЧИК КНОПОК ====================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Центральный обработчик для всех inline-кнопок."""
    query = update.callback_query
    await query.answer()
    data = query.data

    logger.info(f"[CALLBACK] Received data: '{data}'")

    if data == "main_menu_start":
        logger.info("[CALLBACK] Branch: main_menu_start")
        await start(update, context)
    
    elif data == "main_menu_genres":
        logger.info("[CALLBACK] Branch: main_menu_genres")
        markup = get_main_menu_keyboard()
        await query.edit_message_text(
            "🗂 *Каталог жанров:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup
        )
        
    elif data.startswith("cat|"):
        logger.info(f"[CALLBACK] Branch: cat| with path '{data}'")
        path_str = data.removeprefix("cat|")
        if not path_str:
            await start(update, context)
            return

        path = path_str.split('|')
        
        try:
            current_level = MUSIC_CATALOG
            for p in path:
                current_level = current_level[p]
        except KeyError:
            logger.error(f"Invalid path in callback: {path_str}")
            await query.edit_message_text("❌ Ошибка в структуре меню!", reply_markup=get_main_menu_keyboard())
            return

        await query.edit_message_text(
            f"💿 *{path[-1]}:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_subcategory_keyboard(path_str)
        )

    elif data.startswith("play_cat|"):
        logger.info(f"[CALLBACK] Branch: play_cat| with path '{data}'")
        path_str = data.removeprefix("play_cat|")
        if not path_str:
            await query.edit_message_text("❗️Не удалось найти этот жанр.", reply_markup=get_main_menu_keyboard())
            return
            
        path = path_str.split('|')
        
        try:
            current_level = MUSIC_CATALOG
            for p in path[:-1]:
                current_level = current_level[p]
            search_query = current_level[path[-1]]
        except (KeyError, TypeError):
            search_query = " ".join(path) 
            logger.warning(f"Could not resolve radio query for path: {path_str}. Falling back to '{search_query}'")

        await query.edit_message_text(f"🎵 Запускаю: *{path[-1]}*...", parse_mode=ParseMode.MARKDOWN)
        asyncio.create_task(context.application.radio_manager.start(
            chat_id=query.message.chat_id, 
            query=str(search_query)
        ))

    elif data == "play_random":
        logger.info("[CALLBACK] Branch: play_random")
        await query.edit_message_text("🎲 Случайная волна...")
        asyncio.create_task(context.application.radio_manager.start(
            chat_id=query.message.chat_id, 
            query="top 50 global hits"
        ))

    elif data.startswith("sel_track|"):
        logger.info(f"[CALLBACK] Branch: sel_track| with video_id '{data}'")
        video_id = data.split("|", 1)[1]
        await query.edit_message_text("⏳ Загружаю трек...")
        await _send_track(context, query.message.chat_id, video_id)
        await start(update, context)

    elif data == "noop":
        logger.info("[CALLBACK] Branch: noop")
        pass

    else:
        logger.warning(f"[CALLBACK] Unhandled callback data: '{data}'")


# ==================== HELPERS ====================

async def _send_track(context: ContextTypes.DEFAULT_TYPE, chat_id: int, video_id: str):
    """Загружает и отправляет трек пользователю с кнопкой веб-плеера."""
    dl = context.application.downloader
    settings: Settings = context.application.settings
    res = await dl.download(video_id)
    
    if not res.success:
        await context.bot.send_message(chat_id, f"❌ Ошибка загрузки: {res.error_message}")
        return

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎧 Открыть плеер", web_app=WebAppInfo(url=settings.WEBHOOK_URL))]
    ])

    try:
        if res.file_id:
            await context.bot.send_audio(
                chat_id, 
                audio=res.file_id, 
                title=res.track_info.title, 
                performer=res.track_info.artist,
                reply_markup=markup
            )
        elif res.file_path:
            with open(res.file_path, 'rb') as f:
                msg = await context.bot.send_audio(
                    chat_id, 
                    audio=f, 
                    title=res.track_info.title, 
                    performer=res.track_info.artist, 
                    caption="#groove_ai",
                    reply_markup=markup
                )
                if msg.audio:
                    await dl.cache_file_id(video_id, msg.audio.file_id)
    finally:
        if res.file_path and os.path.exists(res.file_path):
            try: 
                os.unlink(res.file_path)
            except OSError as e:
                logger.error(f"Ошибка удаления временного файла {res.file_path}: {e}")

# ==================== РЕГИСТРАЦИЯ ====================

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    """Регистрирует все обработчики в приложении."""
    app.downloader = downloader
    app.radio_manager = radio
    app.settings = settings
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("radio", radio_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("skip", skip_command))
    
    # Обработчик кнопок (единственный и главный)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработка неизвестных команд (должна быть последней)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

from __future__ import annotations
import logging
import os
import asyncio
from math import ceil
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.constants import ParseMode, ChatType
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
    """Обрабатывает команду /start, отображая главное меню и кнопку плеера."""
    if not hasattr(context.application, 'settings'):
        logger.error("❌ Settings not found in application context")
        await update.message.reply_text("Ошибка конфигурации бота.")
        return

    settings: Settings = context.application.settings
    # Очищаем URL от пробелов, если они есть
    base_url = settings.BASE_URL.strip() if settings.BASE_URL else ""
    
    text = (
        "🎧 *Музыкальный комбайн*\n\n"
        "Нажмите кнопку ниже, чтобы запустить веб-плеер или открыть меню жанров.\n\n"
        "Команды:\n"
        "/play `<название>` - поиск трека\n"
        "/radio - случайная волна"
    )
    
    keyboard = []
    
    # Логика добавления кнопки плеера
    if base_url and base_url.startswith("https"):
        # WebApp кнопка работает ТОЛЬКО в личных чатах
        if update.effective_chat.type == ChatType.PRIVATE:
            keyboard.append([InlineKeyboardButton("🎧 Открыть плеер", web_app=WebAppInfo(url=base_url))])
        else:
            # В группах даем обычную ссылку, чтобы не было ошибки Button_type_invalid
            keyboard.append([InlineKeyboardButton("🎧 Открыть плеер (в браузере)", url=base_url)])
    
    # Кнопка меню жанров (работает везде)
    keyboard.append([InlineKeyboardButton("🗂 Открыть меню жанров", callback_data="main_menu_genres")])
    
    markup = InlineKeyboardMarkup(keyboard)

    try:
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
            )
        elif update.message:
            await update.message.reply_text(
                text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
            )
    except Exception as e:
        logger.error(f"Error in /start: {e}", exc_info=True)

async def player_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет кнопку для запуска веб-плеера."""
    if update.effective_chat.type == ChatType.CHANNEL:
        return

    settings: Settings = context.application.settings
    base_url = settings.BASE_URL.strip() if settings.BASE_URL else ""
    
    if not base_url or not base_url.startswith("https"):
        await update.message.reply_text("⚠️ URL плеера не настроен.")
        return

    text = "👇 Нажмите кнопку ниже, чтобы открыть плеер."
    
    # Та же логика безопасности
    if update.effective_chat.type == ChatType.PRIVATE:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎧 Открыть плеер", web_app=WebAppInfo(url=base_url))]
        ])
    else:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Открыть плеер", url=base_url)]
        ])
        
    await update.message.reply_text(text, reply_markup=markup)

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
    
    try:
        tracks = await context.application.downloader.search(query=query_text, search_mode='track', limit=1)
        
        if tracks:
            await msg.delete()
            # Передаем ChatType, чтобы внутри _send_track тоже была проверка
            chat_type = update.effective_chat.type
            await _send_track(context, update.effective_chat.id, tracks[0].identifier, chat_type)
        else:
            await msg.edit_text("😕 Ничего не найдено.")
    except Exception as e:
        logger.error(f"Error in /play: {e}", exc_info=True)
        await msg.edit_text("❌ Ошибка поиска.")

async def radio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /radio — запускает случайное радио."""
    await update.message.reply_text("🎲 Запускаю случайную волну...")
    asyncio.create_task(context.application.radio_manager.start(
        chat_id=update.effective_chat.id, 
        query="random",
        chat_type=update.message.chat.type
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
        await start(update, context)
    
    elif data == "main_menu_genres":
        markup = get_main_menu_keyboard()
        await query.edit_message_text(
            "🗂 *Каталог жанров:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=markup
        )
        
    elif data.startswith("cat|"):
        path_str = data[4:] 
        if not path_str:
            await start(update, context)
            return

        path = path_str.split('|')
        try:
            current_level = MUSIC_CATALOG
            for p in path:
                current_level = current_level[p]
        except KeyError:
            await query.edit_message_text("❌ Ошибка меню", reply_markup=get_main_menu_keyboard())
            return

        await query.edit_message_text(
            f"💿 *{path[-1]}:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_subcategory_keyboard(path_str)
        )

    elif data.startswith("play_cat|"):
        path_str = data[9:]
        if not path_str:
            await query.edit_message_text("❗️Ошибка жанра", reply_markup=get_main_menu_keyboard())
            return
            
        path = path_str.split('|')
        try:
            current_level = MUSIC_CATALOG
            for p in path[:-1]:
                current_level = current_level[p]
            search_query = current_level[path[-1]]
        except (KeyError, TypeError):
            search_query = " ".join(path) 

        await query.edit_message_text(f"🎵 Запускаю: *{path[-1]}*...", parse_mode=ParseMode.MARKDOWN)
        asyncio.create_task(context.application.radio_manager.start(
            chat_id=query.message.chat.id, 
            query=str(search_query),
            chat_type=query.message.chat.type
        ))

    elif data == "play_random":
        await query.edit_message_text("🎲 Случайная волна...")
        asyncio.create_task(context.application.radio_manager.start(
            chat_id=query.message.chat.id, 
            query="top 50 global hits",
            chat_type=query.message.chat.type
        ))

    elif data.startswith("sel_track|"):
        video_id = data.split("|", 1)[1]
        await query.edit_message_text("⏳ Загружаю трек...")
        await _send_track(context, query.message.chat.id, video_id, query.message.chat.type)
        await start(update, context)

    elif data == "noop":
        pass

# ==================== HELPERS ====================

async def _send_track(context: ContextTypes.DEFAULT_TYPE, chat_id: int, video_id: str, chat_type: str):
    """Загружает и отправляет трек пользователю."""
    dl = context.application.downloader
    settings: Settings = context.application.settings
    res = await dl.download(video_id)
    
    if not res.success:
        await context.bot.send_message(chat_id, f"❌ Ошибка загрузки: {res.error_message}")
        return

    markup = None
    base_url = settings.BASE_URL.strip() if settings.BASE_URL else ""
    
    # Кнопка плеера под треком (WebApp только в ЛС)
    if chat_type != ChatType.CHANNEL and base_url.startswith("https"):
        if chat_type == ChatType.PRIVATE:
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎧 Открыть плеер", web_app=WebAppInfo(url=base_url))]
            ])
        else:
             # В группах кнопку WebApp для конкретного трека лучше не давать или давать ссылку
             pass

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
            try: os.unlink(res.file_path)
            except OSError: pass

# ==================== РЕГИСТРАЦИЯ ====================

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    app.downloader = downloader
    app.radio_manager = radio
    app.settings = settings
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("player", player_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("radio", radio_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))


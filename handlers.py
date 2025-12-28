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

from radio import RadioManager
from config import Settings
from youtube import YouTubeDownloader
from keyboards import (
    get_track_search_keyboard, 
    get_pagination_keyboard, 
    get_main_menu_keyboard, 
    get_subcategory_keyboard,
    resolve_path
)


logger = logging.getLogger("handlers")

# Состояния
PAGE_SIZE = 5
SEARCH_LIMIT = 30
MENU, WAITING_ARTIST, WAITING_TRACK = range(3)

# ==================== КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает команду /start, отображая главное меню."""
    text = "🎧 *Музыкальный комбайн*\n\nВыберите категорию:"
    markup = get_main_menu_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
        )
    elif update.message:
        await update.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup
        )
    return MENU

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Останавливает воспроизведение радио."""
    await context.application.radio_manager.stop(update.effective_chat.id)
    await update.message.reply_text("🛑 Плеер остановлен.")

async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропускает текущий трек в радио."""
    await context.application.radio_manager.skip(update.effective_chat.id)

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /play — начинает поиск трека."""
    cancel_btn = InlineKeyboardButton("🔙 Отмена", callback_data="main_menu")
    await update.message.reply_text(
        "🎵 Введите название трека:", 
        reply_markup=InlineKeyboardMarkup([[cancel_btn]])
    )
    return WAITING_TRACK

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

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[int]:
    """Центральный обработчик для всех inline-кнопок."""
    query = update.callback_query
    await query.answer()
    data = query.data

    # Возврат в главное меню
    if data == "main_menu":
        return await start(update, context)

    # Навигация по категориям
    if data.startswith("cat|"):
        path_hash = data.removeprefix("cat|")
        path_str = resolve_path(path_hash)
        if not path_str:
            await query.edit_message_text("❗️Меню устарело. Пожалуйста, откройте заново.", reply_markup=get_main_menu_keyboard())
            return MENU
            
        path = path_str.split('|')
        
        await query.edit_message_text(
            f"💿 *{path[-1]}:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_subcategory_keyboard(path_str)
        )
        return MENU

    # Запуск радио по жанру
    if data.startswith("play_cat|"):
        path_hash = data.removeprefix("play_cat|")
        path_str = resolve_path(path_hash)
        if not path_str:
            await query.edit_message_text("❗️Не удалось найти этот жанр.", reply_markup=get_main_menu_keyboard())
            return MENU
            
        path = path_str.split('|')
        search_query = " ".join(path) # Fallback to path if lookup fails
        
        current_level = context.application.settings.MUSIC_CATALOG
        try:
            for p in path[:-1]:
                current_level = current_level[p]
            search_query = current_level[path[-1]]
        except (KeyError, TypeError):
            logger.warning(f"Could not resolve radio query for path: {path_str}. Falling back to '{search_query}'")

        await query.edit_message_text(f"🎵 Запускаю: *{path[-1]}*...", parse_mode=ParseMode.MARKDOWN)
        await context.application.radio_manager.start(
            query.message.chat_id, 
            str(search_query), 
            message_id=query.message.message_id
        )
        return MENU

    # Пагинация поиска
    if data.startswith("page|"):
        _, page, query_text = data.split("|", 2)
        await _send_artist_search_results(update, context, query_text, int(page))
        return MENU

    # Выбор трека из поиска
    if data.startswith("sel_track|"):
        video_id = data.split("|", 1)[1]
        await query.edit_message_text("⏳ Загружаю трек...")
        await _send_track(context, query.message.chat_id, video_id)
        return await start(update, context)

    if data == "noop":
        return None

    logger.warning(f"Unhandled button callback data: {data}")
    await query.message.reply_text("Неизвестная команда. Возвращаю в меню.", reply_markup=get_main_menu_keyboard())
    return MENU


# ==================== ПОИСК ====================

async def track_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает текстовый ввод для поиска трека."""
    query_text = update.message.text
    chat_id = update.effective_chat.id
    
    msg = await update.message.reply_text(f"🔎 Ищу: *{query_text}*...", parse_mode=ParseMode.MARKDOWN)
    
    # В режиме поиска трека ищем только один самый релевантный
    tracks = await context.application.downloader.search(query=query_text, search_mode='track', limit=1)
    
    if tracks:
        await msg.delete()
        await _send_track(context, chat_id, tracks[0].identifier)
    else:
        await msg.edit_text("😕 Ничего не найдено.")
    
    return await start(update, context)

# ==================== HELPERS ====================

async def _send_artist_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str, page: int):
    """Отправляет результаты поиска по артисту с пагинацией."""
    # Для поиска по артисту ищем больше треков
    tracks = await context.application.downloader.search(query=query_text, search_mode='artist', limit=SEARCH_LIMIT)
    
    if not tracks:
        reply_markup = get_main_menu_keyboard()
        text = "😕 Ничего не найдено."
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await context.bot.send_message(update.effective_chat.id, text, reply_markup=reply_markup)
        return

    total_pages = ceil(len(tracks) / PAGE_SIZE)
    start_offset = (page - 1) * PAGE_SIZE
    page_tracks = tracks[start_offset:start_offset + PAGE_SIZE]

    markup = InlineKeyboardMarkup(
        get_track_search_keyboard(page_tracks).inline_keyboard +
        get_pagination_keyboard(page, total_pages, query_text).inline_keyboard
    )
    
    text = f"👤 *{query_text}* (Стр. {page}/{total_pages})"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    else:
        await context.bot.send_message(update.effective_chat.id, text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)

async def _send_track(context: ContextTypes.DEFAULT_TYPE, chat_id: int, video_id: str):
    """Загружает и отправляет трек пользователю."""
    dl = context.application.downloader
    res = await dl.download(video_id)
    
    if not res.success:
        await context.bot.send_message(chat_id, f"❌ Ошибка загрузки: {res.error_message}")
        return

    try:
        if res.file_id:
            await context.bot.send_audio(chat_id, audio=res.file_id, title=res.track_info.title, performer=res.track_info.artist)
        elif res.file_path:
            with open(res.file_path, 'rb') as f:
                msg = await context.bot.send_audio(chat_id, audio=f, title=res.track_info.title, performer=res.track_info.artist, caption="#groove_ai")
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
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler("play", play_command),
            CallbackQueryHandler(button_callback), # Обработка кнопок как точка входа
        ],
        states={
            MENU: [
                CallbackQueryHandler(button_callback)
            ],
            WAITING_TRACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, track_search_handler),
                CallbackQueryHandler(button_callback, pattern="^main_menu$") 
            ],
        },
        fallbacks=[
            CommandHandler('start', start),
        ],
        allow_reentry=True
    )
    
    app.add_handler(conv_handler)
    
    # Команды, которые работают всегда, вне состояний
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CommandHandler("radio", radio_command))
    
    # Обработка неизвестных команд (должна быть последней)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

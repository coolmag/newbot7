from __future__ import annotations
import logging
import os
import asyncio
from math import ceil
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)

from radio import RadioManager
from config import Settings
from youtube import YouTubeDownloader
from models import VoteCallback, CallbackAction
from keyboards import get_track_search_keyboard, get_pagination_keyboard

logger = logging.getLogger("handlers")

# Состояния
PAGE_SIZE = 5
SEARCH_LIMIT = 30
MENU, WAITING_ARTIST, WAITING_TRACK = range(3)

# ==================== НАВИГАЦИЯ ====================

def _get_node_from_path(path: str, settings: Settings) -> Optional[Dict[str, Any]]:
    try:
        keys = path.split(':')
        node = settings.GENRE_DATA
        for key in keys:
            if 'children' in node:
                node = node['children'][key]
            else:
                node = node[key]
        return node
    except KeyError:
        return None

def _generate_keyboard_from_path(path: str, settings: Settings) -> InlineKeyboardMarkup:
    node = _get_node_from_path(path, settings)
    if not node:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Ошибка", callback_data="noop")]])

    buttons = []
    if 'children' in node:
        for key, child in node['children'].items():
            child_path = f"{path}:{key}"
            
            if 'children' in child:
                action = CallbackAction.NAVIGATE
                value = child_path
            elif 'query' in child:
                action = CallbackAction.START_RADIO
                value = child['query']
            elif 'action' in child:
                action = child['action']
                value = child.get('value', key)
            else:
                continue
            
            cb = VoteCallback(action, value).to_callback_data()
            buttons.append(InlineKeyboardButton(child['name'], callback_data=cb))

    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    
    nav_buttons = []
    if ':' in path:
        parent_path = ":".join(path.split(':')[:-1])
        nav_buttons.append(InlineKeyboardButton(
            "◀️ Назад", 
            callback_data=VoteCallback(CallbackAction.NAVIGATE, parent_path).to_callback_data()
        ))
    
    if path != "main_menu":
        nav_buttons.append(InlineKeyboardButton(
            "🔝 В начало", 
            callback_data=VoteCallback(CallbackAction.NAVIGATE, "main_menu").to_callback_data()
        ))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    return InlineKeyboardMarkup(keyboard)

# ==================== КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = "🎧 *Музыкальный комбайн v18*\n\n🎛 Выберите категорию:"
    markup = _generate_keyboard_from_path("main_menu", context.application.settings)
    
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        except Exception:
            await update.callback_query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    elif update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    
    return MENU

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.application.radio_manager.stop(update.effective_chat.id)
    await update.message.reply_text("🛑 Плеер остановлен.")

async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.application.radio_manager.skip(update.effective_chat.id)

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /play — начинает поиск трека."""
    cancel_btn = InlineKeyboardButton(
        "🔙 Отмена",
        callback_data=VoteCallback(CallbackAction.NAVIGATE, "main_menu").to_callback_data()
    )
    await update.message.reply_text("🎵 Введите название трека:", reply_markup=InlineKeyboardMarkup([[cancel_btn]]))
    return WAITING_TRACK

async def radio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /radio — запускает случайное радио."""
    await update.message.reply_text("🎲 Запускаю случайную волну...")
    asyncio.create_task(context.application.radio_manager.start(
        chat_id=update.effective_chat.id, query="random"
    ))

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤔 Команда не распознана. Жми /start")

# ==================== КНОПКИ ПЛЕЕРА ====================

async def stop_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🛑 Останавливаю...")
    await context.application.radio_manager.stop(update.effective_chat.id)
    await query.message.reply_text("🛑 Радио остановлено.")

async def skip_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏭ Пропускаю...")
    await context.application.radio_manager.skip(update.effective_chat.id)

async def select_track_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    callback = VoteCallback.from_callback_data(query.data)
    if not callback:
        return
    
    await query.edit_message_text("⏳ Загружаю трек...")
    await _send_track(context, query.message.chat_id, callback.value)

# ==================== 4. НАВИГАЦИЯ ПО МЕНЮ ====================

# Новый обработчик кнопок меню WebApp и жанров
from keyboards import get_main_menu_keyboard, get_subcategory_keyboard
from config import get_settings

from keyboards import get_main_menu_keyboard, get_subcategory_keyboard
from config import get_settings
from telegram.constants import ChatType
from logging import getLogger
from config import get_settings
from keyboards import get_main_menu_keyboard, get_subcategory_keyboard
from radio import RadioManager
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional
from telegram import Update

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data

    # Главное меню
    if data == "main_menu":
        await query.edit_message_text(
            "💿 *Каталог жанров:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_keyboard()
        )
        return

    # Навигация по категориям и подкатегориям
    if data.startswith("cat|"):
        from keyboards import shorten_path # если есть, иначе заменить на правильный импорт
        from keyboards import resolve_path
        path_hash = data.removeprefix("cat|")
        path_str = resolve_path(path_hash)
        if not path_str:
            await query.edit_message_text("❗️Меню устарело. Пожалуйста, откройте заново.")
            return
        path = path_str.split('|')
        current_level = context.application.settings.MUSIC_CATALOG
        try:
            for p in path:
                current_level = current_level[p]
        except Exception:
            await query.edit_message_text("❌ Ошибка в структуре меню!")
            return
        await query.edit_message_text(
            f"💿 *{path[-1]}:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_subcategory_keyboard(path_str)
        )
        return

    # Запуск радио жанра
    if data.startswith("play_cat|"):
        from keyboards import resolve_path
        path_hash = data.removeprefix("play_cat|")
        path_str = resolve_path(path_hash)
        if not path_str:
            await query.edit_message_text("❗️Не удалось найти этот жанр. Открой меню заново.")
            return
        path = path_str.split('|')
        current_level = context.application.settings.MUSIC_CATALOG
        try:
            for p in path[:-1]:
                current_level = current_level[p]
            search_query = current_level[path[-1]]
        except Exception:
            search_query = "top 50 hits"
        await query.edit_message_text("🎵 Запускаю музыку...")
        await context.application.radio_manager.start(query.message.chat_id, str(search_query), query.message.chat.type, message_id=query.message.message_id)
        return

    # Случайный микс
    if data == "play_random":
        await query.edit_message_text("🎲 Случайная волна...")
        await context.application.radio_manager.start(query.message.chat_id, "top 50 global hits", query.message.chat.type, message_id=query.message.message_id)
        return

    # Обычные действия плеера
    if data == "stop_radio":
        await context.application.radio_manager.stop(query.message.chat_id)
        await query.edit_message_text("🛑 Радио остановлено.")
        return
    if data == "skip_track":
        await context.application.radio_manager.skip(query.message.chat_id)
        await query.answer("⏭️")
        return

    # Нет действия
    if data == "noop":
        await query.answer()
        return
    await query.answer("Неизвестная команда (Версия меню может быть устарела)")

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    callback = VoteCallback.from_callback_data(query.data)
    if not callback:
        logger.warning(f"Failed to parse: {query.data}")
        return MENU
    
    action, value = callback.action, callback.value
    settings: Settings = context.application.settings

    if action == CallbackAction.NAVIGATE:
        node = _get_node_from_path(value, settings)
        if node:
            title = node.get('name', 'Меню')
            markup = _generate_keyboard_from_path(value, settings)
            await query.edit_message_text(f"👇 *{title}*", parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        else:
            markup = _generate_keyboard_from_path("main_menu", settings)
            await query.edit_message_text("❌ Ошибка", reply_markup=markup)
        return MENU

    elif action == CallbackAction.START_RADIO:
        await query.edit_message_text("🎵 Запускаю музыку...")
        asyncio.create_task(context.application.radio_manager.start(
            chat_id=query.message.chat_id, query=value
        ))
        return MENU

    elif action == "random_radio":
        await query.edit_message_text("🎲 Случайная волна...")
        asyncio.create_task(context.application.radio_manager.start(
            chat_id=query.message.chat_id, query="random"
        ))
        return MENU

    # Поиск по артисту
    elif action == CallbackAction.SEARCH_ARTIST:
        cancel_btn = InlineKeyboardButton(
            "🔙 Отмена",
            callback_data=VoteCallback(CallbackAction.NAVIGATE, "main_menu").to_callback_data()
        )
        await query.edit_message_text("👤 Напишите имя артиста:", reply_markup=InlineKeyboardMarkup([[cancel_btn]]))
        return WAITING_ARTIST
        
    # Поиск по треку
    elif action == CallbackAction.SEARCH_TRACK:
        cancel_btn = InlineKeyboardButton(
            "🔙 Отмена",
            callback_data=VoteCallback(CallbackAction.NAVIGATE, "main_menu").to_callback_data()
        )
        await query.edit_message_text("🎵 Напишите название трека:", reply_markup=InlineKeyboardMarkup([[cancel_btn]]))
        return WAITING_TRACK

    # Пагинация
    elif action == CallbackAction.PAGE:
        try:
            page_str, search_query = value.split(":", 1)
            await _send_artist_search_results(update, context, search_query, int(page_str))
        except Exception as e:
            logger.error(f"Page error: {e}")
        return MENU

    # Отмена
    elif action == CallbackAction.CANCEL:
        return await start(update, context)
        
    return MENU

# ==================== ПОИСК ====================

async def artist_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await _send_artist_search_results(update, context, update.message.text, 1)
    return MENU

async def track_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query_text = update.message.text
    chat_id = update.effective_chat.id
    
    msg = await update.message.reply_text(f"🔎 Ищу: *{query_text}*...", parse_mode=ParseMode.MARKDOWN)
    tracks = await context.application.downloader.search(query=query_text, search_mode='track', limit=1)
    
    if tracks:
        await msg.delete()
        await _send_track(context, chat_id, tracks[0].identifier)
    else:
        await msg.edit_text("😕 Ничего не найдено.")
    
    return MENU

# ==================== HELPERS ====================

async def _send_artist_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str, page: int):
    tracks = await context.application.downloader.search(query=query_text, search_mode='artist', limit=SEARCH_LIMIT)
    
    if not tracks:
        await context.bot.send_message(update.effective_chat.id, "😕 Ничего не найдено.")
        return

    total_pages = ceil(len(tracks) / PAGE_SIZE)
    start = (page - 1) * PAGE_SIZE
    page_tracks = tracks[start:start + PAGE_SIZE]

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
    dl = context.application.downloader
    res = await dl.download(video_id)
    
    if not res.success:
        await context.bot.send_message(chat_id, f"❌ Ошибка: {res.error_message}")
        return

    try:
        if res.file_id:
            await context.bot.send_audio(chat_id, audio=res.file_id, title=res.track_info.title, performer=res.track_info.artist)
        elif res.file_path:
            with open(res.file_path, 'rb') as f:
                msg = await context.bot.send_audio(chat_id, audio=f, title=res.track_info.title, performer=res.track_info.artist)
                if msg.audio:
                    await dl.cache_file_id(video_id, msg.audio.file_id)
    finally:
        if res.file_path and os.path.exists(res.file_path):
            try: os.unlink(res.file_path)
            except: pass

async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer("♻️ Перезагружаю...")
        await start(update, context)

# ==================== РЕГИСТРАЦИЯ ====================

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    app.downloader = downloader
    app.radio_manager = radio
    app.settings = settings
    
    # 1. Глобальные команды
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CommandHandler("play", play_command))
    app.add_handler(CommandHandler("radio", radio_command))
    
    # 2. Кнопки плеера (ИСПРАВЛЕНО: добавлен .* в паттерн)
    app.add_handler(CallbackQueryHandler(stop_button, pattern=f"^{CallbackAction.STOP}:.*"))
    app.add_handler(CallbackQueryHandler(skip_button, pattern=f"^{CallbackAction.SKIP}:.*"))
    app.add_handler(CallbackQueryHandler(select_track_button, pattern=f"^{CallbackAction.SELECT}:.*"))
    
    # 3. ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
        ],
        states={
            MENU: [
                CallbackQueryHandler(menu_handler),
            ],
            WAITING_ARTIST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, artist_search_handler),
                CallbackQueryHandler(menu_handler),
            ],
            WAITING_TRACK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, track_search_handler),
                CallbackQueryHandler(menu_handler),
            ],
        },
        fallbacks=[
            CommandHandler('start', start),
        ],
        per_message=True,
        per_chat=True,
    )
    app.add_handler(conv_handler)
    
    # 4. Наш главный обработчик меню!
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # 5. Неизвестные команды (в самом конце)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

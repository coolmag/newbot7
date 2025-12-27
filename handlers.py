from __future__ import annotations
import logging
import os
import asyncio
from math import ceil
from typing import Optional, Dict, Any, List

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

# Constants & Conversation states
PAGE_SIZE = 5
SEARCH_LIMIT = 30
MENU, WAITING_ARTIST, WAITING_TRACK = range(3)

# +++ 1. Вспомогательные функции (Логика JSON) +++

def _get_node_from_path(path: str, settings: Settings) -> Optional[Dict[str, Any]]:
    """Получает узел меню из JSON по пути."""
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
    """Генерирует клавиатуру на основе JSON."""
    node = _get_node_from_path(path, settings)
    if not node:
        return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Ошибка меню", callback_data="noop")]])

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
            
            buttons.append(InlineKeyboardButton(child['name'], callback_data=VoteCallback(action, value).to_callback_data()))

    # Раскладка в 2 колонки
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    
    # Кнопки навигации
    nav_buttons = []
    if ':' in path:
        parent_path = ":".join(path.split(':')[:-1])
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(CallbackAction.NAVIGATE, parent_path).to_callback_data()))
    
    if path != "main_menu":
         nav_buttons.append(InlineKeyboardButton("🔝 В начало", callback_data=VoteCallback(CallbackAction.NAVIGATE, "main_menu").to_callback_data()))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
        
    return InlineKeyboardMarkup(keyboard)

# +++ 2. Обработчики Команд (Global) +++

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда /start - Вход в меню."""
    text = "🎧 *Музыкальный комбайн v17*\n\n🎛 Управление через меню ниже:"
    markup = _generate_keyboard_from_path("main_menu", context.application.settings)
    
    # Если вызвано кнопкой (например, при отмене поиска)
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        except Exception:
            await update.callback_query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    return MENU

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stop"""
    await context.application.radio_manager.stop(update.effective_chat.id)
    await update.message.reply_text("🛑 Плеер остановлен.")

async def skip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /skip"""
    await context.application.radio_manager.skip(update.effective_chat.id)
    # Сообщение не отправляем, бот просто переключит трек

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /play - Запускает случайное радио"""
    await update.message.reply_text("🎲 Запускаю случайную волну...")
    asyncio.create_task(context.application.radio_manager.start(chat_id=update.effective_chat.id, query="random"))

async def radio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /radio - Перенаправляет в меню"""
    await update.message.reply_text("📡 Чтобы выбрать станцию, используйте меню:", reply_markup=_generate_keyboard_from_path("main_menu", context.application.settings))

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Неизвестная команда"""
    await update.message.reply_text("🤔 Команда не распознана. Жми /start")

# +++ 3. Обработчики Кнопок Плеера (Global Buttons) +++

async def stop_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка 'Стоп' под сообщением"""
    query = update.callback_query
    await query.answer("Останавливаю...")
    await context.application.radio_manager.stop(update.effective_chat.id)
    await query.message.reply_text("🛑 Радио остановлено.")

async def skip_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка 'Пропустить' под сообщением"""
    query = update.callback_query
    await query.answer("Пропускаю трек...")
    await context.application.radio_manager.skip(update.effective_chat.id)

async def select_track_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор трека из поиска"""
    query = update.callback_query
    await query.answer()
    
    callback = VoteCallback.from_callback_data(query.data)
    if not callback: return
    
    await query.edit_message_text("⏳ Загружаю выбранный трек...")
    await _send_track(context, query.message.chat_id, callback.value)

# +++ 4. Логика Меню (Conversation) +++

async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка навигации по папкам и жанрам."""
    query = update.callback_query
    await query.answer()
    
    callback = VoteCallback.from_callback_data(query.data)
    if not callback: return MENU
    
    action, value = callback.action, callback.value
    settings: Settings = context.application.settings

    if action == CallbackAction.NAVIGATE:
        node = _get_node_from_path(value, settings)
        if node:
            title = node.get('name', 'Меню')
            markup = _generate_keyboard_from_path(value, settings)
            await query.edit_message_text(f"👇 *{title}*", parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        else:
            await query.edit_message_text("❌ Ошибка пути.", reply_markup=_generate_keyboard_from_path("main_menu", settings))
        return MENU

    elif action == CallbackAction.START_RADIO:
        await query.answer("🚀 Поехали!", show_alert=False)
        asyncio.create_task(context.application.radio_manager.start(chat_id=query.message.chat_id, query=value))
        return MENU 

    elif action == "random_radio":
        await query.answer("🎲 Удачи!", show_alert=False)
        asyncio.create_task(context.application.radio_manager.start(chat_id=query.message.chat_id, query="random"))
        return MENU

    elif action == CallbackAction.SEARCH_ARTIST:
        await query.edit_message_text("👤 Напишите имя артиста:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data=VoteCallback(CallbackAction.NAVIGATE, "main_menu").to_callback_data())]]))
        return WAITING_ARTIST
        
    elif action == CallbackAction.SEARCH_TRACK:
        await query.edit_message_text("🎵 Напишите название трека:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data=VoteCallback(CallbackAction.NAVIGATE, "main_menu").to_callback_data())]]))
        return WAITING_TRACK

    elif action == CallbackAction.PAGE:
        # Пагинация поиска
        try:
            page_num_str, search_query = value.split(":", 1)
            await _send_artist_search_results(update, context, query_text=search_query, page=int(page_num_str))
        except Exception as e:
            logger.error(f"Pag error: {e}")
            await query.answer("❌ Ошибка")
        return MENU
        
    return MENU

# +++ 5. Логика Поиска (Text Input) +++

async def search_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, mode: str) -> int:
    """Общий обработчик для ввода текста поиска."""
    query_text = update.message.text
    chat_id = update.effective_chat.id
    
    # Пытаемся удалить сообщение пользователя для чистоты
    try: await context.bot.delete_message(chat_id, update.message.message_id)
    except: pass
    
    # Удаляем предыдущее сообщение бота ("Введите имя...")
    try: await context.bot.delete_message(chat_id, update.message.reply_to_message.message_id)
    except: pass

    if mode == 'artist':
        await _send_artist_search_results(update, context, query_text, 1)
        return MENU
    elif mode == 'track':
        msg = await update.message.reply_text(f"🔎 Ищу: *{query_text}*...", parse_mode=ParseMode.MARKDOWN)
        tracks = await context.application.downloader.search(query=query_text, search_mode='track', limit=1)
        if tracks:
            await msg.delete()
            await _send_track(context, chat_id, tracks[0].identifier)
        else:
            await msg.edit_text("😕 Ничего не найдено.")
        return MENU

async def artist_input_wrapper(u, c): return await search_input_handler(u, c, 'artist')
async def track_input_wrapper(u, c): return await search_input_handler(u, c, 'track')

# +++ 6. Helpers (Отправка и Загрузка) +++

async def _send_artist_search_results(update: Update, context: ContextTypes.DEFAULT_TYPE, query_text: str, page: int):
    tracks = await context.application.downloader.search(query=query_text, search_mode='artist', limit=SEARCH_LIMIT)
    if not tracks:
        await context.bot.send_message(update.effective_chat.id, "😕 Не нашел такого артиста.")
        return

    total_pages = ceil(len(tracks) / PAGE_SIZE)
    start = (page - 1) * PAGE_SIZE
    page_tracks = tracks[start : start + PAGE_SIZE]

    if not page_tracks:
        await context.bot.send_message(update.effective_chat.id, "😕 Пустая страница.")
        return

    markup = InlineKeyboardMarkup(
        get_track_search_keyboard(page_tracks).inline_keyboard +
        get_pagination_keyboard(page, total_pages, query_text).inline_keyboard
    )
    
    text = f"👤 **Результаты: {query_text}** (Стр. {page}/{total_pages})"
    
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
            msg = await context.bot.send_audio(chat_id, audio=res.file_id, title=res.track_info.title, performer=res.track_info.artist, duration=res.track_info.duration, thumbnail=res.track_info.thumbnail_url)
        elif res.file_path:
            with open(res.file_path, 'rb') as f:
                msg = await context.bot.send_audio(chat_id, audio=f, title=res.track_info.title, performer=res.track_info.artist, duration=res.track_info.duration, thumbnail=res.track_info.thumbnail_url)
                if msg.audio: await dl.cache_file_id(video_id, msg.audio.file_id)
    finally:
        if res.file_path and os.path.exists(res.file_path):
            try: os.unlink(res.file_path)
            except: pass

async def global_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Если бот перезагрузился и забыл состояние, эта функция восстановит меню."""
    if update.callback_query:
        await update.callback_query.answer("♻️ Восстанавливаю меню...")
        await start(update, context)

# +++ 7. SETUP (Регистрация всего) +++

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    app.downloader = downloader
    app.radio_manager = radio
    app.settings = settings
    
    # 1. КОМАНДЫ (Global)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("skip", skip_command))
    app.add_handler(CommandHandler("play", play_command))   # Добавили /play
    app.add_handler(CommandHandler("radio", radio_command)) # Добавили /radio

    # 2. КНОПКИ УПРАВЛЕНИЯ (Global - работают всегда)
    app.add_handler(CallbackQueryHandler(stop_button, pattern=f"^{CallbackAction.STOP}:.*"))
    app.add_handler(CallbackQueryHandler(skip_button, pattern=f"^{CallbackAction.SKIP}:.*"))
    app.add_handler(CallbackQueryHandler(select_track_button, pattern=f"^{CallbackAction.SELECT}:.*"))

    # 3. МЕНЮ (State machine)
    conv_handler = ConversationHandler(
        entry_points=[
            # Вход через навигацию (если юзер нажал кнопку меню)
            CallbackQueryHandler(menu_callback_handler, pattern=f"^{CallbackAction.NAVIGATE}:main_menu$"),
            # Вход через start (если юзер уже в диалоге)
            CommandHandler('start', start)
        ],
        states={
            MENU: [CallbackQueryHandler(menu_callback_handler)],
            WAITING_ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, artist_input_wrapper)],
            WAITING_TRACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, track_input_wrapper)],
        },
        fallbacks=[CommandHandler('start', start)],
        per_message=False
    )
    app.add_handler(conv_handler)

    # 4. Fallback (если кнопка нажата, а бот забыл состояние)
    app.add_handler(CallbackQueryHandler(global_fallback))
    
    # 5. Неизвестные команды (в самом конце)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

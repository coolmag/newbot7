from __future__ import annotations
import logging
import os
import random
from typing import Optional

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters
)
from telegram.error import BadRequest

from radio import RadioManager
from config import Settings
from youtube import YouTubeDownloader
from models import VoteCallback, CallbackAction

logger = logging.getLogger("handlers")

# Conversation states
MENU, WAITING_ARTIST, WAITING_TRACK = range(3)

# +++ Keyboard Generators +++

def _generate_main_menu_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    """Level 0: Generates the main 'Control Panel' keyboard."""
    buttons = [
        InlineKeyboardButton(
            button["text"],
            callback_data=VoteCallback(action=button["action"], value="go").to_callback_data()
        ) for button in settings.GENRE_DATA["main_menu"]["buttons"]
    ]
    return InlineKeyboardMarkup([buttons[i:i + 2] for i in range(0, len(buttons), 2)])

def _generate_era_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    """Level 1: Generates the Era selection keyboard."""
    buttons = [
        InlineKeyboardButton(
            data["name"],
            callback_data=VoteCallback(action=CallbackAction.ERA, value=era_key).to_callback_data()
        ) for era_key, data in settings.GENRE_DATA.items() if era_key not in ["main_menu", "moods"]
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ В главное меню", callback_data=VoteCallback(action="main_menu", value="back").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_mood_keyboard(settings: Settings) -> InlineKeyboardMarkup:
    buttons = []
    # This is a special case where we start radio from a subgenre-like menu
    for mood_key, mood_data in settings.GENRE_DATA["moods"]["subgenres"].items():
        # We use DECADE action to directly start the radio
        callback_data = VoteCallback(action=CallbackAction.DECADE, value=f"moods:{mood_key}:all").to_callback_data()
        buttons.append(InlineKeyboardButton(mood_data["name"], callback_data=callback_data))

    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ В главное меню", callback_data=VoteCallback(action="main_menu", value="back").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_subgenre_keyboard(settings: Settings, era_key: str) -> InlineKeyboardMarkup:
    """Level 2: Generates the Subgenre selection keyboard for a given Era."""
    buttons = [
        InlineKeyboardButton(
            sub_data["name"],
            callback_data=VoteCallback(action=CallbackAction.SUBGENRE, value=f"{era_key}:{sub_key}").to_callback_data()
        ) for sub_key, sub_data in settings.GENRE_DATA[era_key].get("subgenres", {{}}).items()
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(action=CallbackAction.ERA, value="main_menu").to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

def _generate_decade_keyboard(settings: Settings, era_key: str, subgenre_key: str) -> InlineKeyboardMarkup:
    """Level 3: Generates the Decade selection keyboard for a given Subgenre."""
    buttons = [
        InlineKeyboardButton(
            decade_data["name"],
            callback_data=VoteCallback(action=CallbackAction.DECADE, value=f"{era_key}:{subgenre_key}:{decade_key}").to_callback_data()
        ) for decade_key, decade_data in settings.GENRE_DATA[era_key]["subgenres"][subgenre_key].get("decades", {{}}).items()
    ]
    keyboard = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data=VoteCallback(action=CallbackAction.ERA, value=era_key).to_callback_data())])
    return InlineKeyboardMarkup(keyboard)

# +++ Main Entry Point and State Handlers +++

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and shows the main menu."""
    text = "🎧 *Музыкальный комбайн v9*\n\nВыберите действие:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_main_menu_keyboard(context.application.settings))
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_main_menu_keyboard(context.application.settings))
    return MENU

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles all button clicks within the main menu navigation."""
    query = update.callback_query
    await query.answer()
    callback = VoteCallback.from_callback_data(query.data)
    if not callback: return MENU # Stay in menu on invalid callback

    settings = context.application.settings
    action = callback.action
    value = callback.value

    if action == "main_menu":
        await query.edit_message_text("🎧 *Музыкальный комбайн v9*\n\nВыберите действие:", parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_main_menu_keyboard(settings))
        return MENU
    elif action == "menu_eras":
        await query.edit_message_text("👇 Выбери эпоху:", reply_markup=_generate_era_keyboard(settings))
        return MENU
    elif action == "menu_moods":
        await query.edit_message_text("🌈 Выбери настроение:", reply_markup=_generate_mood_keyboard(settings))
        return MENU
    elif action == "search_artist":
        await query.edit_message_text("👤 Введите имя артиста:")
        return WAITING_ARTIST
    elif action == "search_track":
        await query.edit_message_text("🎵 Введите название трека:")
        return WAITING_TRACK
    elif action == "random_radio":
        await query.edit_message_text("🎲 Ищу случайную волну...")
        context.application.create_task(context.application.radio_manager.start(chat_id=query.message.chat_id, query="random"))
        return ConversationHandler.END
    elif action == CallbackAction.ERA:
        era_name = settings.GENRE_DATA.get(value, {{}}).get("name", "Музыка")
        await query.edit_message_text(f"🎧 *{era_name}*\n\nВыберите поджанр:", parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_subgenre_keyboard(settings, value))
        return MENU
    elif action == CallbackAction.SUBGENRE:
        try:
            era_key, sub_key = value.split(":")
            sub_name = settings.GENRE_DATA[era_key]["subgenres"][sub_key].get("name", "Музыка")
            await query.edit_message_text(f"🕰️ *{sub_name}*\n\nВыберите десятилетие:", parse_mode=ParseMode.MARKDOWN, reply_markup=_generate_decade_keyboard(settings, era_key, sub_key))
            return MENU
        except (ValueError, KeyError) as e:
            logger.error(f"Invalid SUBGENRE callback: {value} - {e}")
            await query.edit_message_text("❌ Меню устарело. Пожалуйста, используйте /start.")
            return ConversationHandler.END
    elif action == CallbackAction.DECADE:
        try:
            # This handles both mood and genre selections
            parts = value.split(":")
            if len(parts) == 3: # Era -> Sub -> Decade
                era_key, sub_key, decade_key = parts
                era_data = settings.GENRE_DATA[era_key]
                sub_data = era_data["subgenres"][sub_key]
                decade_data = sub_data["decades"][decade_key]
                search_query = decade_data["query"]
                display_name = f"{sub_data['name']} ({decade_data['name']})"
            elif len(parts) == 2: # Moods -> Mood
                era_key, mood_key = parts
                mood_data = settings.GENRE_DATA[era_key]["subgenres"][mood_key]
                search_query = mood_data["query"]
                display_name = mood_data["name"]
                decade_key = None # No decade for moods
            else:
                raise ValueError("Invalid DECADE callback format")

            await query.edit_message_text(f"🛰️ Настраиваюсь на волну: *{display_name}*...", parse_mode=ParseMode.MARKDOWN)
            context.application.create_task(
                context.application.radio_manager.start(chat_id=query.message.chat_id, query=search_query, decade=decade_key, display_name=display_name)
            )
            return ConversationHandler.END
        except (ValueError, KeyError, IndexError) as e:
            logger.error(f"Invalid DECADE callback: {value} - {e}")
            await query.edit_message_text("❌ Меню устарело. Пожалуйста, используйте /start.")
            return ConversationHandler.END

    return MENU # Default to staying in the menu

async def search_artist_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    artist_name = update.message.text
    await update.message.reply_text(f"🔎 Ищу лучшие треки: *{artist_name}*", parse_mode=ParseMode.MARKDOWN)

    tracks = await context.application.downloader.search(query=artist_name, search_mode='artist', limit=10)

    if not tracks:
        await update.message.reply_text("😕 Не удалось найти треки этого исполнителя.")
    else:
        text = f"**Лучшие треки {artist_name}:**\n\n" + "\n".join([f"{i}. {t.title}" for i, t in enumerate(tracks, 1)])
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=get_track_search_keyboard(tracks))

    return ConversationHandler.END

async def search_track_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    track_name = update.message.text
    msg = await update.message.reply_text(f"🔎 Ищу трек: *{track_name}*", parse_mode=ParseMode.MARKDOWN)

    tracks = await context.application.downloader.search(query=track_name, search_mode='track', limit=1)

    if not tracks:
        await msg.edit_text("😕 Ничего не найдено.")
    else:
        await msg.delete()
        await _send_track(context, update.message.chat_id, tracks[0].identifier, context.application.downloader)

    return ConversationHandler.END

async def select_track_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles when a user selects a track from a search result."""
    query = update.callback_query
    await query.answer()
    callback = VoteCallback.from_callback_data(query.data)
    if not callback or callback.action != CallbackAction.SELECT: return ConversationHandler.END

    await query.message.edit_text("⏳ Готовлю выбранный трек к отправке...")
    context.application.create_task(
        _send_track(context, query.message.chat_id, callback.value, context.application.downloader)
    )
    return ConversationHandler.END

async def stop_radio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.application.radio_manager.stop(update.effective_chat.id)
    await update.effective_message.reply_text("🛑 Радио остановлено.")

async def skip_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.application.radio_manager.skip(update.effective_chat.id)

def setup_handlers(app: Application, radio: RadioManager, settings: Settings, downloader: YouTubeDownloader):
    app.downloader = downloader
    app.radio_manager = radio
    app.settings = settings

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('radio', start)],
        states={
            MENU: [
                CallbackQueryHandler(menu_handler),
                # Also handle direct track selections from search results
                CallbackQueryHandler(select_track_handler, pattern=f"^{CallbackAction.SELECT}:.*")
            ],
            WAITING_ARTIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_artist_handler)],
            WAITING_TRACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_track_handler)],
        },
        fallbacks=[CommandHandler('start', start)], # Allow restarting the conversation
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("stop", stop_radio))
    app.add_handler(CommandHandler("skip", skip_track))
    # Direct search not part of conversation
    # app.add_handler(CommandHandler(["play", "search"], search_or_play_cmd))
    # Direct track selection from outside the main menu conversation
    app.add_handler(CallbackQueryHandler(select_track_handler, pattern=f"^{CallbackAction.SELECT}:.*"))
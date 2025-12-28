from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import get_settings
import hashlib

# Глобальное хранилище путей
PATH_STORE = {}

def shorten_path(path: str) -> str:
    """Генерирует короткий хэш пути (например 'Pop|Hits') для компактных callback'ов."""
    if not isinstance(path, str):
        path = str(path)
    h = hashlib.md5(path.encode()).hexdigest()[:10]
    PATH_STORE[h] = path
    return h

def resolve_path(hash_key: str) -> str:
    """Получает путь по хэшу через PATH_STORE."""
    return PATH_STORE.get(hash_key, "")

def preload_paths(catalog, parent_path=""):
    """Рекурсивно наполняет PATH_STORE всеми путями из каталога."""
    for key, val in catalog.items():
        curr_path = f"{parent_path}|{key}" if parent_path else key
        h = shorten_path(curr_path)
        if isinstance(val, dict):
            preload_paths(val, curr_path)

# Заполнить PATH_STORE при импорте
settings = get_settings()
preload_paths(settings.MUSIC_CATALOG)

def get_main_menu_keyboard():
    categories = list(settings.MUSIC_CATALOG.keys())
    keyboard = []
    for cat in categories:
        cb = "cat|" + shorten_path(cat)
        keyboard.append([InlineKeyboardButton(cat, callback_data=cb)])
    keyboard.append([InlineKeyboardButton("🎲 Случайный микс", callback_data="play_random")])
    return InlineKeyboardMarkup(keyboard)

def get_subcategory_keyboard(path_str):
    path = path_str.split('|')
    current_level = settings.MUSIC_CATALOG
    for p in path:
        current_level = current_level[p]
    keyboard = []
    for name, val in current_level.items():
        full_path = f"{path_str}|{name}"
        if isinstance(val, dict):
            callback = "cat|" + shorten_path(full_path)
            keyboard.append([InlineKeyboardButton(f"📂 {name}", callback_data=callback)])
        else:
            callback = "play_cat|" + shorten_path(full_path)
            keyboard.append([InlineKeyboardButton(f"▶️ {name}", callback_data=callback)])
    # Кнопка «Назад»
    if '|' in path_str:
        parent_path = '|'.join(path[:-1])
        back_cb = "cat|" + shorten_path(parent_path)
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data=back_cb)])
    else:
        keyboard.append([InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

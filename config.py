from pathlib import Path
from typing import List, Dict, Any, Optional
from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    
    # --- Mandatory Settings (Переменные окружения) ---
    # В Railway переменная должна называться TELEGRAM_TOKEN или BOT_TOKEN
    # Pydantic сам найдет её, если имя совпадает.
    # Если в main.py используется settings.TOKEN, можно добавить алиас, но обычно BOT_TOKEN ок.
    BOT_TOKEN: str 
    WEBHOOK_URL: str 
    
    # Если BASE_URL не задан, можно попробовать взять WEBHOOK_URL
    BASE_URL: str = "" 

    # --- Optional Settings ---
    ADMIN_IDS: str = ""
    COOKIES_CONTENT: str = ""
    PROXY_URL: Optional[str] = None
    
    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent
    DOWNLOADS_DIR: Path = BASE_DIR / "downloads"
    TEMP_AUDIO_DIR: Path = BASE_DIR / "temp_audio"
    CACHE_DB_PATH: Path = BASE_DIR / "cache.db"
    COOKIES_FILE: Path = BASE_DIR / "cookies.txt"
    
    # --- App Logic ---
    LOG_LEVEL: str = "INFO"
    MAX_FILE_SIZE_MB: int = 49  # Telegram limit is 50MB (ставим 49 для запаса)
    
    # --- Radio & Search ---
    RADIO_MIN_DURATION_S: int = 60    
    RADIO_MAX_DURATION_S: int = 900   
    GENRE_SEARCH_MIN_DURATION_S: int = 120   
    GENRE_SEARCH_MAX_DURATION_S: int = 600 
    
    # --- Fields populated by validators ---
    ADMIN_ID_LIST: List[int] = []
    
    # --- СТРУКТУРА МЕНЮ (Вшитая в код) ---
    # Мы убрали загрузку из файла, чтобы избежать ошибок FileNotFoundError
    GENRE_DATA: Dict[str, Any] = {
        "main_menu": {
            "name": "Главное меню",
            "children": {
                "g_for": { "name": "🌍 Зарубежная музыка", "action": "navigate", "value": "genres" },
                "g_ru": { "name": "🇷🇺 Русская музыка", "action": "navigate", "value": "ru_music" },
                "moods": { "name": "✨ Под настроение", "action": "navigate", "value": "moods" },
                "search": { "name": "🔎 Поиск", "action": "navigate", "value": "search_menu" },
                "random": { "name": "🎲 Мне повезет", "action": "random_radio" }
            }
        },
        "genres": {
            "name": "🌍 Жанры и Эпохи",
            "children": {
                "pop": {
                    "name": "💃 Поп & Ретро",
                    "children": {
                        "p80": { "name": "80-е (Disco/Pop)", "query": "best 80s pop hits michael jackson madonna" },
                        "p90": { "name": "90-е (Eurodance/Pop)", "query": "90s pop hits spice girls backstreet boys" },
                        "p00": { "name": "2000-е (MTV Hits)", "query": "2000s pop hits britney spears rihanna" },
                        "p_now": { "name": "Свежие хиты 2024", "query": "top pop hits 2024" }
                    }
                },
                "rock": {
                    "name": "🎸 Рок & Метал",
                    "children": {
                        "r_cl": { "name": "Classic Rock (60-70s)", "query": "classic rock 70s led zeppelin pink floyd" },
                        "r_80": { "name": "Hard & Glam (80s)", "query": "80s hard rock guns n roses acdc" },
                        "r_alt": { "name": "Alt & Grunge (90s)", "query": "90s grunge nirvana pearl jam" },
                        "r_ind": { "name": "Indie & Britpop", "query": "indie rock arctic monkeys the strokes" },
                        "r_mtl": { "name": "Heavy Metal", "query": "best heavy metal metallica iron maiden" },
                        "r_pnk": { "name": "Punk Rock", "query": "punk rock green day blink 182" }
                    }
                },
                "hip": {
                    "name": "🎤 Хип-хоп & R'n'B",
                    "children": {
                        "h_old": { "name": "Old School (90s)", "query": "90s hip hop tupac biggie snoop dogg" },
                        "h_em": { "name": "Eminem & 2000s", "query": "2000s hip hop eminem 50 cent" },
                        "h_trp": { "name": "Trap & Modern", "query": "modern trap hip hop drake travis scott" },
                        "h_lo": { "name": "Lofi & Chill", "query": "lofi hip hop radio beats to relax" }
                    }
                },
                "edm": {
                    "name": "🎧 Электроника",
                    "children": {
                        "e_hou": { "name": "House", "query": "ibiza house music summer mix" },
                        "e_tec": { "name": "Techno", "query": "techno bunker mix" },
                        "e_dnb": { "name": "Drum & Bass", "query": "liquid drum and bass mix" },
                        "e_syn": { "name": "Synthwave / Retro", "query": "synthwave retrowave mix" },
                        "e_phk": { "name": "Phonk", "query": "drift phonk mix" }
                    }
                },
                "soul": {
                    "name": "🎷 Джаз, Блюз, Соул",
                    "children": {
                        "s_jaz": { "name": "Jazz Classics", "query": "classic jazz frank sinatra louis armstrong" },
                        "s_blu": { "name": "Blues Rock", "query": "blues rock guitar mix" },
                        "s_sou": { "name": "Soul & R&B", "query": "classic soul music marvin gaye" }
                    }
                }
            }
        },
        "ru_music": {
            "name": "🇷🇺 Русская музыка",
            "children": {
                "ru_sov": {
                    "name": "☭ Советская Эстрада & Ретро",
                    "children": {
                        "sov_hit": { "name": "🎙 Золотые хиты СССР", "query": "лучшие песни ссср 70-80 эстрада магомаев пугачева" },
                        "sov_mov": { "name": "🎬 Песни из Кинофильмов", "query": "песни из советских кинофильмов сборник" },
                        "sov_via": { "name": "🎸 ВИА (Песняры, Земляне)", "query": "лучшие виа ссср песняры самоцветы" },
                        "sov_vys": { "name": "🔥 Высоцкий и Барды", "query": "владимир высоцкий лучшие песни" }
                    }
                },
                "ru_rck": {
                    "name": "🎸 Русский Рок",
                    "children": {
                        "rr_leg": { "name": "Легенды (Кино, Би-2)", "query": "русский рок хиты кино би-2 сплин" },
                        "rr_mod": { "name": "Современный", "query": "современный русский рок" },
                        "rr_pnk": { "name": "Панк (КиШ)", "query": "король и шут сектор газа лучшее" }
                    }
                },
                "ru_pop": {
                    "name": "💃 Русская Попса",
                    "children": {
                        "rp_90": { "name": "Лихие 90-е", "query": "русская дискотека 90 руки вверх" },
                        "rp_00": { "name": "Нулевые", "query": "русские хиты 2000х" },
                        "rp_now": { "name": "Топ чарты сейчас", "query": "русские хиты 2024 новинки" }
                    }
                },
                "ru_rap": {
                    "name": "🎤 Русский Рэп",
                    "children": {
                        "rap_ol": { "name": "Олдскул (Баста, Гуф)", "query": "русский рэп 2000х баста гуф" },
                        "rap_nw": { "name": "Новая Школа", "query": "русский рэп новинки моргенштерн" },
                        "rap_ly": { "name": "Лирика / Кальянный", "query": "кальянный рэп мияги энди панда" }
                    }
                },
                "ru_atm": { "name": "🚬 Шансон / Душевное", "query": "золотой шансон михаил круг" }
            }
        },
        "moods": {
            "name": "✨ Настроение и Дела",
            "children": {
                "m_wrk": { "name": "👨‍💻 Работа / Фокус", "query": "deep focus music for work" },
                "m_gym": { "name": "💪 Спорт / Gym", "query": "workout motivation music aggressive phonk" },
                "m_rel": { "name": "😌 Релакс / Сон", "query": "ambient relaxing music for sleep" },
                "m_prt": { "name": "🎉 Вечеринка", "query": "party mix 2024 club dance" },
                "m_drv": { "name": "🚗 В машину", "query": "night drive music bass boosted" },
                "m_cls": { "name": "🎻 Классика", "query": "best classical music mozart beethoven" }
            }
        },
        "search_menu": {
            "name": "🔎 Поиск",
            "children": {
                "artist": { "name": "👤 По Артисту", "action": "search_artist" },
                "track": { "name": "🎵 По Треку", "action": "search_track" }
            }
        }
    }

    @field_validator("ADMIN_ID_LIST", mode="before")
    @classmethod
    def _assemble_admin_ids(cls, v, info) -> List[int]:
        admin_ids_str = info.data.get("ADMIN_IDS", "")
        if not admin_ids_str: return []
        try:
            return [int(i.strip()) for i in admin_ids_str.split(",") if i.strip()]
        except ValueError as e:
            # Логируем ошибку, но не роняем приложение, возвращаем пустой список
            print(f"⚠️ Ошибка парсинга ADMIN_IDS: {e}")
            return []

@lru_cache()
def get_settings() -> Settings:
    return Settings()
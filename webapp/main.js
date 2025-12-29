import { store } from './store.js';
import { api } from './api.js';
import { Player } from './player.js';
import { Visualizer } from './visualizer.js';
import { UI } from './ui.js';

document.addEventListener('DOMContentLoaded', () => {
    console.log('[Main] Starting Aurora OS...');

    // 1. Инициализация Telegram
    try {
        const tg = window.Telegram?.WebApp;
        if (tg) {
            tg.expand();
            tg.setHeaderColor('#050510');
            tg.setBackgroundColor('#050510');
            console.log('[Main] Telegram WebApp initialized');
        }
    } catch (e) {
        console.warn('[Main] Telegram init failed:', e);
    }

    // 2. Инициализация UI (Критически важно)
    try {
        // Создаем глобальный хендлер ДО инициализации UI
        window.loadGenreHandler = async (query) => {
            console.log('[Main] Loading genre:', query);
            UI.toggleDrawer('genres', false); // Закрыть меню
            
            // Визуальный индикатор
            const title = document.getElementById('track-title');
            if(title) title.textContent = "Loading...";

            try {
                const playlist = await api.fetchPlaylist(query);
                store.playlist = playlist;
                if (playlist.length > 0) {
                    Player.playTrack(0);
                } else {
                    if(title) title.textContent = "No tracks found";
                }
            } catch (err) {
                console.error('API Error:', err);
                if(title) title.textContent = "Error loading";
            }
        };

        UI.initialize(Player);
        console.log('[Main] UI initialized successfully');
    } catch (e) {
        console.error('[Main] UI CRASHED:', e);
    }

    // 3. Запуск Визуализатора (Может упасть, не страшно)
    try {
        const startAudioContext = () => {
            const audio = Player.getAudioElement();
            // Пробуем запустить, но не роняем приложение при ошибке
            try {
                Visualizer.initialize(audio);
            } catch (vErr) {
                console.warn('[Visualizer] Failed to start:', vErr);
            }
            
            // Удаляем слушатели
            document.removeEventListener('click', startAudioContext);
            document.removeEventListener('touchstart', startAudioContext);
        };
        
        document.addEventListener('click', startAudioContext);
        document.addEventListener('touchstart', startAudioContext);
    } catch (e) {
        console.warn('[Main] Visualizer setup failed:', e);
    }

    // 4. Автозагрузка (Опционально)
    /*
    setTimeout(() => {
        window.loadGenreHandler('lofi hip hop');
    }, 1000);
    */
});
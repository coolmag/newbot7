import { store } from './store.js';
import * as api from './api.js'; // <--- ИСПРАВЛЕНО: Теперь импорт работает корректно
import { Player } from './player.js';
import { UI } from './ui.js';

document.addEventListener('DOMContentLoaded', async () => {
    console.log('[Main] System booting...');

    // 1. Инициализация Telegram
    try {
        const tg = window.Telegram?.WebApp;
        if (tg) {
            tg.expand();
            tg.setHeaderColor('#050510');
            tg.setBackgroundColor('#050510');
        }
    } catch (e) {
        console.warn('Telegram init error:', e);
    }

    // 2. Инициализация UI
    try {
        // Хендлер загрузки
        window.loadGenreHandler = async (query) => {
            console.log('[Main] Loading genre:', query);
            UI.toggleDrawer('genres', false);
            
            const titleEl = document.getElementById('track-title');
            const artistEl = document.getElementById('track-artist');
            
            if(titleEl) titleEl.textContent = "Loading...";
            if(artistEl) artistEl.textContent = "Connecting to server...";

            try {
                const playlist = await api.fetchPlaylist(query);
                store.playlist = playlist;
                if (playlist.length > 0) {
                    Player.playTrack(0);
                } else {
                    if(titleEl) titleEl.textContent = "No signals found";
                    if(artistEl) artistEl.textContent = "Try another frequency";
                }
            } catch (err) {
                console.error('[Main] Playlist error:', err);
                if(titleEl) titleEl.textContent = "Connection Error";
                if(artistEl) artistEl.textContent = "Check network";
            }
        };

        UI.initialize(Player);
        console.log('[Main] UI Active');
        
    } catch (e) {
        console.error('[Main] UI CRASH:', e);
    }

    // 3. Запуск 3D (Безопасный режим)
    const start3D = async () => {
        try {
            // Динамический импорт, чтобы не блокировать основной поток
            const { Visualizer } = await import('./visualizer.js');
            const audio = Player.getAudioElement();
            Visualizer.initialize(audio);
            console.log('[Main] Visualizer engaged');
        } catch (e) {
            console.warn('[Main] Visualizer skipped:', e);
        }
    };

    const onUserInteract = () => {
        start3D();
        document.removeEventListener('click', onUserInteract);
        document.removeEventListener('touchstart', onUserInteract);
    };
    document.addEventListener('click', onUserInteract);
    document.addEventListener('touchstart', onUserInteract);

    // 4. Авто-старт
    setTimeout(() => {
        // Пробуем загрузить, если есть подключение
        if (navigator.onLine) {
            window.loadGenreHandler('lofi hip hop radio');
        }
    }, 1000);
});
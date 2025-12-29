import { store } from './store.js';
import { api } from './api.js';
import { Player } from './player.js';
import { UI } from './ui.js';
// Visualizer импортируем позже, внутри кода

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

    // 2. Инициализация UI (Кнопки заработают СРАЗУ)
    try {
        // Создаем глобальный обработчик для жанров
        window.loadGenreHandler = async (query) => {
            console.log('[Main] Loading genre:', query);
            UI.toggleDrawer('genres', false);
            
            // Показываем статус
            const titleEl = document.getElementById('track-title');
            if(titleEl) titleEl.textContent = "Loading...";

            try {
                const playlist = await api.fetchPlaylist(query);
                store.playlist = playlist;
                if (playlist.length > 0) {
                    Player.playTrack(0);
                } else {
                    if(titleEl) titleEl.textContent = "Playlist empty";
                }
            } catch (err) {
                console.error('[Main] Playlist load failed:', err);
                if(titleEl) titleEl.textContent = "Network Error";
            }
        };

        // Запускаем UI
        UI.initialize(Player);
        console.log('[Main] UI Active. Buttons should work now.');
        
    } catch (e) {
        console.error('[Main] CRITICAL UI ERROR:', e);
        alert('UI Error: ' + e.message);
    }

    // 3. Попытка загрузить 3D Визуализатор (Изолировано)
    // Если здесь будет ошибка, она НЕ сломает плеер
    const start3D = async () => {
        try {
            console.log('[Main] Loading 3D Engine...');
            // Динамический импорт: если three.js не загрузится, ошибка упадет сюда
            const { Visualizer } = await import('./visualizer.js');
            
            const audio = Player.getAudioElement();
            Visualizer.initialize(audio);
            console.log('[Main] 3D Engine Started');
        } catch (e) {
            console.warn('[Main] 3D Visualizer disabled (module error):', e);
            // Можно скрыть канвас, если 3D не работает
            const canvas = document.getElementById('visualizer-canvas');
            if (canvas) canvas.style.display = 'none';
        }
    };

    // Запускаем 3D только по клику (требование браузеров)
    const onUserInteract = () => {
        start3D();
        document.removeEventListener('click', onUserInteract);
        document.removeEventListener('touchstart', onUserInteract);
    };
    document.addEventListener('click', onUserInteract);
    document.addEventListener('touchstart', onUserInteract);

    // 4. Авто-старт музыки (Lo-Fi)
    setTimeout(() => {
        window.loadGenreHandler('lofi hip hop radio');
    }, 500);
});
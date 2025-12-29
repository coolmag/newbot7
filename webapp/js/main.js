import { store } from './store.js';
import { fetchPlaylist } from './api.js'; // <--- ИСПРАВЛЕНО
import { Player } from './player.js';
import { Visualizer } from './visualizer.js';
import { UI } from './ui.js';

document.addEventListener('DOMContentLoaded', async () => {
    // Оптимизация для мобильных
    document.body.style.touchAction = 'manipulation';

    // 1. Telegram Init
    try {
        const tg = window.Telegram?.WebApp;
        if (tg) {
            tg.expand();
            tg.setHeaderColor('#050510');
            tg.setBackgroundColor('#050510');
            tg.enableClosingConfirmation();
        }
    } catch (e) {}

    // 2. UI Logic
    window.loadGenreHandler = async (query) => {
        UI.toggleDrawer('genres', false);
        
        // Сброс UI
        const tTitle = document.getElementById('track-title');
        const tArtist = document.getElementById('track-artist');
        if(tTitle) tTitle.textContent = "Loading...";
        if(tArtist) tArtist.textContent = "Searching cosmos...";

        try {
            // Используем исправленный импорт
            const playlist = await fetchPlaylist(query);
            store.playlist = playlist;
            
            if (playlist.length > 0) {
                Player.playTrack(0);
            } else {
                if(tTitle) tTitle.textContent = "Empty Sector";
                if(tArtist) tArtist.textContent = "Try another signal";
            }
        } catch (err) {
            console.error(err);
            if(tTitle) tTitle.textContent = "Signal Lost";
        }
    };

    UI.initialize(Player);

    // 3. Запуск Визуализатора (теперь он легкий и не упадет)
    const initAudio = () => {
        const audio = Player.getAudioElement();
        Visualizer.initialize(audio);
        // Снимаем слушатели после первого клика
        document.removeEventListener('click', initAudio);
        document.removeEventListener('touchstart', initAudio);
    };
    
    document.addEventListener('click', initAudio);
    document.addEventListener('touchstart', initAudio);

    // Авто-старт (если сеть есть)
    setTimeout(() => {
        if(navigator.onLine) window.loadGenreHandler('lofi hip hop radio');
    }, 800);
});
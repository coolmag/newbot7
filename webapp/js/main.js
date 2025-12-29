import { store } from './store.js';
import { fetchPlaylist } from './api.js';
import { Player } from './player.js';
import { Visualizer } from './visualizer.js';
import { UI } from './ui.js';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Инициализация Telegram
    try {
        const tg = window.Telegram?.WebApp;
        if (tg) {
            tg.expand();
            tg.setHeaderColor('#050510');
            tg.setBackgroundColor('#050510');
        }
    } catch (e) {}

    // 2. Логика "Tap to Start" (Решает проблему автоплея)
    const startBtn = document.getElementById('btn-start-system');
    const startOverlay = document.getElementById('start-overlay');

    const initializeSystem = async () => {
        // Убираем оверлей
        startOverlay.style.opacity = '0';
        setTimeout(() => startOverlay.remove(), 500);

        // Разблокируем аудио
        const audio = Player.getAudioElement();
        try {
            // Тихий старт аудио контекста
            await audio.play().then(() => audio.pause()).catch(() => {});
            Visualizer.initialize(audio);
        } catch (e) {
            console.log('Audio init warning:', e);
        }

        // Загружаем первый плейлист
        window.loadGenreHandler('lofi hip hop radio');
    };

    startBtn.onclick = initializeSystem;

    // 3. UI Логика
    window.loadGenreHandler = async (query) => {
        UI.toggleDrawer('genres', false);
        
        const tTitle = document.getElementById('track-title');
        const tArtist = document.getElementById('track-artist');
        
        tTitle.textContent = "Scanning...";
        tArtist.textContent = "Connecting to frequency...";

        try {
            const playlist = await fetchPlaylist(query);
            store.playlist = playlist;
            
            if (playlist.length > 0) {
                Player.playTrack(0);
            } else {
                tTitle.textContent = "No Signal";
                tArtist.textContent = "Try another frequency";
            }
        } catch (err) {
            tTitle.textContent = "Connection Error";
        }
    };

    UI.initialize(Player);
});
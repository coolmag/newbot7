import { store } from './store.js';
import { fetchPlaylist } from './api.js';
import { Player } from './player.js';
import { Visualizer } from './visualizer.js';
import { UI } from './ui.js';

// Хелпер для логов
function log(msg) {
    const el = document.getElementById('system-log');
    if(el) {
        el.textContent = `> ${msg}`;
        // Мигание при обновлении
        el.style.opacity = '1';
        setTimeout(() => el.style.opacity = '0.7', 100);
    }
    console.log(`[SYS] ${msg}`);
}

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

    // 2. Старт Системы
    const startBtn = document.getElementById('btn-start-system');
    const startOverlay = document.getElementById('start-overlay');

    startBtn.onclick = async () => {
        log('INITIALIZING AUDIO CORE...');
        startOverlay.style.opacity = '0';
        setTimeout(() => startOverlay.remove(), 500);

        const audio = Player.getAudioElement();
        try {
            await audio.play().then(() => audio.pause()).catch(() => {});
            Visualizer.initialize(audio);
            log('AUDIO CORE ONLINE');
        } catch (e) {
            log('AUDIO WARNING: ' + e.message);
        }
        
        window.loadGenreHandler('lofi hip hop radio');
    };

    // 3. Логика загрузки
    window.loadGenreHandler = async (query) => {
        UI.toggleDrawer('genres', false);
        log(`SEARCHING: ${query.toUpperCase()}`);
        
        const tTitle = document.getElementById('track-title');
        const tArtist = document.getElementById('track-artist');
        tTitle.textContent = "Scanning...";
        tArtist.textContent = "Please wait";

        try {
            const playlist = await fetchPlaylist(query);
            store.playlist = playlist;
            
            if (playlist.length > 0) {
                log(`FOUND ${playlist.length} TRACKS`);
                Player.playTrack(0);
            } else {
                log('NO SIGNAL FOUND');
                tTitle.textContent = "No Signal";
                tArtist.textContent = "Try another frequency";
            }
        } catch (err) {
            log('CONNECTION ERROR');
            tTitle.textContent = "Error";
        }
    };
    
    // Кнопка Shuffle
    document.getElementById('btn-shuffle').onclick = () => {
        if (store.playlist.length < 2) return;
        log('SHUFFLING PLAYLIST...');
        // Алгоритм Фишера-Йетса
        for (let i = store.playlist.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [store.playlist[i], store.playlist[j]] = [store.playlist[j], store.playlist[i]];
        }
        // Сброс индекса и старт первого трека
        store.currentTrackIndex = -1;
        Player.playTrack(0);
        // Обновить список в UI
        // UI сам обновится через подписку на store, но можно форсировать
        log('PLAYLIST SHUFFLED');
    };

    UI.initialize(Player);
    log('SYSTEM STANDBY');
});
import { store } from './store.js';
import { fetchPlaylist } from './api.js';
import { Player } from './player.js';
import { Visualizer } from './visualizer.js';
import { UI } from './ui.js';

// --- SYSTEM LOGGER ---
const logger = {
    el: null,
    init() {
        this.el = document.getElementById('system-log');
    },
    print(msg, type = 'info') {
        if (!this.el) return;
        this.el.textContent = `> ${msg}`;
        this.el.className = 'system-log'; // Reset class
        if (type === 'error') this.el.classList.add('log-error');
        if (type === 'success') this.el.classList.add('log-success');
        if (type === 'loading') this.el.classList.add('log-loading');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    logger.init();
    
    // 1. Telegram
    try {
        const tg = window.Telegram?.WebApp;
        if (tg) {
            tg.expand();
            tg.setHeaderColor('#050510');
            tg.setBackgroundColor('#050510');
        }
    } catch (e) {}

    // 2. Подключаем "Уши" к плееру (слушаем события)
    Player.setStatusCallback((state, message) => {
        let logType = 'info';
        if (state === 'error') logType = 'error';
        if (state === 'playing') logType = 'success';
        if (state === 'loading') logType = 'loading';
        
        logger.print(message, logType);

        // Обновляем статус текста в плеере, если грузится
        const tArtist = document.getElementById('track-artist');
        if (state === 'loading' && tArtist) {
            tArtist.textContent = "Processing stream...";
            tArtist.style.color = '#ffe600';
        } else if (state === 'playing' && tArtist) {
            // Возвращаем имя артиста (берем из store)
            const track = store.playlist[store.currentTrackIndex];
            if (track) {
                tArtist.textContent = track.artist;
                tArtist.style.color = '#8899a6';
            }
        }
    });

    // 3. Обработчик "INITIALIZE"
    const startBtn = document.getElementById('btn-start-system');
    const startOverlay = document.getElementById('start-overlay');

    startBtn.onclick = async () => {
        logger.print('INITIALIZING CORE SYSTEMS...', 'loading');
        
        // Анимация исчезновения
        startOverlay.style.opacity = '0';
        setTimeout(() => startOverlay.remove(), 500);

        const audio = Player.getAudioElement();
        try {
            await audio.play().then(() => audio.pause()).catch(() => {});
            Visualizer.initialize(audio);
            logger.print('AUDIO CORE ONLINE', 'success');
        } catch (e) {
            logger.print('CORE WARNING: BYPASSING AUDIO CHECK', 'error');
        }
        
        // Грузим первый жанр
        window.loadGenreHandler('lofi hip hop radio');
    };

    // 4. Логика загрузки плейлиста
    window.loadGenreHandler = async (query) => {
        UI.toggleDrawer('genres', false);
        logger.print(`SEARCHING: ${query.toUpperCase()}`, 'loading');
        
        const tTitle = document.getElementById('track-title');
        const tArtist = document.getElementById('track-artist');
        tTitle.textContent = "Scanning Network";
        tArtist.textContent = "Please wait...";

        try {
            const playlist = await fetchPlaylist(query);
            store.playlist = playlist;
            
            if (playlist.length > 0) {
                logger.print(`TARGET ACQUIRED: ${playlist.length} TRACKS`, 'success');
                Player.playTrack(0);
            } else {
                logger.print('SCAN COMPLETE: NO SIGNALS', 'error');
                tTitle.textContent = "No Signal";
                tArtist.textContent = "Select another frequency";
            }
        } catch (err) {
            logger.print('NETWORK ERROR: CONNECTION LOST', 'error');
            tTitle.textContent = "Connection Fail";
        }
    };

    // 5. Shuffle
    document.getElementById('btn-shuffle').onclick = () => {
        if (store.playlist.length < 2) return;
        logger.print('RANDOMIZING SEQUENCE...', 'loading');
        
        for (let i = store.playlist.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [store.playlist[i], store.playlist[j]] = [store.playlist[j], store.playlist[i]];
        }
        
        store.currentTrackIndex = -1;
        Player.playTrack(0);
    };

    UI.initialize(Player);
});
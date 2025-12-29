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
        if (!this.el) this.el = document.getElementById('system-log');
        if (!this.el) return;
        this.el.textContent = `> ${msg}`;
        this.el.className = 'system-log';
        if (type === 'error') this.el.classList.add('log-error');
        if (type === 'success') this.el.classList.add('log-success');
        if (type === 'loading') this.el.classList.add('log-loading');
    }
};

// Глобальный перехват ошибок (чтобы видеть их на телефоне)
window.onerror = function(msg, url, line) {
    const debugEl = document.getElementById('debug-log');
    if (debugEl) {
        debugEl.innerHTML += `<br>ERR: ${msg} @ ${url?.split('/').pop()}:${line}`;
    }
    if (logger && logger.print) logger.print(`КРИТ. ОШИБКА: ${msg}`, 'error');
    return false;
};

document.addEventListener('DOMContentLoaded', () => {
    logger.init();
    
    // 1. Telegram Init
    try {
        const tg = window.Telegram?.WebApp;
        if (tg) {
            tg.expand();
            if (tg.isVersionAtLeast('6.1')) {
                tg.setHeaderColor('#050510');
                tg.setBackgroundColor('#050510');
            }
        }
    } catch (e) {
        console.warn(e);
    }

    // 2. Подключаем логи плеера
    Player.setStatusCallback((state, message) => {
        let logType = 'info';
        if (state === 'error') logType = 'error';
        if (state === 'playing') logType = 'success';
        if (state === 'loading') logType = 'loading';
        
        logger.print(message, logType);

        const tArtist = document.getElementById('track-artist');
        if (tArtist) {
            if (state === 'loading') {
                tArtist.textContent = "Обработка...";
                tArtist.style.color = '#ffe600';
            } else if (state === 'playing') {
                const track = store.playlist[store.currentTrackIndex];
                if (track) {
                    tArtist.textContent = track.artist;
                    tArtist.style.color = '#8899a6';
                }
            }
        }
    });

    // 3. Обработчик "INITIALIZE" (ИСПРАВЛЕННЫЙ)
    const startBtn = document.getElementById('btn-start-system');
    const startOverlay = document.getElementById('start-overlay');

    if (startBtn) {
        startBtn.onclick = async () => {
            logger.print('1/3 ЗАПУСК...', 'loading');
            
            if (startOverlay) {
                startOverlay.style.opacity = '0';
                setTimeout(() => startOverlay.remove(), 500);
            }

            try {
                const audio = Player.getAudioElement();
                
                logger.print('2/3 ИНИЦИАЛИЗАЦИЯ АУДИО...', 'loading');
                await Visualizer.initialize(audio);
                logger.print('3/3 АУДИО-ЯДРО: ОНЛАЙН', 'success');

            } catch (e) {
                logger.print('СБОЙ АУДИО: ' + e.message, 'error');
                // Также выводим в дебаг-лог
                const debugEl = document.getElementById('debug-log');
                if (debugEl) debugEl.innerHTML += `<br>AUDIO FAIL: ${e.message}`;
            }
            
            window.loadGenreHandler('lofi hip hop radio');
        };
    }

    // 4. Логика загрузки
    window.loadGenreHandler = async (query) => {
        UI.toggleDrawer('genres', false);
        logger.print(`ПОИСК: ${query.toUpperCase()}`, 'loading');
        
        const tTitle = document.getElementById('track-title');
        const tArtist = document.getElementById('track-artist');
        if(tTitle) tTitle.textContent = "Сканирование...";
        if(tArtist) tArtist.textContent = "Подождите...";

        try {
            const playlist = await fetchPlaylist(query);
            store.playlist = playlist;
            
            if (playlist && playlist.length > 0) {
                logger.print(`НАЙДЕНО ${playlist.length} ТРЕКОВ`, 'success');
                Player.playTrack(0);
            } else {
                logger.print('СИГНАЛ НЕ НАЙДЕН', 'error');
                if(tTitle) tTitle.textContent = "Пусто";
            }
        } catch (err) {
            logger.print('ОШИБКА СЕТИ', 'error');
            if(tTitle) tTitle.textContent = "Сбой соединения";
        }
    };

    // 5. Shuffle
    const btnShuffle = document.getElementById('btn-shuffle');
    if (btnShuffle) {
        btnShuffle.onclick = () => {
            if (!store.playlist || store.playlist.length < 2) return;
            logger.print('ПЕРЕМЕШИВАНИЕ...', 'loading');
            for (let i = store.playlist.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [store.playlist[i], store.playlist[j]] = [store.playlist[j], store.playlist[i]];
            }
            store.currentTrackIndex = -1;
            Player.playTrack(0);
        };
    }

    UI.initialize(Player);
});
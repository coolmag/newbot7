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

// Глобальный перехват ошибок
window.onerror = function(msg, url, line) {
    const debugEl = document.getElementById('debug-log');
    if (debugEl) {
        debugEl.innerHTML += `<br>ERR: ${msg}`;
    }
    if (logger && logger.print) logger.print(`КРИТ. ОШИБКА: ${msg}`, 'error');
    return false;
};

document.addEventListener('DOMContentLoaded', () => {
    logger.init();
    logger.print('ИМПОРТЫ ЗАГРУЖЕНЫ', 'success');
    // Пока остальной код закомментирован
});
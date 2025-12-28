import { initializeEventListeners } from './events.js';
import { initializeVisualizer } from './visualizer.js';
import * as elements from './elements.js';

document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    
    // Инициализация WebApp
    if (window.Telegram.WebApp) {
        window.Telegram.WebApp.expand();
        window.Telegram.WebApp.ready();
    }

    // Визуализатор стартует после первого клика (политика браузеров)
    const startAll = () => {
        initializeVisualizer(elements.audio);
        document.removeEventListener('click', startAll);
    };
    document.addEventListener('click', startAll);
});
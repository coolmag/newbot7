import { initializeEventListeners } from './events.js';
import { initializeVisualizer } from './visualizer.js';
import * as elements from './elements.js'; // Убедитесь, что elements.js обновлен

document.addEventListener('DOMContentLoaded', () => {
    // Инициализация Telegram WebApp
    if (window.Telegram.WebApp) {
        window.Telegram.WebApp.expand();
        window.Telegram.WebApp.ready();
    }

    // Инициализация слушателей событий (для кнопок и дроеров)
    initializeEventListeners();

    // Визуализатор стартует после первого клика (политика браузеров)
    // Вешаем слушатель на основной контейнер, чтобы поймать первый клик
    const startAll = () => {
        initializeVisualizer(elements.audio); // Передаем audioElement
        document.removeEventListener('click', startAll); // Отписываемся после первого клика
        // Возможно, здесь нужно сразу запустить плейлист по умолчанию
        // player.playTrack(0); // Или что-то подобное, если плеер уже готов
    };
    document.addEventListener('click', startAll);
});
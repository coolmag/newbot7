import { store } from './store.js';
import { api } from './api.js';
import { Player } from './player.js';
import { Visualizer } from './visualizer.js';
import { UI } from './ui.js';

document.addEventListener('DOMContentLoaded', () => {
    // 1. Инициализация Telegram
    const tg = window.Telegram?.WebApp;
    if (tg) {
        tg.expand();
        tg.enableClosingConfirmation();
        // Установим цвет хедера под наш дизайн
        tg.setHeaderColor('#050510');
        tg.setBackgroundColor('#050510');
    }

    // 2. Инициализация UI
    UI.initialize(Player);

    // 3. Хендлер загрузки жанра (глобальный, чтобы UI мог вызывать)
    window.loadGenreHandler = async (query) => {
        store.playlist = []; // Очистка
        // Показать индикатор загрузки можно тут
        const playlist = await api.fetchPlaylist(query);
        store.playlist = playlist;
        if (playlist.length > 0) Player.playTrack(0);
    };

    // 4. Запуск визуализатора при первом клике (политика браузеров)
    const startAudioContext = () => {
        const audio = Player.getAudioElement();
        Visualizer.initialize(audio);
        document.removeEventListener('click', startAudioContext);
        document.removeEventListener('touchstart', startAudioContext);
    };
    document.addEventListener('click', startAudioContext);
    document.addEventListener('touchstart', startAudioContext);

    // 5. Загрузка стартового плейлиста
    (async () => {
        // Загружаем что-то нейтральное или популярное
        await window.loadGenreHandler('lofi hip hop radio');
    })();

    console.log('[Aurora] Ready for Space 2025');
});
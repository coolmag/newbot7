import store from './store.js';
import * as elements from './elements.js';
import * as api from './api.js';
import * as player from './player.js';
import { render } from './renderer.js'; // Импортируем render из renderer.js

export function initializeEventListeners() {
    elements.playBtn.onclick = () => player.togglePlay();
    elements.nextBtn.onclick = () => player.playTrack(store.currentTrackIndex + 1);
    elements.prevBtn.onclick = () => player.playTrack(store.currentTrackIndex - 1);
    
    // Top bar buttons
    elements.btnGenres.onclick = () => {
        elements.drawerGenres.classList.add('active');
        elements.overlay.classList.add('active');
        // Render genres grid if not already done
        renderGenres();
    };

    elements.btnPlaylist.onclick = () => {
        elements.drawerPlaylist.classList.add('active');
        elements.overlay.classList.add('active');
        renderPlaylist(); // Рендерим плейлист при открытии
    };

    elements.overlay.onclick = () => {
        elements.drawerGenres.classList.remove('active');
        elements.drawerPlaylist.classList.remove('active');
        elements.overlay.classList.remove('active');
    };

    // Genre grid interaction
    const genres = ["Lofi", "Rock", "Pop", "Techno"]; // Упрощенно
    function renderGenres() {
        elements.genreGrid.innerHTML = ''; // Очищаем перед рендерингом
        genres.forEach(g => {
            const b = document.createElement('button');
            b.className = 'genre-card';
            b.textContent = g;
            b.onclick = async () => {
                store.playlist = await api.fetchPlaylist(g);
                player.playTrack(0);
                elements.overlay.click(); // Закрываем дроера
            };
            elements.genreGrid.appendChild(b);
        });
    }

    function renderPlaylist() {
        elements.playlistContent.innerHTML = ''; // Очищаем перед рендерингом
        if (store.playlist.length === 0) {
            elements.playlistContent.innerHTML = '<p>Плейлист пуст.</p>';
            return;
        }
        store.playlist.forEach((track, index) => {
            const item = document.createElement('div');
            item.className = 'playlist-item';
            item.textContent = `${track.title} - ${track.artist}`;
            item.onclick = () => {
                player.playTrack(index);
                elements.overlay.click(); // Закрываем дроера
            };
            elements.playlistContent.appendChild(item);
        });
    }

    // Progress bar seeking
    elements.progressClickable.onclick = (e) => {
        const audio = elements.audio;
        if (!audio.duration) return;
        const rect = elements.progressClickable.getBoundingClientRect();
        const percent = (e.clientX - rect.left) / rect.width;
        audio.currentTime = percent * audio.duration;
        render(); // Обновляем UI после перемотки
    };

    // Инициализация при запуске
    render(); // Первоначальный рендер UI
}

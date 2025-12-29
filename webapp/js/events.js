import store from './store.js';
import * as elements from './elements.js';
import * as api from './api.js';
import * as player from './player.js';

export function initializeEventListeners() {
    // Вспомогательная функция для безопасного биндинга
    const safeBind = (id, event, fn) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener(event, fn);
        else console.warn(`[DOM] Element #${id} not found.`);
    };

    safeBind('btn-genres', 'click', () => {
        document.getElementById('drawer-genres')?.classList.add('active');
        document.getElementById('overlay')?.classList.add('active');
    });

    safeBind('btn-playlist', 'click', () => {
        document.getElementById('drawer-playlist')?.classList.add('active');
        document.getElementById('overlay')?.classList.add('active');
    });

    safeBind('overlay', 'click', () => {
        document.querySelectorAll('.drawer').forEach(d => d.classList.remove('active'));
        document.getElementById('overlay')?.classList.remove('active');
    });

    // Управление плеером
    if (elements.btnPlayPause) {
        elements.btnPlayPause.onclick = () => player.togglePlay();
    }

    safeBind('btn-next', 'click', () => player.playTrack(store.currentTrackIndex + 1));
    safeBind('btn-prev', 'click', () => player.playTrack(store.currentTrackIndex - 1));

    // Генерация сетки жанров (Senior Approach: Data-Driven UI)
    const GENRE_DATA = [
        { name: "🎸 Русский Рок", query: "russian rock classics" },
        { name: "🎹 Techno Bunker", query: "dark techno bunker mix" },
        { name: "🍹 Deep House", query: "deep house ibiza 2024" },
        { name: "🎷 Smooth Jazz", query: "smooth jazz chillout" },
        { name: "🇷🇺 Русская Попса", query: "russian pop 2000 hits" },
        { name: "🌌 Lofi Focus", query: "lofi hip hop radio" }
    ];

    const grid = document.getElementById('genre-grid');
    if (grid) {
        grid.innerHTML = '';
        GENRE_DATA.forEach(g => {
            const card = document.createElement('div');
            card.className = 'genre-item';
            card.innerHTML = `<span>${g.name}</span>`;
            card.onclick = async () => {
                const playlist = await api.fetchPlaylist(g.query);
                store.playlist = playlist;
                player.playTrack(0);
                document.getElementById('overlay')?.click();
            };
            grid.appendChild(card);
        });
    }
}
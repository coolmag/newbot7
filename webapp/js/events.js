import store from './store.js';
import * as elements from './elements.js';
import * as api from './api.js';
import * as player from './player.js';

export function initializeEventListeners() {
    const bind = (id, fn) => {
        const el = document.getElementById(id);
        if (el) el.onclick = fn;
    };

    bind('btn-genres', () => {
        document.getElementById('drawer-genres').classList.add('active');
        document.getElementById('overlay').classList.add('active');
    });

    bind('btn-playlist', () => {
        document.getElementById('drawer-playlist').classList.add('active');
        document.getElementById('overlay').classList.add('active');
    });

    bind('overlay', () => {
        document.querySelectorAll('.drawer').forEach(d => d.classList.remove('active'));
        document.getElementById('overlay').classList.remove('active');
    });

    // Управление
    if (elements.playBtn) elements.playBtn.onclick = () => player.togglePlay();
    bind('btn-next', () => player.playTrack(store.currentTrackIndex + 1));
    bind('btn-prev', () => player.playTrack(store.currentTrackIndex - 1));

    // Наполнение жанров из твоего бота
    const genres = [
        { n: "🎸 Русский Рок", q: "русский рок хиты кино би-2" },
        { n: "💃 Русская Попса", q: "русские хиты 2000" },
        { n: "🎧 House", q: "house music club mix" },
        { n: "🎷 Jazz", q: "classic jazz greatest hits" },
        { n: "🔥 Топ-50", q: "top 50 global hits" },
        { n: "😌 Релакс", q: "lofi hip hop radio study" }
    ];

    const grid = document.getElementById('genre-grid');
    if (grid) {
        grid.innerHTML = '';
        genres.forEach(g => {
            const div = document.createElement('div');
            div.className = 'genre-item';
            div.textContent = g.n;
            div.onclick = async () => {
                store.playlist = await api.fetchPlaylist(g.q);
                player.playTrack(0);
                document.getElementById('overlay').click();
            };
            grid.appendChild(div);
        });
    }
}
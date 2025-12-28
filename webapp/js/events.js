import store from './store.js';
import * as elements from './elements.js';
import * as api from './api.js';
import * as player from './player.js';

export function initializeEventListeners() {
    elements.playBtn.onclick = () => player.togglePlay();
    document.getElementById('btn-next').onclick = () => player.playTrack(store.currentTrackIndex + 1);
    document.getElementById('btn-prev').onclick = () => player.playTrack(store.currentTrackIndex - 1);
    
    document.getElementById('btn-genres').onclick = () => {
        document.getElementById('screen-genres').classList.add('active');
        document.getElementById('overlay').classList.add('active');
    };

    document.getElementById('overlay').onclick = () => {
        document.querySelectorAll('.drawer').forEach(d => d.classList.remove('active'));
        document.getElementById('overlay').classList.remove('active');
    };

    // Наполнение жанров (упрощенно)
    const genres = ["Lofi", "Rock", "Pop", "Techno"];
    const grid = document.getElementById('genre-grid');
    genres.forEach(g => {
        const b = document.createElement('button');
        b.className = 'genre-card';
        b.textContent = g;
        b.onclick = async () => {
            store.playlist = await api.fetchPlaylist(g);
            player.playTrack(0);
            document.getElementById('overlay').click();
        };
        grid.appendChild(b);
    });
}
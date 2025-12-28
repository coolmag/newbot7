import store from './store.js';
import * as elements from './elements.js';
import * as api from './api.js';
import * as player from './player.js';
import { initializeVisualizer } from './visualizer.js';

// --- UI Manager (реактивные обновления) ---
class UIManager {
    constructor() {
        window.uiManager = this; // Доступ из store
    }
    render(property, value) {
        if (property === 'isPlaying') {
            this.updatePlayButton(value);
        }
        if (property === 'playlist' || property === 'currentTrackIndex') {
            this.updatePlaylist(store.playlist, store.currentTrackIndex);
            if (store.currentTrackIndex !== -1) {
                this.updateTrackInfo(store.playlist[store.currentTrackIndex]);
            }
        }
    }

    updatePlayButton(isPlaying) {
        const icon = document.getElementById('icon-play');
        if (icon) icon.textContent = isPlaying ? 'pause_arrow' : 'play_arrow';
    }

    updateTrackInfo(track) {
        if (!track) return;
        elements.trackTitle.textContent = track.title;
        elements.trackArtist.textContent = track.artist;
    }

    updatePlaylist(playlist, currentIndex) {
        elements.playlistContainer.innerHTML = '';
        playlist.forEach((track, index) => {
            const item = document.createElement('div');
            item.className = 'playlist-item' + (index === currentIndex ? ' active' : '');
            item.textContent = `${track.artist} - ${track.title}`;
            item.onclick = () => player.playTrack(index);
            elements.playlistContainer.appendChild(item);
        });
    }
}

// --- Инициализация ---
document.addEventListener('DOMContentLoaded', () => {
    new UIManager();

    // Загрузка жанров по умолчанию
    (async () => {
        const initialPlaylist = await api.fetchPlaylist("lofi hip hop");
        store.playlist = initialPlaylist;
    })();

    // Основные слушатели событий
    elements.playBtn.onclick = () => player.togglePlay();
    elements.nextBtn.onclick = () => player.playTrack(store.currentTrackIndex + 1);
    elements.prevBtn.onclick = () => player.playTrack(store.currentTrackIndex - 1);
    
    // Инициализация 3D сцены по первому клику
    document.body.addEventListener('click', () => {
        initializeVisualizer(elements.audio);
    }, { once: true });

    // Обновление прогресс-бара
    elements.audio.addEventListener('timeupdate', () => {
        const { currentTime, duration } = elements.audio;
        if (duration) {
            const progressPercent = (currentTime / duration) * 100;
            elements.progressFill.style.width = `${progressPercent}%`;
            elements.timeCurrent.textContent = formatTime(currentTime);
            if (elements.timeTotal.textContent === '0:00') {
                 elements.timeTotal.textContent = formatTime(duration);
            }
        }
    });
    
    elements.progressContainer.onclick = (e) => {
        const { duration } = elements.audio;
        if (!duration) return;
        const rect = elements.progressContainer.getBoundingClientRect();
        const percent = (e.clientX - rect.left) / rect.width;
        elements.audio.currentTime = percent * duration;
    };
});

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
}
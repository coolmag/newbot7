import store from './store.js';
import * as elements from './elements.js';

export function render() {
    const track = store.playlist[store.currentTrackIndex];
    if (track) {
        elements.titleEl.textContent = track.title;
        elements.artistEl.textContent = track.artist;
    }
    document.getElementById('icon-play').textContent = store.isPlaying ? 'pause' : 'play_arrow';
}

// Обновление прогресс-бара
setInterval(() => {
    const a = document.getElementById('audio-player');
    if (a.duration) {
        const p = (a.currentTime / a.duration) * 100;
        document.getElementById('progress-bar').style.width = p + '%';
        document.getElementById('curr-time').textContent = Math.floor(a.currentTime/60) + ":" + Math.floor(a.currentTime%60).toString().padStart(2,'0');
    }
}, 500);
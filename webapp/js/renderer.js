import store from './store.js';
import * as elements from './elements.js';

export function render() {
    const track = store.playlist[store.currentTrackIndex];
    if (track) {
        elements.trackTitle.textContent = track.title;
        elements.trackArtist.textContent = track.artist;
    } else {
        elements.trackTitle.textContent = "Музыка не выбрана";
        elements.trackArtist.textContent = "Нажмите кнопку «Жанры»";
    }
    document.getElementById('icon-play').textContent = store.isPlaying ? 'pause' : 'play_arrow';
}

// Обновление прогресс-бара
setInterval(() => {
    const a = elements.audio; // Используем элемент из elements.js
    if (a.duration && elements.progressBar) {
        const p = (a.currentTime / a.duration) * 100;
        elements.progressBar.style.width = p + '%';
        elements.currTime.textContent = Math.floor(a.currentTime/60) + ":" + Math.floor(a.currentTime%60).toString().padStart(2,'0');
        elements.durTime.textContent = Math.floor(a.duration/60) + ":" + Math.floor(a.duration%60).toString().padStart(2,'0');
    }
}, 500);
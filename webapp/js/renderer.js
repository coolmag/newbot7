import store from './store.js';
import * as elements from './elements.js';

export function render() {
    const track = store.playlist[store.currentTrackIndex];
    if (track) {
        elements.trackTitle.textContent = track.title;
        elements.trackArtist.textContent = track.artist;
    } else {
        elements.trackTitle.textContent = "Система готова";
        elements.trackArtist.textContent = "Выберите волну";
    }
    // Обновляем иконку Play/Pause
    if (elements.iconPlay) {
        elements.iconPlay.textContent = store.isPlaying ? 'pause' : 'play_arrow';
    }
}

// Обновление прогресс-бара
setInterval(() => {
    const audio = elements.audio; // Используем элемент из elements.js
    if (audio.duration && elements.progressBar) {
        const p = (audio.currentTime / audio.duration) * 100;
        elements.progressBar.style.width = p + '%';
        elements.currTime.textContent = Math.floor(audio.currentTime/60) + ":" + Math.floor(audio.currentTime%60).toString().padStart(2,'0');
        elements.durTime.textContent = Math.floor(audio.duration/60) + ":" + Math.floor(audio.duration%60).toString().padStart(2,'0');
    }
}, 500);
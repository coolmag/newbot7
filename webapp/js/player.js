import store from './store.js';
import * as elements from './elements.js';
import { render } from './renderer.js';

export function playTrack(index) {
    if (index < 0 || index >= store.playlist.length) return;
    
    store.currentTrackIndex = index;
    const track = store.playlist[index];
    
    // ВАЖНО: Путь должен соответствовать main.py
    elements.audio.src = `/audio/${track.identifier}.mp3`;
    elements.audio.load();
    
    elements.audio.play().then(() => {
        store.isPlaying = true;
        updateUI(track);
    }).catch(() => console.log("Interaction required"));
}

export function togglePlay() {
    if (elements.audio.paused) {
        elements.audio.play();
        store.isPlaying = true;
    } else {
        elements.audio.pause();
        store.isPlaying = false;
    }
    render();
}

function updateUI(track) {
    document.getElementById('track-title').textContent = track.title || "Unknown";
    document.getElementById('track-artist').textContent = track.artist || "Unknown";
    document.getElementById('icon-play').textContent = 'pause';
}
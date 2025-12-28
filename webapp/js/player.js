import store from './store.js';
import * as elements from './elements.js';
import { render } from './renderer.js';

export function playTrack(index) {
    if (index < 0 || index >= store.playlist.length) return;
    
    store.currentTrackIndex = index;
    const track = store.playlist[index];
    
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
    // Используем iconPlay из elements.js
    if (elements.iconPlay) {
        elements.iconPlay.textContent = store.isPlaying ? 'pause' : 'play_arrow';
    }
    render();
}

function updateUI(track) {
    elements.trackTitle.textContent = track.title || "Unknown";
    elements.trackArtist.textContent = track.artist || "Unknown";
    if (elements.iconPlay) {
        elements.iconPlay.textContent = 'pause';
    }
}
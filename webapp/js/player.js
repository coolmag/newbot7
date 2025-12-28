// js/player.js

import store from './store.js';
import * as elements from './elements.js';
import { visualizer } from './visualizer.js';

let audioLoadTimeout = null;

function cleanupAudioListeners() {
    const audio = elements.audio;
    if (!audio) return;
    // Create a new element to effectively remove all listeners
    const newAudio = audio.cloneNode(true);
    audio.parentNode.replaceChild(newAudio, audio);
    elements.audio = newAudio; // Update the reference in the elements module
    store.audio = newAudio; // Update the reference in the store
    return newAudio;
}

// --- Audio Event Handlers ---

function handleCanPlay() {
    console.log('[Player] Event: canplay');
    clearTimeout(audioLoadTimeout);
    store.isAudioLoading = false;
    safePlay(); // Attempt to play now that it's ready
}

function handleError(e) {
    console.error("[Player] Event: error", e);
    clearTimeout(audioLoadTimeout);
    store.isAudioLoading = false;
    visualizer.setPlaying(false); // Stop visuals on error
    setTimeout(playNext, 1500); // Try the next track after a short delay
}

function handleLoadedMetadata() {
    console.log('[Player] Event: loadedmetadata');
    clearTimeout(audioLoadTimeout);
}

function handleEnded() {
    console.log('[Player] Event: ended');
    store.isAudioLoading = false; // <-- FIX #3
    playNext();
}

function handlePlay() {
    store.isPlaying = true;
    visualizer.setPlaying(true);
}

function handlePause() {
    store.isPlaying = false;
    visualizer.setPlaying(false);
}

// --- Player Control Functions ---

export function playTrack(index) {
    if (store.isAudioLoading || index < 0 || index >= store.playlist.length) {
        if (index >= store.playlist.length) {
            console.log('[Player] Playlist finished.');
            store.isPlaying = false;
            store.currentTrackIndex = -1;
            visualizer.setPlaying(false);
        }
        return;
    }
    
    store.isAudioLoading = true;
    store.currentTrackIndex = index;

    try {
        const track = store.playlist[index];
        const audio = cleanupAudioListeners(); // Use a fresh element to avoid listener stacking

        visualizer.setPlaying(false);

        const audioUrl = track.url || `/audio/${track.identifier}`; 
        console.log('[Player] Setting audio src:', audioUrl);
        audio.src = audioUrl;
        
        clearTimeout(audioLoadTimeout);
        audioLoadTimeout = setTimeout(() => {
            if (store.isAudioLoading) {
                console.warn("[Player] Track load timeout, skipping...");
                handleError(new Error("Load Timeout"));
            }
        }, 10000); 

        audio.addEventListener('canplay', handleCanPlay, { once: true });
        audio.addEventListener('error', handleError, { once: true });
        audio.addEventListener('loadedmetadata', handleLoadedMetadata, { once: true });
        audio.addEventListener('ended', handleEnded, { once: true });
        audio.addEventListener('play', handlePlay);
        audio.addEventListener('pause', handlePause);

        audio.load();
        updateMediaSessionMetadata();

    } catch (error) {
        console.error("[Player] Critical error in playTrack:", error);
        handleError(error); // Funnel errors to the handler that resets state
    }
}

export function playNext() {
    playTrack(store.currentTrackIndex + 1);
}

export function playPrev() {
    if (elements.audio.currentTime > 3) {
        elements.audio.currentTime = 0;
    } else {
        playTrack(store.currentTrackIndex - 1);
    }
}

export async function safePlay() {
    const audio = elements.audio;
    if (!audio.src) return;
    try {
        await audio.play();
    } catch (err) {
        console.error("Playback error:", err.name, err.message);
        store.isPlaying = false;
        if (err.name === 'NotAllowedError') {
            console.log("Playback was prevented by browser autoplay policy.");
        }
    }
}

export function togglePlayPause() {
    if (store.isPlaying) {
        elements.audio.pause();
    } else {
        safePlay();
    }
}

export function seek(offset) {
    const audio = elements.audio;
    if (!isFinite(audio.duration)) return;
    audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + offset));
}

function updateMediaSessionMetadata() {
    if ('mediaSession' in navigator && store.currentTrackIndex >= 0) {
        const track = store.playlist[store.currentTrackIndex];
        navigator.mediaSession.metadata = new MediaMetadata({
            title: track.title || 'Unknown',
            artist: track.artist || 'Unknown',
            album: store.currentGenre || 'Music',
        });
        
        navigator.mediaSession.setActionHandler('play', togglePlayPause);
        navigator.mediaSession.setActionHandler('pause', togglePlayPause);
        navigator.mediaSession.setActionHandler('previoustrack', playPrev);
        navigator.mediaSession.setActionHandler('nexttrack', playNext);
    }
}

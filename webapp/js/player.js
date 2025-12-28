import store from './store.js';
import * as elements from './elements.js';

let playPromise = null;

export async function playTrack(index) {
    if (index < 0 || !store.playlist[index]) return;

    // 1. Остановка текущего потока
    if (playPromise) {
        try { await playPromise; } catch(e) {}
    }
    elements.audio.pause();

    // 2. Смена состояния
    store.currentTrackIndex = index;
    const track = store.playlist[index];
    
    // 3. Загрузка из вашего FastAPI /audio/
    elements.audio.src = `/audio/${track.identifier}.mp3`;
    elements.audio.load();

    // 4. Визуальное обновление (UI Manager подхватит через Proxy)
    store.isPlaying = true;
    
    try {
        playPromise = elements.audio.play();
        await playPromise;
    } catch (e) {
        if (e.name !== 'AbortError') store.isPlaying = false;
    } finally {
        playPromise = null;
    }
}

export function togglePlay() {
    if (elements.audio.paused) {
        elements.audio.play();
        store.isPlaying = true;
    } else {
        elements.audio.pause();
        store.isPlaying = false;
    }
}
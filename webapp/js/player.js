import { store } from './store.js';

const audio = document.getElementById('audio-player');
let playPromise = null;

/**
 * Безопасно запускает воспроизведение нового трека.
 * @param {number} index - Индекс трека в плейлисте.
 */
async function playTrack(index) {
    if (index < 0 || !store.playlist[index]) {
        console.warn(`[Player] Неверный индекс трека: ${index}`);
        return;
    }

    // Прерываем предыдущее обещание play, если оно есть
    if (playPromise) {
        try {
            await playPromise;
        } catch(e) {
            // Игнорируем AbortError, это ожидаемо
        }
    }
    audio.pause();

    store.currentTrackIndex = index;
    const track = store.playlist[index];
    
    audio.src = `/audio/${track.identifier}.mp3`;
    audio.load();

    try {
        playPromise = audio.play();
        if (playPromise !== undefined) {
            await playPromise;
            store.isPlaying = true;
        }
    } catch (e) {
        if (e.name !== 'AbortError') {
            console.error('[Player] Ошибка воспроизведения:', e);
            store.isPlaying = false;
        }
    } finally {
        playPromise = null;
    }
}

/**
 * Переключает состояние play/pause.
 */
function togglePlay() {
    if (audio.paused) {
        // Если трек не выбран, запускаем первый
        if (store.currentTrackIndex === -1 && store.playlist.length > 0) {
            playTrack(0);
        } else {
            playTrack(store.currentTrackIndex);
        }
    } else {
        audio.pause();
        store.isPlaying = false;
    }
}

/**
 * Переход к следующему треку.
 */
function nextTrack() {
    let nextIndex = store.currentTrackIndex + 1;
    if (nextIndex >= store.playlist.length) {
        nextIndex = 0; // Зацикливаем плейлист
    }
    playTrack(nextIndex);
}

/**
 * Переход к предыдущему треку.
 */
function prevTrack() {
    let prevIndex = store.currentTrackIndex - 1;
    if (prevIndex < 0) {
        prevIndex = store.playlist.length - 1; // Зацикливаем плейлист
    }
    playTrack(prevIndex);
}

/**
 * Перемотка трека.
 * @param {number} percentage - Процент перемотки (0 to 1).
 */
function seek(percentage) {
    if (audio.duration) {
        audio.currentTime = audio.duration * percentage;
    }
}

export const Player = {
    playTrack,
    togglePlay,
    nextTrack,
    prevTrack,
    seek,
    getAudioElement: () => audio,
};

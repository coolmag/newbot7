import { store } from './store.js';

const audio = document.getElementById('audio-player');
let onStatusChange = null; // Функция для отправки логов в UI

// Настройка слушателей событий аудио
function setupAudioListeners() {
    // 1. Начало загрузки
    audio.addEventListener('loadstart', () => {
        reportStatus('loading', 'ESTABLISHING CONNECTION...');
    });

    // 2. Ожидание данных (буферизация)
    audio.addEventListener('waiting', () => {
        reportStatus('loading', 'BUFFERING DATA STREAM...');
    });

    // 3. Готов к воспроизведению
    audio.addEventListener('canplay', () => {
        reportStatus('ready', 'STREAM READY');
        // Если стоял флаг isPlaying, запускаем
        if (store.isPlaying) audio.play().catch(e => console.warn(e));
    });

    // 4. Воспроизведение началось
    audio.addEventListener('play', () => {
        store.isPlaying = true;
        reportStatus('playing', 'PLAYBACK INITIATED');
        // Сообщаем в UI, чтобы включил визуализатор
        document.documentElement.style.setProperty('--reactor-color', '#00f2ff'); // Blue
    });

    // 5. Пауза
    audio.addEventListener('pause', () => {
        store.isPlaying = false;
        reportStatus('paused', 'SYSTEM PAUSED');
        document.documentElement.style.setProperty('--reactor-color', '#ff0055'); // Red/Dim
    });

    // 6. Ошибка
    audio.addEventListener('error', (e) => {
        console.error("Audio Error:", e);
        reportStatus('error', 'STREAM CORRUPTED. REROUTING...');
        document.documentElement.style.setProperty('--reactor-color', '#ff0000');
        
        // Авто-скип через 2 секунды
        setTimeout(() => nextTrack(), 2000);
    });

    // 7. Трек закончился
    audio.addEventListener('ended', () => {
        nextTrack();
    });
}

// Функция отправки статуса
function reportStatus(state, message) {
    if (onStatusChange) onStatusChange(state, message);
}

// Установка коллбека для логов
function setStatusCallback(fn) {
    onStatusChange = fn;
}

async function playTrack(index) {
    if (index < 0 || index >= store.playlist.length) return;
    
    // Обновляем индекс
    store.currentTrackIndex = index;
    const track = store.playlist[index];

    // Сброс
    audio.pause();
    store.isPlaying = true; // Сразу ставим флаг, что хотим играть
    
    // Сообщаем UI, что начали процесс
    reportStatus('loading', `LOADING: ${track.title.toUpperCase().substring(0, 20)}...`);
    document.documentElement.style.setProperty('--reactor-color', '#ffe600'); // Yellow (Loading)

    // Загрузка
    audio.src = `/audio/${track.identifier}.mp3`;
    audio.load(); // Принудительный старт загрузки
    
    // Попытка воспроизведения
    try {
        await audio.play();
    } catch (e) {
        // Ошибка AbortError нормальна при быстром переключении
        if (e.name !== 'AbortError') {
            console.warn("Play request interrupted or waiting for user interaction");
        }
    }
}

function togglePlay() {
    if (audio.paused) {
        if (store.currentTrackIndex === -1 && store.playlist.length > 0) {
            playTrack(0);
        } else {
            audio.play().catch(() => playTrack(store.currentTrackIndex));
        }
    } else {
        audio.pause();
    }
}

function nextTrack() {
    let next = store.currentTrackIndex + 1;
    if (next >= store.playlist.length) next = 0;
    playTrack(next);
}

function prevTrack() {
    let prev = store.currentTrackIndex - 1;
    if (prev < 0) prev = store.playlist.length - 1;
    playTrack(prev);
}

function seek(pct) {
    if (audio.duration) {
        audio.currentTime = audio.duration * pct;
        reportStatus('seeking', `SEEKING TO ${Math.floor(pct*100)}%`);
    }
}

// Инициализируем слушатели при загрузке модуля
setupAudioListeners();

export const Player = {
    playTrack,
    togglePlay,
    nextTrack,
    prevTrack,
    seek,
    getAudioElement: () => audio,
    setStatusCallback
};
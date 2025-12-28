import { store, subscribe } from './store.js';

// --- DOM Elements Cache ---
const elements = {
    trackTitle: document.getElementById('track-title'),
    trackArtist: document.getElementById('track-artist'),
    playPauseBtn: document.getElementById('btn-play-pause'),
    playPauseIcon: document.querySelector('#btn-play-pause .material-icons-round'),
    timeCurrent: document.getElementById('time-current'),
    timeDuration: document.getElementById('time-duration'),
    progressBarFill: document.getElementById('progress-bar-fill'),
    currentGenre: document.getElementById('current-genre'),
    genreList: document.getElementById('genre-list'),
    genresDrawer: document.getElementById('genres-drawer'),
    overlay: document.getElementById('overlay'),
};

// --- Utility Functions ---
function formatTime(seconds) {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60).toString().padStart(2, '0');
    return `${mins}:${secs}`;
}

// --- UI Update Functions ---
function updateTrackInfo(index) {
    if (index === -1 || !store.playlist[index]) {
        elements.trackTitle.textContent = 'Трек не выбран';
        elements.trackArtist.textContent = 'Откройте меню жанров';
    } else {
        const track = store.playlist[index];
        elements.trackTitle.textContent = track.title;
        elements.trackArtist.textContent = track.artist;
    }
}

function updatePlayButton(isPlaying) {
    elements.playPauseIcon.textContent = isPlaying ? 'pause' : 'play_arrow';
}

function updateProgress(audioElement) {
    const { currentTime, duration } = audioElement;
    if (duration) {
        const progressPercent = (currentTime / duration) * 100;
        elements.progressBarFill.style.width = `${progressPercent}%`;
        elements.timeCurrent.textContent = formatTime(currentTime);
        elements.timeDuration.textContent = formatTime(duration);
    }
}

function updateGenreDisplay(genre) {
    elements.currentGenre.textContent = genre;
}

function populateGenres(genres, onSelect) {
    elements.genreList.innerHTML = '';
    for (const genre in genres) {
        const card = document.createElement('div');
        card.className = 'genre-card';
        card.textContent = genre;
        card.onclick = () => onSelect(genres[genre]);
        elements.genreList.appendChild(card);
    }
}

function toggleGenresDrawer(force) {
    elements.genresDrawer.classList.toggle('active', force);
    elements.overlay.classList.toggle('active', force);
}

/**
 * Initializes all UI subscriptions and event listeners.
 */
function initializeUI(player) {
    // --- Subscriptions to Store ---
    subscribe('isPlaying', updatePlayButton);
    subscribe('currentTrackIndex', updateTrackInfo);
    subscribe('currentGenre', updateGenreDisplay);
    subscribe('playlist', (playlist) => {
        // Automatically select first track if none is selected
        if (store.currentTrackIndex === -1 && playlist.length > 0) {
            updateTrackInfo(0);
        }
    });

    // --- Audio Player Events ---
    const audio = player.getAudioElement();
    audio.addEventListener('timeupdate', () => updateProgress(audio));
    audio.addEventListener('loadedmetadata', () => updateProgress(audio));
    audio.addEventListener('ended', () => player.nextTrack());

    // --- DOM Event Listeners ---
    elements.playPauseBtn.onclick = () => player.togglePlay();
    document.getElementById('btn-next').onclick = () => player.nextTrack();
    document.getElementById('btn-prev').onclick = () => player.prevTrack();

    document.getElementById('progress-bar-clickable').onclick = (e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const percent = (e.clientX - rect.left) / rect.width;
        player.seek(percent);
    };

    // Genres Drawer
    document.getElementById('btn-genres').onclick = () => toggleGenresDrawer(true);
    elements.overlay.onclick = () => toggleGenresDrawer(false);
}


export const UI = {
    initialize: initializeUI,
    populateGenres,
    toggleGenresDrawer,
};

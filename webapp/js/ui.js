import { store, subscribe } from './store.js';
import { GENRES, MOODS } from './genres.js';

const elements = {
    title: document.getElementById('track-title'),
    artist: document.getElementById('track-artist'),
    progressFill: document.getElementById('progress-fill'),
    timeCurrent: document.getElementById('time-current'),
    timeDuration: document.getElementById('time-duration'),
    playIcon: document.querySelector('#btn-play-pause .material-icons-round'),
    overlay: document.getElementById('overlay'),
    drawerGenres: document.getElementById('drawer-genres'),
    drawerPlaylist: document.getElementById('drawer-playlist'),
    genreGrid: document.getElementById('genre-grid'),
    playlistContainer: document.getElementById('playlist-container'),
};

// Форматирование времени
const fmt = (s) => {
    if (isNaN(s)) return '0:00';
    return Math.floor(s/60) + ':' + Math.floor(s%60).toString().padStart(2,'0');
};

function renderGenreMenu(onSelect) {
    elements.genreGrid.innerHTML = '';
    
    // 1. Moods (Сверху, как чипсы)
    const moodSection = document.createElement('div');
    moodSection.style.gridColumn = '1 / -1';
    moodSection.style.display = 'flex';
    moodSection.style.gap = '10px';
    moodSection.style.overflowX = 'auto';
    moodSection.style.paddingBottom = '10px';
    
    MOODS.forEach(mood => {
        const chip = document.createElement('div');
        chip.className = 'list-item';
        chip.style.whiteSpace = 'nowrap';
        chip.textContent = mood.name;
        chip.onclick = () => onSelect(mood.query);
        moodSection.appendChild(chip);
    });
    elements.genreGrid.appendChild(moodSection);

    // 2. Main Genres
    Object.values(GENRES).forEach(g => {
        const card = document.createElement('div');
        card.className = 'genre-card';
        card.innerHTML = `<div class="genre-icon">${g.icon}</div><div>${g.name}</div>`;
        card.onclick = () => {
            // Показать поджанры
            showSubgenres(g, onSelect);
        };
        elements.genreGrid.appendChild(card);
    });
}

function showSubgenres(genreObj, onSelect) {
    elements.genreGrid.innerHTML = `
        <div style="grid-column: 1/-1; margin-bottom: 10px; color: var(--primary-neon);" onclick="UI.resetGenres()">
            <span class="material-icons-round" style="vertical-align: middle;">arrow_back</span> Назад
        </div>
        <h3 style="grid-column: 1/-1;">${genreObj.name}</h3>
    `;
    
    genreObj.subgenres.forEach(sub => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = `<span>${sub.name}</span>`;
        item.onclick = () => onSelect(sub.query);
        elements.genreGrid.appendChild(item);
    });
}

function renderPlaylist(playlist, currentIndex, player) {
    elements.playlistContainer.innerHTML = '';
    if (playlist.length === 0) {
        elements.playlistContainer.innerHTML = '<div style="text-align:center; padding:20px; color:#666;">Пусто</div>';
        return;
    }

    playlist.forEach((track, idx) => {
        const item = document.createElement('div');
        item.className = `list-item ${idx === currentIndex ? 'active' : ''}`;
        item.innerHTML = `
            <span class="material-icons-round" style="margin-right: 10px; font-size: 20px;">
                ${idx === currentIndex ? 'equalizer' : 'music_note'}
            </span>
            <div style="overflow: hidden;">
                <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${track.title}</div>
                <div style="font-size: 12px; color: #888;">${track.artist}</div>
            </div>
        `;
        item.onclick = () => {
            player.playTrack(idx);
            toggleDrawer('playlist', false);
        };
        elements.playlistContainer.appendChild(item);
    });
}

function toggleDrawer(name, show) {
    elements.overlay.classList.toggle('active', show);
    if (name === 'genres') elements.drawerGenres.classList.toggle('active', show);
    if (name === 'playlist') elements.drawerPlaylist.classList.toggle('active', show);
    
    // Haptic feedback if in Telegram
    if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
    }
}

function initialize(player) {
    // Подписки
    subscribe('isPlaying', (playing) => {
        elements.playIcon.textContent = playing ? 'pause' : 'play_arrow';
    });
    
    subscribe('currentTrackIndex', (idx) => {
        const track = store.playlist[idx];
        if (track) {
            elements.title.textContent = track.title;
            elements.artist.textContent = track.artist;
            // Обновить документ title
            document.title = `${track.title} - Aurora`;
        }
        renderPlaylist(store.playlist, idx, player);
    });

    subscribe('playlist', (list) => {
        renderPlaylist(list, store.currentTrackIndex, player);
    });

    // Аудио события
    const audio = player.getAudioElement();
    audio.addEventListener('timeupdate', () => {
        if (audio.duration) {
            const pct = (audio.currentTime / audio.duration) * 100;
            elements.progressFill.style.width = pct + '%';
            elements.timeCurrent.textContent = fmt(audio.currentTime);
            elements.timeDuration.textContent = fmt(audio.duration);
        }
    });

    // Кнопки
    document.getElementById('btn-play-pause').onclick = () => player.togglePlay();
    document.getElementById('btn-next').onclick = () => player.nextTrack();
    document.getElementById('btn-prev').onclick = () => player.prevTrack();
    
    // Открытие шторок
    document.getElementById('btn-open-genres').onclick = () => {
        // Сброс и рендер жанров
        renderGenreMenu(async (query) => {
            toggleDrawer('genres', false);
            // Тут вызов загрузки через main.js callback (реализуем ниже)
            window.loadGenreHandler(query);
        });
        toggleDrawer('genres', true);
    };

    document.getElementById('btn-open-playlist').onclick = () => toggleDrawer('playlist', true);
    elements.overlay.onclick = () => {
        toggleDrawer('genres', false);
        toggleDrawer('playlist', false);
    };

    // Seekbar click
    document.querySelector('.progress-bar').onclick = (e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const p = (e.clientX - rect.left) / rect.width;
        player.seek(p);
    };

    // Экспорт для кнопки "Назад" в жанрах
    window.UI = { 
        resetGenres: () => renderGenreMenu(window.loadGenreHandler) 
    };
    
    // Первичный рендер
    renderGenreMenu(() => {});
}

export const UI = { initialize, toggleDrawer };
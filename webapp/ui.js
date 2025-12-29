import { store, subscribe } from './store.js';
import { GENRES, MOODS } from './genres.js';

// Кешируем элементы безопасным способом
const getEl = (id) => document.getElementById(id);

// Форматирование времени
const fmt = (s) => {
    if (isNaN(s)) return '0:00';
    return Math.floor(s/60) + ':' + Math.floor(s%60).toString().padStart(2,'0');
};

function renderGenreMenu(onSelect) {
    const grid = getEl('genre-grid');
    if (!grid) return;
    
    grid.innerHTML = '';
    
    // Moods
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
    grid.appendChild(moodSection);

    // Genres
    Object.values(GENRES).forEach(g => {
        const card = document.createElement('div');
        card.className = 'genre-card';
        card.innerHTML = `<div class="genre-icon">${g.icon}</div><div>${g.name}</div>`;
        card.onclick = () => showSubgenres(g, onSelect);
        grid.appendChild(card);
    });
}

function showSubgenres(genreObj, onSelect) {
    const grid = getEl('genre-grid');
    if (!grid) return;

    grid.innerHTML = `
        <div style="grid-column: 1/-1; margin-bottom: 15px; color: var(--primary-neon); cursor:pointer; display:flex; align-items:center; gap:5px;" onclick="UI.resetGenres()">
            <span class="material-icons-round">arrow_back</span> Назад
        </div>
        <h3 style="grid-column: 1/-1; margin-bottom: 10px;">${genreObj.name}</h3>
    `;
    
    genreObj.subgenres.forEach(sub => {
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = `<span>${sub.name}</span>`;
        item.onclick = () => onSelect(sub.query);
        grid.appendChild(item);
    });
}

function renderPlaylist(playlist, currentIndex, player) {
    const container = getEl('playlist-container');
    if (!container) return;

    container.innerHTML = '';
    if (playlist.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding:20px; color:#666;">Пустой плейлист</div>';
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
                <div style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500;">${track.title}</div>
                <div style="font-size: 12px; color: #888;">${track.artist}</div>
            </div>
        `;
        item.onclick = () => {
            player.playTrack(idx);
            toggleDrawer('playlist', false);
        };
        container.appendChild(item);
    });
}

function toggleDrawer(name, show) {
    const overlay = getEl('overlay');
    const dGenres = getEl('drawer-genres');
    const dPlaylist = getEl('drawer-playlist');

    if (overlay) overlay.classList.toggle('active', show);
    
    if (name === 'genres' && dGenres) {
        dGenres.classList.toggle('active', show);
        if (dPlaylist) dPlaylist.classList.remove('active');
    }
    if (name === 'playlist' && dPlaylist) {
        dPlaylist.classList.toggle('active', show);
        if (dGenres) dGenres.classList.remove('active');
    }

    // Haptic
    if (window.Telegram?.WebApp?.HapticFeedback) {
        window.Telegram.WebApp.HapticFeedback.impactOccurred('light');
    }
}

function initialize(player) {
    console.log('[UI] Initializing...');

    // Биндинг кнопок с проверкой
    const bindClick = (id, fn) => {
        const el = getEl(id);
        if (el) el.onclick = fn;
        else console.warn(`[UI] Button #${id} not found`);
    };

    bindClick('btn-play-pause', () => player.togglePlay());
    bindClick('btn-next', () => player.nextTrack());
    bindClick('btn-prev', () => player.prevTrack());
    
    // Drawers
    bindClick('btn-open-genres', () => {
        renderGenreMenu(window.loadGenreHandler); // Сброс меню при открытии
        toggleDrawer('genres', true);
    });
    bindClick('btn-open-playlist', () => toggleDrawer('playlist', true));
    bindClick('overlay', () => toggleDrawer(null, false));

    // Прогресс бар
    const bar = document.querySelector('.progress-bar');
    if (bar) {
        bar.onclick = (e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const p = (e.clientX - rect.left) / rect.width;
            player.seek(p);
        };
    }

    // Подписки Store
    subscribe('isPlaying', (playing) => {
        const icon = document.querySelector('#btn-play-pause .material-icons-round');
        if (icon) icon.textContent = playing ? 'pause' : 'play_arrow';
    });
    
    subscribe('currentTrackIndex', (idx) => {
        const track = store.playlist[idx];
        const tTitle = getEl('track-title');
        const tArtist = getEl('track-artist');
        
        if (track) {
            if (tTitle) tTitle.textContent = track.title;
            if (tArtist) tArtist.textContent = track.artist;
        }
        renderPlaylist(store.playlist, idx, player);
    });

    subscribe('playlist', (list) => {
        renderPlaylist(list, store.currentTrackIndex, player);
    });

    // Аудио обновления
    const audio = player.getAudioElement();
    const pFill = getEl('progress-fill');
    const tCurr = getEl('time-current');
    const tDur = getEl('time-duration');

    audio.addEventListener('timeupdate', () => {
        if (audio.duration) {
            const pct = (audio.currentTime / audio.duration) * 100;
            if (pFill) pFill.style.width = pct + '%';
            if (tCurr) tCurr.textContent = fmt(audio.currentTime);
            if (tDur) tDur.textContent = fmt(audio.duration);
        }
    });

    // Экспорт для кнопки "Назад"
    window.UI = { 
        resetGenres: () => renderGenreMenu(window.loadGenreHandler) 
    };
    
    // Первый рендер
    renderGenreMenu(() => {});
    console.log('[UI] Ready');
}

export const UI = { initialize, toggleDrawer };
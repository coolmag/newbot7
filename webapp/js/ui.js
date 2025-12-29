import { store, subscribe } from './store.js';
import { MENU_ROOT } from './genres.js';

// История навигации для кнопки "Назад"
let menuStack = [];

function getEl(id) { return document.getElementById(id); }

// Рендер меню (рекурсивный)
function renderMenuLevel(items, title = "Menu") {
    const grid = getEl('genre-grid');
    const titleEl = document.querySelector('#drawer-genres h2');
    if (!grid) return;
    
    // Обновляем заголовок
    if (titleEl) titleEl.textContent = title;

    grid.innerHTML = '';
    
    // Кнопка "Назад", если мы не в корне
    if (menuStack.length > 0) {
        const backBtn = document.createElement('div');
        backBtn.className = 'genre-btn back-btn';
        backBtn.innerHTML = `<span class="material-icons-round">arrow_back</span> Назад`;
        backBtn.onclick = () => {
            menuStack.pop(); // Убираем текущий уровень
            const prev = menuStack.length > 0 ? menuStack[menuStack.length - 1] : { items: MENU_ROOT.children, title: MENU_ROOT.name };
            
            // Если вернулись в корень, очищаем стек совсем, чтобы логика работала верно
            if (menuStack.length === 0) {
                 renderMenuLevel(MENU_ROOT.children, MENU_ROOT.name);
            } else {
                 renderMenuLevel(prev.items, prev.title);
            }
        };
        grid.appendChild(backBtn);
    }

    items.forEach(item => {
        const btn = document.createElement('div');
        btn.className = 'genre-btn';
        
        // Разный стиль для папок и для конечных жанров
        if (item.children) {
            btn.className += ' folder';
            btn.innerHTML = `<span class="material-icons-round">folder</span> ${item.name}`;
            btn.onclick = () => {
                menuStack.push({ items, title }); // Сохраняем текущий уровень
                renderMenuLevel(item.children, item.name);
            };
        } else {
            // Это конечный жанр или действие
            const icon = item.type === 'action' ? 'casino' : 'music_note';
            btn.innerHTML = `<span class="material-icons-round">${icon}</span> ${item.name}`;
            
            btn.onclick = () => {
                if (item.action === 'random') {
                    // Логика рандома
                    const randomQuery = getRandomQuery(MENU_ROOT);
                    window.loadGenreHandler(randomQuery);
                } else {
                    window.loadGenreHandler(item.query);
                }
            };
        }
        grid.appendChild(btn);
    });
}

// Рекурсивный поиск случайного жанра
function getRandomQuery(node) {
    if (node.query) return node.query;
    if (node.children) {
        const randomChild = node.children[Math.floor(Math.random() * node.children.length)];
        return getRandomQuery(randomChild);
    }
    return "lofi hip hop"; // fallback
}

function renderPlaylist(playlist, currentIndex, player) {
    const container = getEl('playlist-container');
    if (!container) return;

    container.innerHTML = '';
    if (!playlist || playlist.length === 0) {
        container.innerHTML = '<div style="text-align:center; padding:20px; color:#666;">Empty</div>';
        return;
    }

    playlist.forEach((track, idx) => {
        const item = document.createElement('div');
        item.className = `list-item ${idx === currentIndex ? 'active' : ''}`;
        
        // Более компактный вид для ПК
        item.innerHTML = `
            <div class="list-icon">
                <span class="material-icons-round">${idx === currentIndex ? 'equalizer' : 'music_note'}</span>
            </div>
            <div class="list-info">
                <div class="list-title">${track.title}</div>
                <div class="list-artist">${track.artist}</div>
            </div>
            <div class="list-time">${track.duration || ''}</div>
        `;
        
        item.onclick = () => {
            player.playTrack(idx);
            toggleDrawer('playlist', false);
        };
        container.appendChild(item);
    });
    
    // Авто-скролл к текущему треку
    const activeItem = container.querySelector('.active');
    if (activeItem) activeItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function toggleDrawer(name, show) {
    const overlay = getEl('overlay');
    const dGenres = getEl('drawer-genres');
    const dPlaylist = getEl('drawer-playlist');

    if (show) {
        overlay.classList.add('active');
        if (name === 'genres') {
            dGenres.classList.add('active');
            dPlaylist.classList.remove('active');
            // При открытии жанров всегда показываем корень, если это первое открытие
            if (menuStack.length === 0) renderMenuLevel(MENU_ROOT.children, MENU_ROOT.name);
        }
        if (name === 'playlist') {
            dPlaylist.classList.add('active');
            dGenres.classList.remove('active');
        }
    } else {
        overlay.classList.remove('active');
        if (dGenres) dGenres.classList.remove('active');
        if (dPlaylist) dPlaylist.classList.remove('active');
    }
}

function initialize(player) {
    subscribe('currentTrackIndex', (idx) => {
        const track = store.playlist[idx];
        if (track) {
            const tt = getEl('track-title');
            const ta = getEl('track-artist');
            if(tt) tt.textContent = track.title;
            if(ta) ta.textContent = track.artist;
            
            // Обновляем MediaSession (для управления с клавиатуры ПК)
            if ('mediaSession' in navigator) {
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: track.title,
                    artist: track.artist,
                    artwork: [{ src: 'favicon.png', sizes: '512x512', type: 'image/png' }]
                });
            }
        }
        renderPlaylist(store.playlist, idx, player);
    });

    subscribe('playlist', (list) => {
        renderPlaylist(list, store.currentTrackIndex, player);
    });

    // Прогресс бар
    const audio = player.getAudioElement();
    audio.addEventListener('timeupdate', () => {
        if (!audio.duration) return;
        const pct = (audio.currentTime / audio.duration) * 100;
        const fill = getEl('progress-fill');
        const curr = getEl('time-current');
        const dur = getEl('time-duration');
        
        if (fill) fill.style.width = pct + '%';
        if (curr) curr.textContent = formatTime(audio.currentTime);
        if (dur) dur.textContent = formatTime(audio.duration);
    });
    
    // Клик по прогресс бару
    const pContainer = document.querySelector('.progress-container');
    if(pContainer) {
        pContainer.onclick = (e) => {
            const rect = pContainer.getBoundingClientRect();
            const p = (e.clientX - rect.left) / rect.width;
            player.seek(p);
        };
    }

    // Кнопки
    const bind = (id, fn) => { const el = getEl(id); if(el) el.onclick = fn; };
    bind('btn-play-pause', () => player.togglePlay());
    bind('btn-next', () => player.nextTrack());
    bind('btn-prev', () => player.prevTrack());
    bind('btn-open-genres', () => toggleDrawer('genres', true));
    bind('btn-open-playlist', () => toggleDrawer('playlist', true));
    bind('overlay', () => toggleDrawer(null, false));
    
    // Обновление иконки Play/Pause
    subscribe('isPlaying', (playing) => {
        const icon = document.querySelector('#btn-play-pause span');
        if(icon) icon.textContent = playing ? 'pause' : 'play_arrow';
    });
}

function formatTime(s) {
    if(isNaN(s)) return '0:00';
    const m = Math.floor(s/60);
    const sec = Math.floor(s%60);
    return `${m}:${sec.toString().padStart(2,'0')}`;
}

export const UI = { initialize, toggleDrawer };
import { store, subscribe } from './store.js';
import { MENU_ROOT } from './genres.js';

let menuStack = []; // История переходов

function getEl(id) { return document.getElementById(id); }

// Генератор рандома
function getRandomQuery(node) {
    if (node.query) return node.query;
    if (node.children) {
        const child = node.children[Math.floor(Math.random() * node.children.length)];
        return getRandomQuery(child);
    }
    return "lofi hip hop";
}

// --- ОТРИСОВКА МЕНЮ (ЖАНРОВ) ---
function renderMenu() {
    const drawer = getEl('drawer-genres');
    if (!drawer) return;

    // Определяем, где мы находимся
    const current = menuStack.length > 0 
        ? menuStack[menuStack.length - 1] 
        : { title: "Frequency", items: MENU_ROOT.children, isRoot: true };

    drawer.innerHTML = ''; 

    // 1. ШАПКА (Header) с навигацией
    const header = document.createElement('div');
    header.className = 'drawer-header';

    // Кнопка НАЗАД
    const backBtn = document.createElement('button');
    backBtn.className = 'nav-btn';
    backBtn.innerHTML = '<span class="material-icons-round">arrow_back_ios_new</span>';
    backBtn.onclick = () => {
        if (!current.isRoot) {
            menuStack.pop();
            renderMenu();
        }
    };
    // Скрываем, если мы в главном меню
    backBtn.style.visibility = current.isRoot ? 'hidden' : 'visible';

    // ЗАГОЛОВОК
    const title = document.createElement('div');
    title.className = 'drawer-title-text';
    title.textContent = current.title;

    // Кнопка ЗАКРЫТЬ
    const closeBtn = document.createElement('button');
    closeBtn.className = 'nav-btn';
    closeBtn.innerHTML = '<span class="material-icons-round">close</span>';
    closeBtn.onclick = () => toggleDrawer('genres', false);

    header.appendChild(backBtn);
    header.appendChild(title);
    header.appendChild(closeBtn);
    drawer.appendChild(header);

    // 2. СПИСОК (List)
    const listContainer = document.createElement('div');
    listContainer.className = 'scroll-area menu-list';

    current.items.forEach(item => {
        const row = document.createElement('div');
        row.className = 'menu-row';
        
        // Иконка
        let iconHtml = '';
        if (item.action === 'random') iconHtml = '<span class="material-icons-round row-icon random">shuffle</span>';
        else if (item.children) iconHtml = '<span class="material-icons-round row-icon folder">folder</span>';
        else iconHtml = '<span class="material-icons-round row-icon music">music_note</span>';

        // Стрелочка справа, если это папка
        const arrowHtml = item.children 
            ? '<span class="material-icons-round row-arrow">chevron_right</span>' 
            : '';

        row.innerHTML = `
            <div class="row-left">
                ${iconHtml}
                <span class="row-title">${item.name}</span>
            </div>
            ${arrowHtml}
        `;
        
        row.onclick = () => {
            // Эффект нажатия
            row.classList.add('clicked');
            setTimeout(() => row.classList.remove('clicked'), 200);

            if (item.children) {
                // Входим внутрь
                menuStack.push({ title: item.name, items: item.children, isRoot: false });
                setTimeout(renderMenu, 50); 
            } else {
                // Выбираем жанр
                toggleDrawer('genres', false);
                if (item.action === 'random') {
                    const q = getRandomQuery(MENU_ROOT);
                    window.loadGenreHandler(q);
                } else {
                    window.loadGenreHandler(item.query);
                }
            }
        };
        listContainer.appendChild(row);
    });

    drawer.appendChild(listContainer);
}

// --- ОТРИСОВКА ПЛЕЙЛИСТА ---
function renderPlaylist(playlist, currentIndex, player) {
    const container = getEl('playlist-container');
    if (!container) return;

    container.innerHTML = '';
    if (!playlist || playlist.length === 0) {
        container.innerHTML = '<div class="empty-state">Queue is empty</div>';
        return;
    }

    // Создаем контейнер заголовка для плейлиста тоже (для симметрии)
    // Но так как шторка плейлиста уже имеет заголовок в HTML, просто заполняем список

    playlist.forEach((track, idx) => {
        const item = document.createElement('div');
        item.className = `playlist-row ${idx === currentIndex ? 'active' : ''}`;
        
        // Красивая иконка слева
        const iconType = idx === currentIndex ? 'equalizer' : 'music_note';
        
        item.innerHTML = `
            <div class="p-icon-box">
                <span class="material-icons-round">${iconType}</span>
            </div>
            <div class="p-info">
                <div class="p-title">${track.title}</div>
                <div class="p-artist">${track.artist}</div>
            </div>
        `;
        
        item.onclick = () => {
            player.playTrack(idx);
            toggleDrawer('playlist', false);
        };
        container.appendChild(item);
    });
    
    // Скролл к активному треку
    const activeEl = container.querySelector('.active');
    if (activeEl) activeEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
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
            // Если открываем первый раз или стек пуст - рендерим корень
            if (menuStack.length === 0) renderMenu();
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
    // Подписки на Store
    subscribe('currentTrackIndex', (idx) => {
        const track = store.playlist[idx];
        if (track) {
            const tt = getEl('track-title');
            const ta = getEl('track-artist');
            if(tt) tt.textContent = track.title;
            if(ta) ta.textContent = track.artist;
            
            if ('mediaSession' in navigator) {
                navigator.mediaSession.metadata = new MediaMetadata({
                    title: track.title,
                    artist: track.artist
                });
            }
        }
        renderPlaylist(store.playlist, idx, player);
    });

    subscribe('playlist', (list) => {
        renderPlaylist(list, store.currentTrackIndex, player);
    });

    // Прогресс
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

    // Биндинг кнопок
    const bind = (id, fn) => { const el = getEl(id); if(el) el.onclick = fn; };
    bind('btn-play-pause', () => player.togglePlay());
    bind('btn-next', () => player.nextTrack());
    bind('btn-prev', () => player.prevTrack());
    bind('btn-open-genres', () => toggleDrawer('genres', true));
    bind('btn-open-playlist', () => toggleDrawer('playlist', true));
    bind('overlay', () => toggleDrawer(null, false));
    
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
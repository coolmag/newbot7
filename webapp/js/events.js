// js/events.js

import store from './store.js';
import * as elements from './elements.js';
import * as player from './player.js';
import * as api from './api.js';
import * as renderer from './renderer.js';
import { haptic } from './ui-helpers.js';
import { GENRES, TRENDING, DECADES, MOODS } from './constants.js';

let fuse; // Fuse.js instance

// --- Reusable Logic ---

async function selectGenre(name, searchQuery) {
    if (store.isLoading) return;
    store.isLoading = true;
    store.currentGenre = name;
    
    closeGenresScreen();
    closeDrawers();
    haptic.impact('medium');

    try {
        const playlist = await api.fetchPlaylistByQuery(searchQuery);
        store.playlist = playlist;
        if (playlist.length > 0) player.playTrack(0);
    } catch (e) {
        console.error('Failed to select genre:', e);
    } finally {
        store.isLoading = false;
    }
}

function closeDrawers() {
    elements.subgenreDrawer?.classList.remove('active');
    elements.playlistDrawer?.classList.remove('active');
    elements.overlay?.classList.remove('active');
}

function openGenresScreen() {
    elements.screenGenres?.classList.add('active');
    elements.screenPlayer?.classList.add('blurred');
    elements.overlay?.classList.add('active');
    // Animate the cards appearing
    staggeredFadeIn(document.querySelectorAll('.genre-card'));
}

function closeGenresScreen() {
    elements.screenGenres?.classList.remove('active');
    elements.screenPlayer?.classList.remove('blurred');
    elements.overlay?.classList.remove('active');
}

/**
 * Applies a staggered fade-in animation to a collection of elements.
 * @param {NodeListOf<Element>} cards - The elements to animate.
 */
function staggeredFadeIn(cards) {
    cards.forEach((card, index) => {
        // Reset state before animating
        card.classList.remove('visible');
        card.style.transitionDelay = `${index * 30}ms`;
        // Use a timeout to ensure the browser applies the initial state before adding the visible class
        setTimeout(() => card.classList.add('visible'), 10);
    });
}

/**
 * Attaches the spotlight mouse-tracking effect to genre cards.
 * @param {HTMLElement} container - The container of the cards to attach the effect to.
 */
function attachSpotlightEffect(container) {
    container.addEventListener('mousemove', (e) => {
        const card = e.target.closest('.genre-card');
        if (card) {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            card.style.setProperty('--mouse-x', `${x}px`);
            card.style.setProperty('--mouse-y', `${y}px`);
        }
    });
}

// --- UI Component Builders ---

function createChips(container, items) {
    if (!container) return;
    container.innerHTML = '';
    items.forEach(item => {
        const chip = document.createElement('button');
        chip.className = 'chip';
        chip.textContent = item.name;
        chip.onclick = () => {
            selectGenre(item.name, item.search);
            haptic.selection();
        };
        container.appendChild(chip);
    });
}

function buildGenreCard(genre) {
    const card = document.createElement('button');
    card.className = 'genre-card';
    card.style.background = `linear-gradient(145deg, ${genre.color} 0%, rgba(0,0,0,0.4) 100%)`;

    card.innerHTML = `<div class="genre-icon">${genre.icon}</div><div class="genre-name">${genre.name}</div>`;
    
    card.onclick = () => {
        elements.drawerTitle.textContent = genre.name;
        elements.drawerIcon.textContent = genre.icon;
        elements.subgenreList.innerHTML = '';
        Object.values(genre.subgenres).forEach(sub => {
            const item = document.createElement('button');
            item.className = 'subgenre-item';
            item.innerHTML = `<div><div class="subgenre-name">${sub.name}</div><div class="subgenre-styles">${sub.styles}</div></div><span class="material-icons-round">arrow_forward</span>`;
            item.onclick = () => selectGenre(sub.name, sub.search);
            elements.subgenreList.appendChild(item);
        });
        elements.subgenreDrawer.classList.add('active');
        elements.overlay.classList.add('active');
        haptic.impact('medium');
    };
    return card;
}

function renderAllGenres() {
    if (!elements.genreGrid) return [];
    elements.genreGrid.innerHTML = '';
    const allGenres = Object.values(GENRES);
    allGenres.forEach(genre => {
        elements.genreGrid.appendChild(buildGenreCard(genre));
    });
    return allGenres;
}

/**
 * Attaches all the application's event listeners to the DOM elements.
 */
export function initializeEventListeners() {
    console.log('[Events] Initializing event listeners...');

    // Initialize Fuse.js for fuzzy search
    const allGenres = renderAllGenres();
    const fuseOptions = {
        keys: ['name', 'subgenres.name', 'subgenres.styles'],
        includeScore: true,
        threshold: 0.3,
    };
    fuse = new Fuse(allGenres, fuseOptions);

    // Player Controls
    elements.playBtn?.addEventListener('click', () => { player.togglePlayPause(); haptic.impact('light'); });
    elements.nextBtn?.addEventListener('click', () => { player.playNext(); haptic.impact('medium'); });
    elements.prevBtn?.addEventListener('click', () => { player.playPrev(); haptic.impact('medium'); });
    elements.rewindBtn?.addEventListener('click', () => { player.seek(-10); haptic.impact('light'); });
    elements.forwardBtn?.addEventListener('click', () => { player.seek(10); haptic.impact('light'); });

    // Speed Control
    elements.playbackSpeed?.addEventListener('change', (e) => {
        if (elements.audio) elements.audio.playbackRate = parseFloat(e.target.value);
        haptic.selection();
    });

    // Progress Bar
    elements.progressContainer?.addEventListener('click', (e) => {
        if (!elements.audio?.duration) return;
        const rect = elements.progressContainer.getBoundingClientRect();
        const percent = (e.clientX - rect.left) / rect.width;
        elements.audio.currentTime = percent * elements.audio.duration;
        haptic.impact('light');
    });
    
    // Navigation
    elements.btnGenres?.addEventListener('click', () => { openGenresScreen(); haptic.impact('medium'); });
    elements.btnBackPlayer?.addEventListener('click', () => { closeGenresScreen(); haptic.impact('medium'); });
    elements.btnPlaylist?.addEventListener('click', () => {
        renderer.renderPlaylistDrawer();
        elements.playlistDrawer?.classList.add('active');
        elements.overlay?.classList.add('active');
        haptic.impact('medium');
    });

    // Playlist item clicks
    elements.playlistContent?.addEventListener('click', (e) => {
        const item = e.target.closest('.playlist-item');
        if (item?.dataset.trackIndex) {
            player.playTrack(parseInt(item.dataset.trackIndex, 10));
            closeDrawers();
            haptic.impact('light');
        }
    });

    elements.overlay?.addEventListener('click', closeDrawers);
    
    // Initialize static UI parts
    createChips(elements.trendingChips, TRENDING);
    createChips(elements.decadeChips, DECADES);
    createChips(elements.moodChips, MOODS);
    
    // Fuzzy Search Input
    elements.genreSearch?.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        if (!elements.genreGrid) return;
        
        elements.genreGrid.innerHTML = '';
        let results;
        if (query) {
            results = fuse.search(query).map(result => result.item);
        } else {
            results = allGenres;
        }

        if (results.length === 0) {
            elements.genreGrid.innerHTML = `<div class="playlist-empty" style="text-align: center; padding: 2rem;">No genres found.</div>`;
        } else {
            results.forEach(genre => {
                elements.genreGrid.appendChild(buildGenreCard(genre));
            });
        }
        staggeredFadeIn(elements.genreGrid.querySelectorAll('.genre-card'));
    });

    // Dynamic search on Enter
    elements.genreSearch?.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            const query = e.target.value.trim();
            if (query) {
                await selectGenre("Search: " + query, query);
                e.target.value = '';
            }
            haptic.impact('medium');
            e.preventDefault();
        }
    });

    // Attach premium visual effects
    if (elements.genreGrid) attachSpotlightEffect(elements.genreGrid);

    // Show genres screen initially if no playlist has been loaded
    if (store.playlist.length === 0) {
        openGenresScreen();
    }
}

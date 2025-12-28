import { store } from './store.js';
import { api } from './api.js';
import { Player } from './player.js';
import { Visualizer } from './visualizer.js';
import { UI } from './ui.js';

// --- Genre Definitions ---
const GENRES = {
    'Lofi & Chill': 'lofi hip hop radio',
    'Synthwave': 'synthwave retro wave',
    'Classic Rock': 'classic rock hits',
    'Deep House': 'deep house mix',
    'Ambient': 'ambient music',
    'Cyberpunk': 'darksynth industrial',
};

// --- Application Entry Point ---
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Main] Aurora Player Initializing...');

    // 1. Initialize UI and get event handlers
    UI.initialize(Player);

    // 2. Populate the genre list
    UI.populateGenres(GENRES, async (query) => {
        // Когда жанр выбран
        UI.toggleGenresDrawer(false);
        store.playlist = []; // Очищаем старый плейлист
        store.currentGenre = Object.keys(GENRES).find(key => GENRES[key] === query);
        
        const playlist = await api.fetchPlaylist(query);
        store.playlist = playlist;
        
        // Автоматически запускаем первый трек
        if (playlist.length > 0) {
            Player.playTrack(0);
        }
    });

    // 3. Initialize Visualizer on first user interaction
    document.body.addEventListener('click', () => {
        const audioEl = Player.getAudioElement();
        Visualizer.initialize(audioEl);
        console.log('[Main] Visualizer activated.');
    }, { once: true });
    
    // 4. Load a default playlist to start
    (async () => {
        store.currentGenre = 'Lofi & Chill';
        const initialPlaylist = await api.fetchPlaylist(GENRES['Lofi & Chill']);
        store.playlist = initialPlaylist;
    })();

    console.log('[Main] Aurora Player is ready.');
});

export class TrackManager {
    constructor() {
        this.tracks = [];
        this.currentIndex = 0;
        this.playHistory = [];
        this.favorites = new Set();
        this.playlists = new Map();
        this.genres = new Set();
        
        this.audioFormats = {
            mp3: 'audio/mpeg',
            flac: 'audio/flac',
            wav: 'audio/wav',
            ogg: 'audio/ogg',
            m4a: 'audio/mp4'
        };
        
        this.init();
    }

    async init() {
        await this.loadLocalTracks();
        this.loadFavorites();
        this.loadPlaylists();
        this.scanGenres();
    }

    async loadTracks() {
        try {
            // Загрузка треков из локального хранилища
            const savedTracks = localStorage.getItem('neovinyl_tracks');
            
            if (savedTracks) {
                this.tracks = JSON.parse(savedTracks);
                console.log(`Loaded ${this.tracks.length} tracks from storage`);
            } else {
                // Загрузка демо-треков по умолчанию
                await this.loadDemoTracks();
                this.saveToLocalStorage();
            }
            
            // Сканирование жанров
            this.scanGenres();
            
            // Создание индексов для быстрого поиска
            this.createSearchIndex();
            
            return this.tracks;
        } catch (error) {
            console.error('Error loading tracks:', error);
            return [];
        }
    }

    async loadDemoTracks() {
        // Демо-треки с киберпанк эстетикой
        this.tracks = [
            {
                id: 'track_001',
                index: 0,
                title: 'NEON DREAMS',
                artist: 'CYBER SYSTEMS',
                album: 'DIGITAL VINYL',
                genre: 'electronic',
                bpm: 128,
                duration: 260, // 4:20
                durationFormatted: '4:20',
                year: 2025,
                url: 'assets/tracks/neon-dreams.mp3',
                cover: 'assets/covers/digital-vinyl.jpg',
                waveform: 'assets/waveforms/neon-dreams.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 48000,
                    channels: 2,
                    encoder: 'NeoVinyl v2.0'
                },
                tags: ['cyberpunk', 'synthwave', 'retrowave'],
                color: '#00f3ff'
            },
            {
                id: 'track_002',
                index: 1,
                title: 'GRID OVERLOAD',
                artist: 'NEURAL NETWORK',
                album: 'MATRIX RESONANCE',
                genre: 'electronic',
                bpm: 140,
                duration: 215,
                durationFormatted: '3:35',
                year: 2025,
                url: 'assets/tracks/grid-overload.mp3',
                cover: 'assets/covers/matrix-resonance.jpg',
                waveform: 'assets/waveforms/grid-overload.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 44100,
                    channels: 2,
                    encoder: 'Quantum Audio'
                },
                tags: ['darksynth', 'industrial', 'techno'],
                color: '#ff00ff'
            },
            {
                id: 'track_003',
                index: 2,
                title: 'SILICON RAIN',
                artist: 'VOID OPERATOR',
                album: 'DIGITAL GHOSTS',
                genre: 'ambient',
                bpm: 90,
                duration: 328,
                durationFormatted: '5:28',
                year: 2024,
                url: 'assets/tracks/silicon-rain.mp3',
                cover: 'assets/covers/digital-ghosts.jpg',
                waveform: 'assets/waveforms/silicon-rain.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 48000,
                    channels: 2,
                    encoder: 'Atmospheric Processor'
                },
                tags: ['ambient', 'downtempo', 'chillout'],
                color: '#00ccff'
            },
            {
                id: 'track_004',
                index: 3,
                title: 'NEUROMANCER',
                artist: 'CYBERPUNK COLLECTIVE',
                album: 'CLASSIC HACKS',
                genre: 'rock',
                bpm: 120,
                duration: 245,
                durationFormatted: '4:05',
                year: 2023,
                url: 'assets/tracks/neuromancer.mp3',
                cover: 'assets/covers/classic-hacks.jpg',
                waveform: 'assets/waveforms/neuromancer.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 44100,
                    channels: 2,
                    encoder: 'Retro Synth'
                },
                tags: ['synthrock', 'cyberpunk', 'retro'],
                color: '#ff6600'
            },
            {
                id: 'track_005',
                index: 4,
                title: 'DATA STREAM',
                artist: 'QUANTUM FLUX',
                album: 'BINARY RHYTHMS',
                genre: 'electronic',
                bpm: 155,
                duration: 192,
                durationFormatted: '3:12',
                year: 2025,
                url: 'assets/tracks/data-stream.mp3',
                cover: 'assets/covers/binary-rhythms.jpg',
                waveform: 'assets/waveforms/data-stream.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 48000,
                    channels: 2,
                    encoder: 'Digital Weaver'
                },
                tags: ['techno', 'trance', 'progressive'],
                color: '#00ffcc'
            },
            {
                id: 'track_006',
                index: 5,
                title: 'CRYSTAL MEMORY',
                artist: 'HYPERSPACE DRIFTER',
                album: 'VOID TRANSMISSIONS',
                genre: 'ambient',
                bpm: 85,
                duration: 420,
                durationFormatted: '7:00',
                year: 2024,
                url: 'assets/tracks/crystal-memory.mp3',
                cover: 'assets/covers/void-transmissions.jpg',
                waveform: 'assets/waveforms/crystal-memory.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 48000,
                    channels: 2,
                    encoder: 'Cosmic Sampler'
                },
                tags: ['space', 'ambient', 'experimental'],
                color: '#cc66ff'
            },
            {
                id: 'track_007',
                index: 6,
                title: 'GLITCH CITY',
                artist: 'ERROR CORRECTION',
                album: 'SYSTEM FAILURE',
                genre: 'electronic',
                bpm: 135,
                duration: 235,
                durationFormatted: '3:55',
                year: 2025,
                url: 'assets/tracks/glitch-city.mp3',
                cover: 'assets/covers/system-failure.jpg',
                waveform: 'assets/waveforms/glitch-city.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 44100,
                    channels: 2,
                    encoder: 'Glitch Generator'
                },
                tags: ['glitch', 'idm', 'experimental'],
                color: '#ff3333'
            },
            {
                id: 'track_008',
                index: 7,
                title: 'SOLAR FLARE',
                artist: 'COSMIC DRONE',
                album: 'STELLAR DRIFT',
                genre: 'ambient',
                bpm: 100,
                duration: 312,
                durationFormatted: '5:12',
                year: 2024,
                url: 'assets/tracks/solar-flare.mp3',
                cover: 'assets/covers/stellar-drift.jpg',
                waveform: 'assets/waveforms/solar-flare.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 48000,
                    channels: 2,
                    encoder: 'Solar Processor'
                },
                tags: ['drone', 'ambient', 'space'],
                color: '#ffcc00'
            },
            {
                id: 'track_009',
                index: 8,
                title: 'NEURAL PATH',
                artist: 'SYNAPSE COLLECTIVE',
                album: 'COGNITIVE PATTERNS',
                genre: 'electronic',
                bpm: 125,
                duration: 278,
                durationFormatted: '4:38',
                year: 2025,
                url: 'assets/tracks/neural-path.mp3',
                cover: 'assets/covers/cognitive-patterns.jpg',
                waveform: 'assets/waveforms/neural-path.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 48000,
                    channels: 2,
                    encoder: 'Neural Network'
                },
                tags: ['experimental', 'electronic', 'psychill'],
                color: '#66ff66'
            },
            {
                id: 'track_010',
                index: 9,
                title: 'DIGITAL ECHO',
                artist: 'VOID TRANSMISSION',
                album: 'SIGNAL LOSS',
                genre: 'ambient',
                bpm: 80,
                duration: 345,
                durationFormatted: '5:45',
                year: 2024,
                url: 'assets/tracks/digital-echo.mp3',
                cover: 'assets/covers/signal-loss.jpg',
                waveform: 'assets/waveforms/digital-echo.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 44100,
                    channels: 2,
                    encoder: 'Echo Processor'
                },
                tags: ['ambient', 'drone', 'minimal'],
                color: '#9966ff'
            },
            {
                id: 'track_011',
                index: 10,
                title: 'ROBOT HEART',
                artist: 'MECHANICAL SOUL',
                album: 'AUTOMATED EMOTIONS',
                genre: 'electronic',
                bpm: 130,
                duration: 224,
                durationFormatted: '3:44',
                year: 2025,
                url: 'assets/tracks/robot-heart.mp3',
                cover: 'assets/covers/automated-emotions.jpg',
                waveform: 'assets/waveforms/robot-heart.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 48000,
                    channels: 2,
                    encoder: 'Robotic Processor'
                },
                tags: ['electro', 'synthpop', 'retro'],
                color: '#ff6699'
            },
            {
                id: 'track_012',
                index: 11,
                title: 'CYBER TEMPLE',
                artist: 'DIGITAL MONK',
                album: 'CODE MEDITATION',
                genre: 'ambient',
                bpm: 70,
                duration: 480,
                durationFormatted: '8:00',
                year: 2024,
                url: 'assets/tracks/cyber-temple.mp3',
                cover: 'assets/covers/code-meditation.jpg',
                waveform: 'assets/waveforms/cyber-temple.json',
                metadata: {
                    bitrate: 320,
                    sampleRate: 48000,
                    channels: 2,
                    encoder: 'Zen Coder'
                },
                tags: ['meditation', 'ambient', 'minimal'],
                color: '#33cccc'
            }
        ];
        
        console.log('Loaded demo tracks:', this.tracks.length);
    }

    async loadLocalTracks() {
        // Проверка наличия треков в IndexedDB
        try {
            const db = await this.openDatabase();
            const tracks = await this.getAllTracksFromDB(db);
            
            if (tracks.length > 0) {
                this.tracks = tracks;
                console.log(`Loaded ${tracks.length} tracks from IndexedDB`);
            }
        } catch (error) {
            console.warn('Could not load tracks from IndexedDB:', error);
        }
    }

    async openDatabase() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open('NeoVinylDB', 2);
            
            request.onerror = () => reject(request.error);
            request.onsuccess = () => resolve(request.result);
            
            request.onupgradeneeded = (event) => {
                const db = event.target.result;
                
                if (!db.objectStoreNames.contains('tracks')) {
                    const store = db.createObjectStore('tracks', { keyPath: 'id' });
                    store.createIndex('artist', 'artist', { unique: false });
                    store.createIndex('genre', 'genre', { unique: false });
                    store.createIndex('year', 'year', { unique: false });
                }
                
                if (!db.objectStoreNames.contains('playlists')) {
                    db.createObjectStore('playlists', { keyPath: 'id' });
                }
                
                if (!db.objectStoreNames.contains('favorites')) {
                    db.createObjectStore('favorites', { keyPath: 'trackId' });
                }
            };
        });
    }

    async getAllTracksFromDB(db) {
        return new Promise((resolve, reject) => {
            const transaction = db.transaction('tracks', 'readonly');
            const store = transaction.objectStore('tracks');
            const request = store.getAll();
            
            request.onsuccess = () => resolve(request.result);
            request.onerror = () => reject(request.error);
        });
    }

    saveToLocalStorage() {
        try {
            localStorage.setItem('neovinyl_tracks', JSON.stringify(this.tracks));
            console.log('Tracks saved to localStorage');
        } catch (error) {
            console.error('Error saving tracks to localStorage:', error);
        }
    }

    loadFavorites() {
        try {
            const favorites = localStorage.getItem('neovinyl_favorites');
            if (favorites) {
                this.favorites = new Set(JSON.parse(favorites));
            }
        } catch (error) {
            console.error('Error loading favorites:', error);
        }
    }

    loadPlaylists() {
        try {
            const playlists = localStorage.getItem('neovinyl_playlists');
            if (playlists) {
                this.playlists = new Map(JSON.parse(playlists));
            }
        } catch (error) {
            console.error('Error loading playlists:', error);
        }
    }

    scanGenres() {
        this.genres.clear();
        this.tracks.forEach(track => {
            if (track.genre) {
                this.genres.add(track.genre.toLowerCase());
            }
        });
    }

    createSearchIndex() {
        this.searchIndex = this.tracks.map(track => ({
            id: track.id,
            title: track.title.toLowerCase(),
            artist: track.artist.toLowerCase(),
            album: track.album.toLowerCase(),
            genre: track.genre.toLowerCase(),
            tags: track.tags ? track.tags.join(' ').toLowerCase() : ''
        }));
    }

    getNextTrack(currentTrack, shuffle = false) {
        if (shuffle) {
            return this.getRandomTrack();
        }
        
        const currentIndex = this.tracks.findIndex(t => t.id === currentTrack.id);
        if (currentIndex === -1) return null;
        
        const nextIndex = (currentIndex + 1) % this.tracks.length;
        
        // Добавление в историю
        this.addToHistory(currentTrack);
        
        return this.tracks[nextIndex];
    }

    getPrevTrack(currentTrack) {
        const currentIndex = this.tracks.findIndex(t => t.id === currentTrack.id);
        if (currentIndex === -1) return null;
        
        const prevIndex = currentIndex === 0 ? this.tracks.length - 1 : currentIndex - 1;
        return this.tracks[prevIndex];
    }

    getRandomTrack() {
        const availableTracks = this.tracks.filter(track => 
            !this.playHistory.includes(track.id)
        );
        
        if (availableTracks.length === 0) {
            // Если все треки были проиграны, сбрасываем историю
            this.playHistory = [];
            return this.tracks[Math.floor(Math.random() * this.tracks.length)];
        }
        
        const randomTrack = availableTracks[
            Math.floor(Math.random() * availableTracks.length)
        ];
        
        this.addToHistory(randomTrack);
        return randomTrack;
    }

    addToHistory(track) {
        this.playHistory.push(track.id);
        
        // Ограничение истории до последних 50 треков
        if (this.playHistory.length > 50) {
            this.playHistory.shift();
        }
    }

    searchTracks(query) {
        if (!query || !this.searchIndex) return this.tracks;
        
        const searchTerms = query.toLowerCase().split(' ');
        
        return this.tracks.filter((track, index) => {
            const indexData = this.searchIndex[index];
            
            return searchTerms.some(term => 
                indexData.title.includes(term) ||
                indexData.artist.includes(term) ||
                indexData.album.includes(term) ||
                indexData.genre.includes(term) ||
                indexData.tags.includes(term)
            );
        });
    }

    filterByGenre(genre) {
        return this.tracks.filter(track => 
            track.genre.toLowerCase() === genre.toLowerCase()
        );
    }

    filterByYear(year) {
        return this.tracks.filter(track => track.year === year);
    }

    filterByBPM(minBPM, maxBPM) {
        return this.tracks.filter(track => 
            track.bpm >= minBPM && track.bpm <= maxBPM
        );
    }

    sortTracks(criteria) {
        const sortedTracks = [...this.tracks];
        
        switch(criteria) {
            case 'title':
                sortedTracks.sort((a, b) => a.title.localeCompare(b.title));
                break;
            case 'artist':
                sortedTracks.sort((a, b) => a.artist.localeCompare(b.artist));
                break;
            case 'year':
                sortedTracks.sort((a, b) => b.year - a.year);
                break;
            case 'bpm':
                sortedTracks.sort((a, b) => b.bpm - a.bpm);
                break;
            case 'duration':
                sortedTracks.sort((a, b) => b.duration - a.duration);
                break;
            case 'random':
                this.shuffleArray(sortedTracks);
                break;
            default:
                sortedTracks.sort((a, b) => a.index - b.index);
        }
        
        // Обновление индексов
        sortedTracks.forEach((track, index) => {
            track.index = index;
        });
        
        this.tracks = sortedTracks;
        return this.tracks;
    }

    shuffleArray(array) {
        for (let i = array.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [array[i], array[j]] = [array[j], array[i]];
        }
        return array;
    }

    getTrackById(id) {
        return this.tracks.find(track => track.id === id);
    }

    getTrackByIndex(index) {
        return this.tracks[index];
    }

    addTrack(trackData) {
        const newTrack = {
            id: `track_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            index: this.tracks.length,
            ...trackData,
            addedDate: new Date().toISOString()
        };
        
        this.tracks.push(newTrack);
        this.saveToLocalStorage();
        this.updateSearchIndex();
        
        return newTrack;
    }

    updateSearchIndex() {
        this.searchIndex = this.tracks.map(track => ({
            id: track.id,
            title: track.title.toLowerCase(),
            artist: track.artist.toLowerCase(),
            album: track.album.toLowerCase(),
            genre: track.genre.toLowerCase(),
            tags: track.tags ? track.tags.join(' ').toLowerCase() : ''
        }));
    }

    removeTrack(trackId) {
        const index = this.tracks.findIndex(t => t.id === trackId);
        if (index === -1) return false;
        
        this.tracks.splice(index, 1);
        
        // Обновление индексов оставшихся треков
        this.tracks.forEach((track, idx) => {
            track.index = idx;
        });
        
        this.saveToLocalStorage();
        this.updateSearchIndex();
        
        return true;
    }

    toggleFavorite(trackId) {
        if (this.favorites.has(trackId)) {
            this.favorites.delete(trackId);
        } else {
            this.favorites.add(trackId);
        }
        
        // Сохранение в localStorage
        localStorage.setItem('neovinyl_favorites', 
            JSON.stringify(Array.from(this.favorites)));
        
        return this.favorites.has(trackId);
    }

    isFavorite(trackId) {
        return this.favorites.has(trackId);
    }

    getFavorites() {
        return this.tracks.filter(track => this.favorites.has(track.id));
    }

    createPlaylist(name, trackIds = []) {
        const playlistId = `playlist_${Date.now()}`;
        const playlist = {
            id: playlistId,
            name,
            trackIds,
            created: new Date().toISOString(),
            modified: new Date().toISOString()
        };
        
        this.playlists.set(playlistId, playlist);
        this.savePlaylists();
        
        return playlist;
    }

    addToPlaylist(playlistId, trackId) {
        const playlist = this.playlists.get(playlistId);
        if (!playlist) return false;
        
        if (!playlist.trackIds.includes(trackId)) {
            playlist.trackIds.push(trackId);
            playlist.modified = new Date().toISOString();
            this.savePlaylists();
        }
        
        return true;
    }

    removeFromPlaylist(playlistId, trackId) {
        const playlist = this.playlists.get(playlistId);
        if (!playlist) return false;
        
        const index = playlist.trackIds.indexOf(trackId);
        if (index !== -1) {
            playlist.trackIds.splice(index, 1);
            playlist.modified = new Date().toISOString();
            this.savePlaylists();
        }
        
        return true;
    }

    getPlaylistTracks(playlistId) {
        const playlist = this.playlists.get(playlistId);
        if (!playlist) return [];
        
        return playlist.trackIds
            .map(id => this.getTrackById(id))
            .filter(track => track !== undefined);
    }

    savePlaylists() {
        const playlistsArray = Array.from(this.playlists.entries());
        localStorage.setItem('neovinyl_playlists', JSON.stringify(playlistsArray));
    }

    analyzeAudioFeatures() {
        // Анализ аудио-характеристик треков
        const features = {
            averageBPM: 0,
            genreDistribution: {},
            yearDistribution: {},
            totalDuration: 0,
            longestTrack: null,
            shortestTrack: null
        };
        
        if (this.tracks.length === 0) return features;
        
        // Расчет среднего BPM
        features.averageBPM = Math.round(
            this.tracks.reduce((sum, track) => sum + (track.bpm || 0), 0) / this.tracks.length
        );
        
        // Распределение по жанрам
        this.tracks.forEach(track => {
            const genre = track.genre || 'unknown';
            features.genreDistribution[genre] = (features.genreDistribution[genre] || 0) + 1;
        });
        
        // Распределение по годам
        this.tracks.forEach(track => {
            const year = track.year || 2024;
            features.yearDistribution[year] = (features.yearDistribution[year] || 0) + 1;
        });
        
        // Общая продолжительность
        features.totalDuration = this.tracks.reduce((sum, track) => 
            sum + (track.duration || 0), 0);
        
        // Самый длинный и короткий трек
        features.longestTrack = [...this.tracks].sort((a, b) => 
            (b.duration || 0) - (a.duration || 0))[0];
        features.shortestTrack = [...this.tracks].sort((a, b) => 
            (a.duration || 0) - (b.duration || 0))[0];
        
        return features;
    }

    generatePlaylistByMood(mood) {
        const moodPresets = {
            energetic: { minBPM: 120, maxBPM: 200, genres: ['electronic', 'rock'] },
            chill: { minBPM: 60, maxBPM: 100, genres: ['ambient', 'jazz'] },
            focus: { minBPM: 90, maxBPM: 130, genres: ['electronic', 'ambient'] },
            workout: { minBPM: 140, maxBPM: 200, genres: ['electronic', 'rock'] },
            sleep: { minBPM: 50, maxBPM: 80, genres: ['ambient'] }
        };
        
        const preset = moodPresets[mood] || moodPresets.chill;
        
        return this.tracks.filter(track => 
            track.bpm >= preset.minBPM && 
            track.bpm <= preset.maxBPM &&
            preset.genres.includes(track.genre)
        );
    }

    exportPlaylist(format = 'json') {
        const data = {
            name: 'NeoVinyl Playlist',
            version: '2.0',
            generated: new Date().toISOString(),
            trackCount: this.tracks.length,
            tracks: this.tracks.map(track => ({
                id: track.id,
                title: track.title,
                artist: track.artist,
                album: track.album,
                genre: track.genre,
                duration: track.duration,
                url: track.url
            }))
        };
        
        switch(format) {
            case 'json':
                return JSON.stringify(data, null, 2);
            case 'm3u':
                return this.generateM3U(data);
            case 'csv':
                return this.generateCSV(data);
            default:
                return JSON.stringify(data);
        }
    }

    generateM3U(data) {
        let m3u = '#EXTM3U\n';
        m3u += '#PLAYLIST:NeoVinyl Playlist\n';
        
        data.tracks.forEach(track => {
            m3u += `#EXTINF:${Math.round(track.duration)},${track.artist} - ${track.title}\n`;
            m3u += `${track.url}\n`;
        });
        
        return m3u;
    }

    generateCSV(data) {
        let csv = 'Title,Artist,Album,Genre,Duration,Year\n';
        
        data.tracks.forEach(track => {
            const durationFormatted = this.formatDuration(track.duration);
            csv += `"${track.title}","${track.artist}","${track.album}",`;
            csv += `"${track.genre}","${durationFormatted}",${track.year || '2025'}\n`;
        });
        
        return csv;
    }

    async importPlaylist(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            
            reader.onload = (e) => {
                try {
                    const content = e.target.result;
                    let importedTracks = [];
                    
                    // Определение формата по содержимому
                    if (file.name.endsWith('.json')) {
                        const data = JSON.parse(content);
                        importedTracks = data.tracks || [];
                    } else if (file.name.endsWith('.m3u') || file.name.endsWith('.m3u8')) {
                        importedTracks = this.parseM3U(content);
                    } else if (file.name.endsWith('.csv')) {
                        importedTracks = this.parseCSV(content);
                    }
                    
                    // Добавление треков
                    importedTracks.forEach(trackData => {
                        this.addTrack(trackData);
                    });
                    
                    resolve({
                        success: true,
                        count: importedTracks.length
                    });
                } catch (error) {
                    reject(new Error('Failed to parse playlist file'));
                }
            };
            
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsText(file);
        });
    }

    parseM3U(content) {
        const tracks = [];
        const lines = content.split('\n');
        let currentTrack = null;
        
        lines.forEach(line => {
            line = line.trim();
            
            if (line.startsWith('#EXTINF:')) {
                // Извлечение информации о треке
                const match = line.match(/#EXTINF:(\d+),(.+)/);
                if (match) {
                    currentTrack = {
                        duration: parseInt(match[1]),
                        title: match[2]
                    };
                }
            } else if (line && !line.startsWith('#')) {
                if (currentTrack) {
                    currentTrack.url = line;
                    tracks.push(currentTrack);
                    currentTrack = null;
                }
            }
        });
        
        return tracks;
    }

    parseCSV(content) {
        const tracks = [];
        const lines = content.split('\n');
        const headers = lines[0].split(',').map(h => h.replace(/"/g, '').trim());
        
        for (let i = 1; i < lines.length; i++) {
            if (!lines[i].trim()) continue;
            
            const values = lines[i].split(',').map(v => v.replace(/^"|"$/g, '').trim());
            const track = {};
            
            headers.forEach((header, index) => {
                track[header.toLowerCase()] = values[index];
            });
            
            // Преобразование продолжительности
            if (track.duration) {
                const [mins, secs] = track.duration.split(':').map(Number);
                track.duration = mins * 60 + secs;
            }
            
            tracks.push(track);
        }
        
        return tracks;
    }

    getStatistics() {
        const stats = {
            totalTracks: this.tracks.length,
            totalDuration: 0,
            genres: {},
            years: {},
            averageBPM: 0,
            fileSizes: {
                estimatedTotalMB: 0,
                averageBitrate: 0
            }
        };
        
        if (this.tracks.length === 0) return stats;
        
        // Расчет статистики
        let totalBPM = 0;
        let totalBitrate = 0;
        
        this.tracks.forEach(track => {
            // Продолжительность
            stats.totalDuration += track.duration || 0;
            
            // Жанры
            const genre = track.genre || 'Unknown';
            stats.genres[genre] = (stats.genres[genre] || 0) + 1;
            
            // Годы
            const year = track.year || 2024;
            stats.years[year] = (stats.years[year] || 0) + 1;
            
            // BPM
            totalBPM += track.bpm || 0;
            
            // Bitrate
            totalBitrate += track.metadata?.bitrate || 320;
            
            // Размер файла (приблизительно)
            if (track.duration && track.metadata?.bitrate) {
                const sizeMB = (track.duration * track.metadata.bitrate * 1000) / (8 * 1024 * 1024);
                stats.fileSizes.estimatedTotalMB += sizeMB;
            }
        });
        
        stats.averageBPM = Math.round(totalBPM / this.tracks.length);
        stats.fileSizes.averageBitrate = Math.round(totalBitrate / this.tracks.length);
        
        // Форматирование продолжительности
        const totalHours = Math.floor(stats.totalDuration / 3600);
        const totalMinutes = Math.floor((stats.totalDuration % 3600) / 60);
        stats.totalDurationFormatted = `${totalHours}h ${totalMinutes}m`;
        
        return stats;
    }
}

// Глобальный доступ к менеджеру треков
window.trackManager = new TrackManager();

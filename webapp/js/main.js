import { initializeAudioEngine } from './audio-engine.js';
import { initializeVisualizer } from './visualizer.js';
import { UIManager } from './ui-manager.js';
import { TrackManager } from './track-manager.js';

class NeoVinylPlayer {
    constructor() {
        this.state = {
            isPlaying: false,
            currentTrack: null,
            volume: 0.7,
            bass: 0.5,
            treble: 0.5,
            repeat: false,
            shuffle: false,
            spatialAudio: false
        };
        
        this.audioEngine = null;
        this.visualizer = null;
        this.uiManager = null;
        this.trackManager = null;
        
        this.init();
    }
    
    async init() {
        try {
            // Инициализация менеджеров
            this.trackManager = new TrackManager();
            this.uiManager = new UIManager(this);
            this.audioEngine = await initializeAudioEngine();
            this.visualizer = await initializeVisualizer();
            
            // Загрузка треков
            await this.trackManager.loadTracks();
            this.uiManager.updatePlaylist(this.trackManager.tracks);
            
            // Установка начального трека
            if (this.trackManager.tracks.length > 0) {
                await this.loadTrack(this.trackManager.tracks[0]);
            }
            
            this.bindEvents();
            this.startVisualization();
            
            console.log('NeoVinyl Player initialized successfully');
        } catch (error) {
            console.error('Failed to initialize player:', error);
        }
    }
    
    async loadTrack(track) {
        try {
            this.state.currentTrack = track;
            await this.audioEngine.loadTrack(track);
            this.uiManager.updateTrackInfo(track);
            
            if (this.state.isPlaying) {
                await this.audioEngine.play();
            }
        } catch (error) {
            console.error('Error loading track:', error);
        }
    }
    
    async playPause() {
        try {
            if (this.state.isPlaying) {
                await this.audioEngine.pause();
            } else {
                await this.audioEngine.play();
            }
            this.state.isPlaying = !this.state.isPlaying;
            this.uiManager.updatePlayButton(this.state.isPlaying);
        } catch (error) {
            console.error('Play/Pause error:', error);
        }
    }
    
    async nextTrack() {
        const nextTrack = this.trackManager.getNextTrack(
            this.state.currentTrack,
            this.state.shuffle
        );
        
        if (nextTrack) {
            await this.loadTrack(nextTrack);
            if (this.state.isPlaying) {
                await this.audioEngine.play();
            }
        }
    }
    
    async prevTrack() {
        const prevTrack = this.trackManager.getPrevTrack(
            this.state.currentTrack
        );
        
        if (prevTrack) {
            await this.loadTrack(prevTrack);
            if (this.state.isPlaying) {
                await this.audioEngine.play();
            }
        }
    }
    
    setVolume(value) {
        this.state.volume = value;
        this.audioEngine.setVolume(value);
        this.uiManager.updateVolumeDisplay(value);
    }
    
    setBass(value) {
        this.state.bass = value;
        this.audioEngine.setBass(value);
    }
    
    setTreble(value) {
        this.state.treble = value;
        this.audioEngine.setTreble(value);
    }
    
    toggleShuffle() {
        this.state.shuffle = !this.state.shuffle;
        this.uiManager.updateShuffleButton(this.state.shuffle);
    }
    
    toggleRepeat() {
        this.state.repeat = !this.state.repeat;
        this.uiManager.updateRepeatButton(this.state.repeat);
    }
    
    bindEvents() {
        document.getElementById('btn-play').addEventListener('click', 
            () => this.playPause());
        
        document.getElementById('btn-next').addEventListener('click', 
            () => this.nextTrack());
        
        document.getElementById('btn-prev').addEventListener('click', 
            () => this.prevTrack());
        
        document.getElementById('btn-shuffle').addEventListener('click', 
            () => this.toggleShuffle());
        
        document.getElementById('btn-repeat').addEventListener('click', 
            () => this.toggleRepeat());
        
        document.getElementById('volume-knob').addEventListener('input', 
            (e) => this.setVolume(e.target.value / 100));
        
        document.getElementById('bass-knob').addEventListener('input', 
            (e) => this.setBass(e.target.value / 100));
        
        document.getElementById('treble-knob').addEventListener('input', 
            (e) => this.setTreble(e.target.value / 100));
    }
    
    startVisualization() {
        this.visualizer.start(this.audioEngine.getAnalyserNode());
    }
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    const player = new NeoVinylPlayer();
    
    // Экспорт для глобального доступа (если нужно)
    window.NeoVinyl = player;
});
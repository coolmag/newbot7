import Tone from 'tone';

class AudioEngine {
    constructor() {
        this.audioContext = null;
        this.audioElement = null;
        this.audioSource = null;
        this.analyser = null;
        this.eqNodes = [];
        this.isInitialized = false;
        
        this.init();
    }
    
    async init() {
        try {
            // Создание аудио контекста с обработкой ошибок
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                latencyHint: 'interactive',
                sampleRate: 48000
            });
            
            this.audioElement = document.getElementById('audio-engine');
            
            // Создание узла анализатора для визуализации
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 2048;
            this.analyser.smoothingTimeConstant = 0.8;
            
            // Создание эквалайзера (10 полос)
            this.createEqualizer();
            
            // Подключение цепочки обработки
            this.connectNodes();
            
            // Разблокировка аудио контекста (требуется для мобильных устройств)
            await this.unlockAudio();
            
            this.isInitialized = true;
            console.log('Audio Engine initialized with sample rate:', this.audioContext.sampleRate);
        } catch (error) {
            console.error('Audio Engine initialization failed:', error);
        }
    }
    
    createEqualizer() {
        const frequencies = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000];
        
        frequencies.forEach((freq, index) => {
            const eqNode = this.audioContext.createBiquadFilter();
            eqNode.type = 'peaking';
            eqNode.frequency.value = freq;
            eqNode.Q.value = 1;
            eqNode.gain.value = 0;
            
            this.eqNodes.push(eqNode);
        });
    }
    
    connectNodes() {
        this.audioSource = this.audioContext.createMediaElementSource(this.audioElement);
        
        // Подключение цепочки: источник -> эквалайзер -> анализатор -> выход
        let currentNode = this.audioSource;
        
        this.eqNodes.forEach(eqNode => {
            currentNode.connect(eqNode);
            currentNode = eqNode;
        });
        
        currentNode.connect(this.analyser);
        this.analyser.connect(this.audioContext.destination);
    }
    
    async unlockAudio() {
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
        
        // Запуск с silent source для разблокировки на iOS
        const buffer = this.audioContext.createBuffer(1, 1, 22050);
        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(this.audioContext.destination);
        source.start(0);
        source.stop(0.01);
    }
    
    async loadTrack(track) {
        if (!this.isInitialized) {
            await this.init();
        }
        
        this.audioElement.src = track.url;
        this.audioElement.load();
        
        // Обновление метаданных трека
        if (track.metadata) {
            this.audioElement.dataset.title = track.metadata.title;
            this.audioElement.dataset.artist = track.metadata.artist;
            this.audioElement.dataset.album = track.metadata.album;
        }
        
        return new Promise((resolve, reject) => {
            this.audioElement.oncanplaythrough = () => {
                resolve();
            };
            
            this.audioElement.onerror = (error) => {
                reject(new Error(`Failed to load track: ${error.message}`));
            };
        });
    }
    
    async play() {
        if (!this.isInitialized) {
            await this.init();
        }
        
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
        
        try {
            await this.audioElement.play();
        } catch (error) {
            console.error('Playback failed:', error);
            throw error;
        }
    }
    
    pause() {
        this.audioElement.pause();
    }
    
    setVolume(value) {
        this.audioElement.volume = value;
    }
    
    setBass(value) {
        // Усиление низких частот
        const bassNode = this.eqNodes[0]; // 60Hz
        const lowMidNode = this.eqNodes[1]; // 170Hz
        
        bassNode.gain.value = (value - 0.5) * 24;
        lowMidNode.gain.value = (value - 0.5) * 12;
    }
    
    setTreble(value) {
        // Усиление высоких частот
        const highNode = this.eqNodes[8]; // 14kHz
        const airNode = this.eqNodes[9]; // 16kHz
        
        highNode.gain.value = (value - 0.5) * 24;
        airNode.gain.value = (value - 0.5) * 12;
    }
    
    setEQBand(bandIndex, value) {
        if (this.eqNodes[bandIndex]) {
            this.eqNodes[bandIndex].gain.value = (value - 0.5) * 30;
        }
    }
    
    enableSpatialAudio(enable) {
        // Пространственный звук (Web Audio API PannerNode)
        if (enable) {
            const panner = this.audioContext.createPanner();
            panner.panningModel = 'HRTF';
            panner.distanceModel = 'inverse';
            panner.refDistance = 1;
            panner.maxDistance = 10000;
            panner.rolloffFactor = 1;
            panner.coneInnerAngle = 360;
            panner.coneOuterAngle = 0;
            panner.coneOuterGain = 0;
            
            // Подключение панорамы в цепочку
            this.audioSource.disconnect();
            this.audioSource.connect(panner);
            panner.connect(this.eqNodes[0]);
        }
    }
    
    getAnalyserNode() {
        return this.analyser;
    }
    
    getCurrentTime() {
        return this.audioElement.currentTime;
    }
    
    getDuration() {
        return this.audioElement.duration;
    }
    
    seekTo(time) {
        this.audioElement.currentTime = time;
    }
}

export async function initializeAudioEngine() {
    const engine = new AudioEngine();
    await engine.init();
    return engine;
}
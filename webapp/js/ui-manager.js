export class UIManager {
    constructor(player) {
        this.player = player;
        this.elements = this.cacheElements();
        this.animations = new Map();
        this.initUI();
    }

    cacheElements() {
        return {
            // Плейлист
            playlist: document.getElementById('playlist-tracks'),
            trackCount: document.getElementById('track-count'),
            
            // Информация о треке
            trackTitle: document.getElementById('current-track'),
            trackArtist: document.getElementById('current-artist'),
            trackAlbum: document.getElementById('current-album'),
            
            // Время и прогресс
            timeCurrent: document.getElementById('time-current'),
            timeTotal: document.getElementById('time-total'),
            progressFill: document.getElementById('progress-fill'),
            progressHandle: document.getElementById('progress-handle'),
            
            // Кнопки управления
            playButton: document.getElementById('btn-play'),
            shuffleButton: document.getElementById('btn-shuffle'),
            repeatButton: document.getElementById('btn-repeat'),
            
            // Элементы эквалайзера
            eqSliders: document.getElementById('eq-sliders'),
            
            // Системная информация
            bitrate: document.getElementById('bitrate-value'),
            sampleRate: document.getElementById('sample-rate'),
            bufferState: document.getElementById('buffer-state'),
            
            // Кнопки тем и эффектов
            themeButton: document.getElementById('btn-theme'),
            visualizerButton: document.getElementById('btn-visualizer'),
            effectsButton: document.getElementById('btn-effects'),
            
            // Модальные окна
            genreModal: document.getElementById('genre-modal'),
            closeGenre: document.getElementById('close-genre'),
            
            // Винтажные элементы
            vinylDisc: document.querySelector('.vinyl-disc'),
            tonearm: document.querySelector('.tonearm'),
            
            // VU-метры
            vuLeft: document.querySelector('.vu-meter.left .vu-needle'),
            vuRight: document.querySelector('.vu-meter.right .vu-needle'),
            
            // Кнопки эквалайзера
            eqBands: document.querySelectorAll('.eq-band')
        };
    }

    initUI() {
        this.setupEventListeners();
        this.generateEQSliders();
        this.setupKnobs();
        this.setupProgressBar();
        this.setupThemeToggle();
        this.initializeHolograms();
    }

    setupEventListeners() {
        // Управление прогрессом
        const progressTrack = document.querySelector('.progress-track');
        progressTrack.addEventListener('click', (e) => this.handleProgressClick(e));
        
        // Перетаскивание прогресса
        this.elements.progressHandle.addEventListener('mousedown', (e) => this.startDragProgress(e));
        
        // Закрытие модальных окон
        this.elements.closeGenre?.addEventListener('click', () => this.closeModal('genre-modal'));
        
        // Эффекты наведения
        document.querySelectorAll('.control-btn').forEach(btn => {
            btn.addEventListener('mouseenter', () => this.createHoverEffect(btn));
            btn.addEventListener('mouseleave', () => this.removeHoverEffect(btn));
        });
        
        // Анимация кнопок
        this.elements.playButton.addEventListener('click', () => this.animatePlayButton());
    }

    updateTrackInfo(track) {
        if (!track) return;
        
        // Основная информация
        this.elements.trackTitle.textContent = track.title || 'UNKNOWN TRACK';
        this.elements.trackTitle.dataset.text = track.title || 'UNKNOWN TRACK';
        this.elements.trackArtist.textContent = track.artist || 'UNKNOWN ARTIST';
        this.elements.trackAlbum.textContent = track.album || 'UNKNOWN ALBUM';
        
        // Обновление глитч-эффекта
        this.applyGlitchEffect(this.elements.trackTitle);
        
        // Обновление времени
        if (track.duration) {
            this.elements.timeTotal.textContent = this.formatTime(track.duration);
        }
        
        // Обновление виниловой пластинки
        this.updateVinylAppearance(track);
        
        // Обновление плейлиста
        this.highlightCurrentTrack(track.id);
    }

    updatePlaylist(tracks) {
        if (!this.elements.playlist) return;
        
        this.elements.playlist.innerHTML = '';
        this.elements.trackCount.textContent = tracks.length;
        
        tracks.forEach(track => {
            const trackElement = this.createTrackElement(track);
            this.elements.playlist.appendChild(trackElement);
        });
    }

    createTrackElement(track) {
        const div = document.createElement('div');
        div.className = 'playlist-item';
        div.dataset.trackId = track.id;
        
        div.innerHTML = `
            <div class="track-index">${String(track.index + 1).padStart(2, '0')}</div>
            <div class="track-info">
                <div class="track-title">${track.title}</div>
                <div class="track-meta">${track.artist} • ${track.durationFormatted || '3:45'}</div>
            </div>
            <div class="track-status">
                <div class="status-indicator"></div>
            </div>
        `;
        
        div.addEventListener('click', () => this.player.loadTrack(track));
        div.addEventListener('dblclick', () => {
            this.player.loadTrack(track);
            this.player.playPause();
        });
        
        return div;
    }

    highlightCurrentTrack(trackId) {
        document.querySelectorAll('.playlist-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.trackId === trackId) {
                item.classList.add('active');
                
                // Прокрутка к активному треку
                item.scrollIntoView({
                    behavior: 'smooth',
                    block: 'center'
                });
            }
        });
    }

    updatePlayButton(isPlaying) {
        const playBtn = this.elements.playButton;
        const vinyl = this.elements.vinylDisc;
        const tonearm = this.elements.tonearm;
        
        if (isPlaying) {
            playBtn.classList.add('playing');
            vinyl?.classList.add('playing');
            tonearm?.classList.add('playing');
            
            // Анимация кнопки
            this.animateElement(playBtn, 'pulse', 0.6);
        } else {
            playBtn.classList.remove('playing');
            vinyl?.classList.remove('playing');
            tonearm?.classList.remove('playing');
            
            this.stopAnimation(playBtn, 'pulse');
        }
    }

    updateVolumeDisplay(value) {
        const volumeKnob = document.getElementById('volume-knob');
        if (volumeKnob) {
            const degrees = value * 270 - 135;
            volumeKnob.style.transform = `rotate(${degrees}deg)`;
            volumeKnob.dataset.value = Math.round(value * 100);
            
            // Обновление неонового свечения
            this.updateKnobGlow(volumeKnob, value);
        }
    }

    updateShuffleButton(isActive) {
        this.elements.shuffleButton.classList.toggle('active', isActive);
        if (isActive) {
            this.animateElement(this.elements.shuffleButton, 'spin', 2);
        } else {
            this.stopAnimation(this.elements.shuffleButton, 'spin');
        }
    }

    updateRepeatButton(isActive) {
        this.elements.repeatButton.classList.toggle('active', isActive);
        if (isActive) {
            this.animateElement(this.elements.repeatButton, 'pulse', 1);
        } else {
            this.stopAnimation(this.elements.repeatButton, 'pulse');
        }
    }

    updateProgress(currentTime, duration) {
        if (!duration) return;
        
        const progress = (currentTime / duration) * 100;
        this.elements.progressFill.style.width = `${progress}%`;
        this.elements.progressHandle.style.left = `${progress}%`;
        
        // Обновление времени
        this.elements.timeCurrent.textContent = this.formatTime(currentTime);
        
        // Обновление VU-метров (симуляция)
        this.updateVUMeters();
    }

    updateVUMeters() {
        if (!this.elements.vuLeft || !this.elements.vuRight) return;
        
        // Имитация аналоговых показаний
        const leftValue = Math.random() * 80 + 20;
        const rightValue = Math.random() * 80 + 20;
        
        this.elements.vuLeft.style.height = `${leftValue}%`;
        this.elements.vuRight.style.height = `${rightValue}%`;
        
        // Добавление дрожания для реалистичности
        this.animateVUMeter(this.elements.vuLeft, leftValue);
        this.animateVUMeter(this.elements.vuRight, rightValue);
    }

    animateVUMeter(meter, value) {
        const jitter = (Math.random() - 0.5) * 5;
        const newHeight = Math.max(20, Math.min(100, value + jitter));
        
        meter.style.transition = 'height 0.1s cubic-bezier(0.4, 0, 0.2, 1)';
        meter.style.height = `${newHeight}%`;
    }

    generateEQSliders() {
        if (!this.elements.eqSliders) return;
        
        const frequencies = [
            { label: '60Hz', type: 'low' },
            { label: '170Hz', type: 'low' },
            { label: '310Hz', type: 'mid' },
            { label: '600Hz', type: 'mid' },
            { label: '1kHz', type: 'mid' },
            { label: '3kHz', type: 'high' },
            { label: '6kHz', type: 'high' },
            { label: '12kHz', type: 'high' },
            { label: '14kHz', type: 'air' },
            { label: '16kHz', type: 'air' }
        ];
        
        this.elements.eqSliders.innerHTML = frequencies.map((freq, index) => `
            <div class="eq-band" data-band="${index}">
                <div class="eq-label">${freq.label}</div>
                <div class="eq-slider-container">
                    <input type="range" 
                           class="eq-slider ${freq.type}" 
                           min="-30" 
                           max="30" 
                           value="0"
                           orient="vertical">
                    <div class="eq-value">0dB</div>
                </div>
            </div>
        `).join('');
        
        // Настройка обработчиков для слайдеров
        this.setupEQSliders();
    }

    setupEQSliders() {
        document.querySelectorAll('.eq-slider').forEach((slider, index) => {
            slider.addEventListener('input', (e) => {
                const value = parseInt(e.target.value);
                const valueDisplay = e.target.parentElement.querySelector('.eq-value');
                valueDisplay.textContent = `${value > 0 ? '+' : ''}${value}dB`;
                
                // Обновление эквалайзера в аудиодвижке
                if (this.player.audioEngine) {
                    const normalizedValue = (value + 30) / 60;
                    this.player.audioEngine.setEQBand(index, normalizedValue);
                }
                
                // Визуальный эффект
                this.createEQEffect(e.target, value);
            });
        });
    }

    setupKnobs() {
        const knobs = document.querySelectorAll('.knob');
        knobs.forEach(knob => {
            knob.addEventListener('mousedown', (e) => this.startKnobDrag(e, knob));
        });
    }

    startKnobDrag(e, knob) {
        e.preventDefault();
        const startY = e.clientY;
        const startValue = parseInt(knob.dataset.value) || 50;
        const maxRotation = 135;
        
        const onMouseMove = (moveEvent) => {
            const deltaY = startY - moveEvent.clientY;
            const sensitivity = 0.5;
            let newValue = Math.max(0, Math.min(100, startValue + deltaY * sensitivity));
            
            knob.dataset.value = Math.round(newValue);
            
            const rotation = (newValue / 100) * 270 - 135;
            knob.style.transform = `rotate(${rotation}deg)`;
            
            this.updateKnobGlow(knob, newValue / 100);
            
            // Обновление соответствующего параметра
            this.handleKnobUpdate(knob.id, newValue / 100);
        };
        
        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }

    handleKnobUpdate(knobId, value) {
        switch(knobId) {
            case 'volume-knob':
                this.player.setVolume(value);
                break;
            case 'bass-knob':
                this.player.setBass(value);
                break;
            case 'treble-knob':
                this.player.setTreble(value);
                break;
        }
    }

    updateKnobGlow(knob, value) {
        const glow = knob.querySelector('.knob-glow');
        if (!glow) return;
        
        const intensity = Math.abs(value - 0.5) * 2;
        glow.style.opacity = intensity;
        
        if (value > 0.5) {
            glow.style.background = `radial-gradient(circle at 30% 30%, 
                rgba(0, 243, 255, ${intensity * 0.5}), 
                transparent 70%)`;
        } else {
            glow.style.background = `radial-gradient(circle at 30% 30%, 
                rgba(255, 0, 255, ${intensity * 0.5}), 
                transparent 70%)`;
        }
    }

    setupProgressBar() {
        const progressTrack = document.querySelector('.progress-track');
        if (!progressTrack) return;
        
        progressTrack.addEventListener('click', (e) => {
            const rect = progressTrack.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const percentage = x / rect.width;
            
            if (this.player.audioEngine) {
                const duration = this.player.audioEngine.getDuration();
                if (duration) {
                    this.player.audioEngine.seekTo(duration * percentage);
                }
            }
        });
    }

    startDragProgress(e) {
        e.preventDefault();
        const progressTrack = document.querySelector('.progress-track');
        const handle = this.elements.progressHandle;
        
        const onMouseMove = (moveEvent) => {
            const rect = progressTrack.getBoundingClientRect();
            let x = moveEvent.clientX - rect.left;
            x = Math.max(0, Math.min(rect.width, x));
            
            const percentage = x / rect.width;
            handle.style.left = `${percentage * 100}%`;
            this.elements.progressFill.style.width = `${percentage * 100}%`;
            
            // Обновление времени
            if (this.player.audioEngine) {
                const duration = this.player.audioEngine.getDuration();
                if (duration) {
                    const currentTime = duration * percentage;
                    this.elements.timeCurrent.textContent = this.formatTime(currentTime);
                }
            }
        };
        
        const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            
            // Применение изменения позиции
            if (this.player.audioEngine) {
                const rect = progressTrack.getBoundingClientRect();
                const x = parseFloat(handle.style.left) / 100 * rect.width;
                const percentage = x / rect.width;
                const duration = this.player.audioEngine.getDuration();
                
                if (duration) {
                    this.player.audioEngine.seekTo(duration * percentage);
                }
            }
        };
        
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    }

    handleProgressClick(e) {
        const progressTrack = document.querySelector('.progress-track');
        const rect = progressTrack.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const percentage = x / rect.width;
        
        this.elements.progressHandle.style.left = `${percentage * 100}%`;
        this.elements.progressFill.style.width = `${percentage * 100}%`;
        
        if (this.player.audioEngine) {
            const duration = this.player.audioEngine.getDuration();
            if (duration) {
                this.player.audioEngine.seekTo(duration * percentage);
            }
        }
    }

    setupThemeToggle() {
        this.elements.themeButton.addEventListener('click', () => {
            const currentTheme = document.documentElement.dataset.theme;
            const newTheme = currentTheme === 'cyberpunk' ? 'vintage' : 'cyberpunk';
            
            document.documentElement.dataset.theme = newTheme;
            this.applyTheme(newTheme);
            
            // Анимация перехода
            this.animateThemeTransition(newTheme);
        });
    }

    applyTheme(theme) {
        const root = document.documentElement;
        
        if (theme === 'vintage') {
            root.style.setProperty('--neon-primary', '#cc9900');
            root.style.setProperty('--neon-secondary', '#996600');
            root.style.setProperty('--neon-accent', '#ffcc66');
            root.style.setProperty('--cyber-dark', '#1a0f0a');
            root.style.setProperty('--cyber-darker', '#0a0500');
            
            // Изменение текстур и фонов
            document.querySelector('.cyber-grid').style.display = 'none';
        } else {
            root.style.setProperty('--neon-primary', '#00f3ff');
            root.style.setProperty('--neon-secondary', '#ff00ff');
            root.style.setProperty('--neon-accent', '#ffcc00');
            root.style.setProperty('--cyber-dark', '#0a0a1a');
            root.style.setProperty('--cyber-darker', '#050510');
            
            document.querySelector('.cyber-grid').style.display = 'block';
        }
    }

    animateThemeTransition(theme) {
        const container = document.querySelector('.player-container');
        container.style.animation = 'none';
        
        setTimeout(() => {
            container.style.animation = 'themeTransition 1s ease';
            setTimeout(() => {
                container.style.animation = '';
            }, 1000);
        }, 10);
    }

    initializeHolograms() {
        // Создание голографических эффектов для элементов
        document.querySelectorAll('.hologram-element').forEach(element => {
            this.createHologramEffect(element);
        });
    }

    createHologramEffect(element) {
        const hologram = document.createElement('div');
        hologram.className = 'hologram-overlay';
        hologram.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(45deg, 
                transparent 0%, 
                rgba(0, 243, 255, 0.1) 50%, 
                transparent 100%);
            pointer-events: none;
            animation: hologramScan 3s linear infinite;
            z-index: 1;
        `;
        
        element.style.position = 'relative';
        element.appendChild(hologram);
    }

    applyGlitchEffect(element) {
        element.classList.remove('glitch');
        
        setTimeout(() => {
            element.classList.add('glitch');
            
            // Случайная интенсивность глитча
            const intensity = Math.random() * 30 + 20;
            element.style.setProperty('--glitch-intensity', `${intensity}px`);
            
            setTimeout(() => {
                element.classList.remove('glitch');
            }, 500);
        }, 10);
    }

    updateVinylAppearance(track) {
        const vinyl = this.elements.vinylDisc;
        if (!vinyl) return;
        
        // Изменение цвета этикетки в зависимости от жанра
        const genreColors = {
            electronic: '#ff0000',
            rock: '#ff6600',
            jazz: '#00ff00',
            classical: '#0066ff',
            hiphop: '#ff00ff',
            default: '#cc0000'
        };
        
        const label = vinyl.querySelector('.vinyl-label');
        if (label && track.genre) {
            const color = genreColors[track.genre.toLowerCase()] || genreColors.default;
            label.style.background = `linear-gradient(45deg, ${color}, ${this.darkenColor(color, 0.3)})`;
        }
        
        // Скорость вращения в зависимости от темпа
        if (track.bpm) {
            const rotationSpeed = 20 + (140 - Math.min(track.bpm, 140)) * 0.5;
            vinyl.style.animationDuration = `${rotationSpeed}s`;
        }
    }

    darkenColor(color, factor) {
        const hex = color.replace('#', '');
        const r = parseInt(hex.substr(0, 2), 16);
        const g = parseInt(hex.substr(2, 2), 16);
        const b = parseInt(hex.substr(4, 2), 16);
        
        return `rgb(${Math.floor(r * factor)}, ${Math.floor(g * factor)}, ${Math.floor(b * factor)})`;
    }

    formatTime(seconds) {
        if (!seconds || isNaN(seconds)) return '0:00';
        
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    createHoverEffect(element) {
        element.classList.add('hover-effect');
        
        // Создание частиц при наведении
        if (element.classList.contains('control-btn')) {
            this.createParticles(element);
        }
    }

    removeHoverEffect(element) {
        element.classList.remove('hover-effect');
    }

    createParticles(element) {
        const rect = element.getBoundingClientRect();
        const particleCount = 8;
        
        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.cssText = `
                position: fixed;
                width: 4px;
                height: 4px;
                background: var(--neon-primary);
                border-radius: 50%;
                pointer-events: none;
                z-index: 1000;
                left: ${rect.left + rect.width / 2}px;
                top: ${rect.top + rect.height / 2}px;
            `;
            
            document.body.appendChild(particle);
            
            const angle = (i / particleCount) * Math.PI * 2;
            const distance = 30 + Math.random() * 30;
            
            const animation = particle.animate([
                {
                    transform: `translate(0, 0) scale(1)`,
                    opacity: 1
                },
                {
                    transform: `translate(${Math.cos(angle) * distance}px, ${Math.sin(angle) * distance}px) scale(0)`,
                    opacity: 0
                }
            ], {
                duration: 600,
                easing: 'cubic-bezier(0.4, 0, 0.2, 1)'
            });
            
            animation.onfinish = () => particle.remove();
        }
    }

    animatePlayButton() {
        const playBtn = this.elements.playButton;
        const ripple = document.createElement('div');
        ripple.className = 'ripple-effect';
        
        playBtn.appendChild(ripple);
        
        setTimeout(() => {
            ripple.remove();
        }, 1000);
    }

    createEQEffect(slider, value) {
        const eqBand = slider.closest('.eq-band');
        const intensity = Math.abs(value) / 30;
        
        eqBand.style.setProperty('--eq-intensity', intensity);
        eqBand.classList.add('eq-active');
        
        setTimeout(() => {
            eqBand.classList.remove('eq-active');
        }, 300);
    }

    animateElement(element, animation, duration) {
        const key = `${element.id || element.className}_${animation}`;
        
        if (this.animations.has(key)) {
            this.stopAnimation(element, animation);
        }
        
        element.style.animation = `${animation} ${duration}s infinite`;
        this.animations.set(key, { element, animation });
    }

    stopAnimation(element, animation) {
        const key = `${element.id || element.className}_${animation}`;
        
        if (this.animations.has(key)) {
            element.style.animation = '';
            this.animations.delete(key);
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('active');
        }
    }

    updateSystemInfo(info) {
        if (info.bitrate) {
            this.elements.bitrate.textContent = `${info.bitrate} kbps`;
        }
        
        if (info.sampleRate) {
            this.elements.sampleRate.textContent = `${info.sampleRate} kHz`;
        }
        
        if (info.buffer) {
            this.elements.bufferState.textContent = info.buffer;
            this.elements.bufferState.className = `buffer-${info.buffer.toLowerCase()}`;
        }
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `cyber-notification ${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">${type === 'info' ? 'ℹ' : '⚠'}</span>
                <span class="notification-text">${message}</span>
            </div>
        `;
        
        document.body.appendChild(notification);
        
        // Анимация появления
        notification.animate([
            { transform: 'translateX(100%)', opacity: 0 },
            { transform: 'translateX(0)', opacity: 1 }
        ], {
            duration: 300,
            easing: 'ease-out'
        });
        
        // Автоматическое удаление
        setTimeout(() => {
            notification.animate([
                { transform: 'translateX(0)', opacity: 1 },
                { transform: 'translateX(100%)', opacity: 0 }
            ], {
                duration: 300,
                easing: 'ease-in'
            }).onfinish = () => notification.remove();
        }, 3000);
    }
}

// Добавление CSS анимаций в документ
const style = document.createElement('style');
style.textContent = `
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    @keyframes hologramScan {
        0% { transform: translateY(-100%); }
        100% { transform: translateY(100%); }
    }
    
    @keyframes themeTransition {
        0% { filter: hue-rotate(0deg) brightness(1); }
        50% { filter: hue-rotate(180deg) brightness(0.8); }
        100% { filter: hue-rotate(0deg) brightness(1); }
    }
    
    .ripple-effect {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 100%;
        height: 100%;
        border-radius: 50%;
        background: radial-gradient(circle, 
            rgba(0, 243, 255, 0.3) 0%, 
            transparent 70%);
        animation: ripple 1s ease-out;
        pointer-events: none;
    }
    
    @keyframes ripple {
        0% { transform: translate(-50%, -50%) scale(0); opacity: 1; }
        100% { transform: translate(-50%, -50%) scale(2); opacity: 0; }
    }
    
    .eq-active {
        animation: eqPulse 0.3s ease;
    }
    
    @keyframes eqPulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    .playlist-item.active {
        background: rgba(0, 243, 255, 0.1);
        border-left: 2px solid var(--neon-primary);
    }
    
    .playlist-item.active .status-indicator {
        background: var(--neon-primary);
        box-shadow: var(--glow-primary);
        animation: pulse 2s infinite;
    }
    
    .buffer-stable { color: #00ff00; }
    .buffer-warning { color: #ffff00; }
    .buffer-critical { color: #ff0000; }
    
    .cyber-notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: var(--cyber-surface);
        border: 1px solid var(--neon-primary);
        padding: 12px 20px;
        border-radius: 8px;
        backdrop-filter: blur(10px);
        box-shadow: var(--glow-primary);
        z-index: 10000;
        max-width: 300px;
    }
`;
document.head.appendChild(style);

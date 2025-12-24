// js/visualizer.js
import * as elements from './elements.js';

class VinylVisualizer {
    constructor() {
        this.audioCtx = null;
        this.analyser = null;
        this.source = null;
        this.dataArray = null;
        this.isInitialized = false;
        this.animationFrameId = null;
    }

    /**
     * Initializes the Web Audio API components.
     * This must be called after a user gesture (e.g., a click).
     */
    init() {
        if (this.isInitialized || !elements.audio) return;
        try {
            console.log('[Visualizer] Initializing AudioContext and Analyser...');
            this.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioCtx.createAnalyser();
            
            // Configuration for a smooth, bass-focused visualization
            this.analyser.fftSize = 256;
            this.analyser.smoothingTimeConstant = 0.7;

            this.source = this.audioCtx.createMediaElementSource(elements.audio);
            this.source.connect(this.analyser);
            this.analyser.connect(this.audioCtx.destination);
            
            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            this.isInitialized = true;
            console.log('[Visualizer] Initialization complete.');
            
            this.start();
        } catch (e) {
            console.error('Audio visualizer initialization failed:', e);
        }
    }

    /**
     * Starts the animation loop.
     */
    start() {
        if (!this.isInitialized || this.animationFrameId) return;
        this.update();
    }

    /**
     * Stops the animation loop.
     */
    stop() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    /**
     * The core animation loop, run with requestAnimationFrame.
     */
    update() {
        this.animationFrameId = requestAnimationFrame(() => this.update());
        
        if (!elements.vinylGlow) return;
        
        this.analyser.getByteFrequencyData(this.dataArray);
        
        // --- Calculate Bass ---
        // Get the average of the first few frequency bins (bass frequencies)
        const bassFrequencies = this.dataArray.slice(0, 4);
        const averageBass = bassFrequencies.reduce((sum, value) => sum + value, 0) / bassFrequencies.length;
        
        // Normalize the value to a 0-1 range
        const normalizedBass = averageBass / 255;
        
        // --- Apply Visuals ---
        // We control the glow effect using CSS Custom Properties for performance.
        const glowOpacity = 0.2 + (normalizedBass * 0.8); // from 0.2 to 1.0
        const glowScale = 1.0 + (normalizedBass * 0.1);   // from 1.0 to 1.1

        elements.vinylGlow.style.setProperty('--glow-opacity', glowOpacity);
        elements.vinylGlow.style.setProperty('--glow-scale', glowScale);
    }
    
    /**
     * Toggles the playing state of the visual elements.
     * @param {boolean} isPlaying - True if music is starting, false if stopping.
     */
    setPlaying(isPlaying) {
        if (!elements.vinylRecord || !elements.tonearm || !elements.vinylGlow) return;
        
        if (isPlaying) {
            // Resume AudioContext if it was suspended
            if (this.isInitialized && this.audioCtx.state === 'suspended') {
                this.audioCtx.resume();
            }
            elements.vinylRecord.classList.add('playing');
            elements.tonearm.classList.add('playing');
            elements.vinylGlow.classList.add('active');
            this.start();
        } else {
            elements.vinylRecord.classList.remove('playing');
            elements.tonearm.classList.remove('playing');
            elements.vinylGlow.classList.remove('active');
            // We can stop the animation loop to save resources when paused
            this.stop(); 
        }
    }
}

// Export a single instance of the visualizer
export const visualizer = new VinylVisualizer();

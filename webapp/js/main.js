// js/main.js
import { initializeEventListeners } from './events.js';
import { visualizer } from './visualizer.js';
import * as elements from './elements.js';

function initializeApp() {
    console.log('[Main] DOM content loaded and WebApp is ready. Initializing app...');
    
    // Expand the Web App to full height.
    window.Telegram.WebApp.expand();

    // Set up all the button clicks and UI interactions.
    initializeEventListeners();

    // The visualizer's AudioContext can only be started after a user gesture.
    // We'll hook into the first click to initialize it.
    const initAudioSystem = () => {
        console.log('[Main] First user gesture, initializing audio system...');
        visualizer.init(); // Initialize our new visualizer
    };
    
    // Use a one-time listener on the main container for robustness.
    document.body.addEventListener('click', initAudioSystem, { once: true });
    document.body.addEventListener('touchend', initAudioSystem, { once: true });

    console.log('[Main] App initialization complete. Waiting for user gesture to start audio.');
}

// Wait for the Telegram WebApp to be ready, then initialize the app.
window.Telegram.WebApp.ready(initializeApp);
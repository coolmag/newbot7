// main.js - Main entry point for CoolMag Player

import { initRenderer } from "./renderer.js";

console.log("🎧 CoolMag Player starting...");

window.addEventListener("load", async () => {
  console.log("✅ WebApp loaded");

  // Initialize the 3D visualizer first
  initRenderer();

  // Telegram WebApp API
  if (window.Telegram?.WebApp) {
    try {
        Telegram.WebApp.ready();
        Telegram.WebApp.expand();
        console.log("✅ Telegram WebApp is ready and expanded.");
    } catch (e) {
        console.error("Telegram WebApp initialization error:", e);
    }
  }

  // Get DOM Elements
  const player = document.getElementById("player");
  const playlistDiv = document.getElementById("playlist");
  const playBtn = document.getElementById("playBtn");
  const pauseBtn = document.getElementById("pauseBtn");
  const nextBtn = document.getElementById("nextBtn");
  const playlistBtn = document.getElementById("playlistBtn");

  // State
  let playlist = [];
  let currentIndex = 0;

  // --- Core Functions ---

  // Fetches playlist from the backend API
  async function loadPlaylist(query = "Classic Rock Radio") {
    if (!playlistBtn.disabled) {
        playlistBtn.disabled = true;
        playlistBtn.textContent = "⌛ Loading...";
    }
    try {
      const res = await fetch(`/api/player/playlist?query=${encodeURIComponent(query)}`);
      if (!res.ok) {
        throw new Error(`API responded with ${res.status}`);
      }
      const data = await res.json();
      playlist = data.playlist || [];
      console.log("📻 Playlist loaded:", playlist);

      renderPlaylist();
      
      // Auto-play the first track if the playlist was loaded successfully
      if (playlist.length > 0) {
        playTrack(0);
      }

    } catch (err) {
      console.error("⚠️ Playlist loading error:", err);
      playlistDiv.innerHTML = `<div class="track error">Failed to load playlist.</div>`;
    } finally {
        playlistBtn.disabled = false;
        playlistBtn.textContent = "📜 Classic Rock";
    }
  }

  // Renders the current playlist to the DOM
  function renderPlaylist() {
      if (!playlist.length) {
          playlistDiv.innerHTML = `<div class="track">Playlist is empty.</div>`;
          return;
      }
      playlistDiv.innerHTML = playlist
        .map((t, i) => `<div class="track" data-idx="${i}">${i + 1}. ${t.title} - ${t.artist}</div>`)
        .join("");
  }

  // Plays a track by its index in the playlist
  function playTrack(index) {
    if (!playlist.length || index < 0 || index >= playlist.length) {
      console.warn("❗ Invalid track index or empty playlist.");
      return;
    }
    currentIndex = index;
    const track = playlist[index];
    
    // Construct the correct audio URL using our backend endpoint
    const audioUrl = `/audio/${track.identifier}.mp3`;
    console.log(`Preparing to play: ${track.title} from ${audioUrl}`);

    player.src = audioUrl;
    
    player.play().then(() => {
      console.log("▶️ Playing:", track.title);
      // Highlight the current track
      document.querySelectorAll('#playlist .track').forEach((el, i) => {
          el.classList.toggle('active', i === currentIndex);
      });
    }).catch(err => {
      console.error("🎧 Playback error:", err);
    });
  }

  // --- Event Listeners ---

  playBtn.addEventListener("click", () => {
    if (player.src) {
        player.play();
    } else {
        playTrack(currentIndex);
    }
  });

  pauseBtn.addEventListener("click", () => {
    player.pause();
  });

  nextBtn.addEventListener("click", () => {
    if (!playlist.length) return;
    currentIndex = (currentIndex + 1) % playlist.length;
    playTrack(currentIndex);
  });

  playlistBtn.addEventListener("click", () => {
    loadPlaylist("80s Synth Pop"); // Load a different genre on click
  });
  
  // Handle clicks on the playlist itself
  playlistDiv.addEventListener('click', (e) => {
      if (e.target && e.target.matches('.track')) {
          const trackIndex = parseInt(e.target.dataset.idx, 10);
          if (!isNaN(trackIndex)) {
              playTrack(trackIndex);
          }
      }
  });
  
  // Play next track when the current one ends
  player.addEventListener('ended', () => {
      nextBtn.click();
  });

  // --- Initial Load ---
  await loadPlaylist();
  console.log("✅ Player initialized.");
});
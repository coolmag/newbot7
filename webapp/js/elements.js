/**
 * Кэширование DOM-элементов для повышения производительности.
 */
export const audio = document.getElementById('audio-engine');

// Track Info
export const trackTitle = document.getElementById('current-track');
export const trackArtist = document.getElementById('current-artist');
export const trackAlbum = document.getElementById('current-album');

// Progress Bar
export const timeCurrent = document.getElementById('time-current');
export const timeTotal = document.getElementById('time-total');
export const progressFill = document.getElementById('progress-fill');
export const progressContainer = document.getElementById('seek-bar');

// Transport Controls
export const playBtn = document.getElementById('btn-play-pause'); // Унифицированный ID
export const nextBtn = document.getElementById('btn-next');
export const prevBtn = document.getElementById('btn-prev');
export const repeatBtn = document.getElementById('btn-repeat');
export const shuffleBtn = document.getElementById('btn-shuffle');

// Playlist
export const playlistContainer = document.getElementById('playlist-tracks');
export const trackCount = document.getElementById('track-count');

// Genres
export const genreGrid = document.getElementById('genre-grid');
export const genreModal = document.getElementById('genre-modal');
export const closeGenreBtn = document.getElementById('close-genre');
export const openGenresBtn = document.getElementById('btn-genres');
export const overlay = document.getElementById('overlay');

// Файл для дебага
document.addEventListener('DOMContentLoaded', () => {
    const debugEl = document.getElementById('debug-log');
    if (debugEl) {
        debugEl.innerHTML = 'DEBUG: main.js DOMContentLoaded сработал!';
    }
    alert('DEBUG: main.js DOMContentLoaded сработал!');
});

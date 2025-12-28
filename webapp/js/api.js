/**
 * Архитектурный модуль для связи с бэкендом FastAPI.
 */
export async function fetchPlaylist(query) {
    console.log(`[API] Запрос квантового потока для: ${query}`);
    try {
        const response = await fetch(`/api/player/playlist?query=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error('Neural Link Error');
        const data = await response.json();
        return data.playlist || [];
    } catch (e) {
        console.error('[API] Критическая ошибка связи:', e);
        return [];
    }
}
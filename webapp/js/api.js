export async function fetchPlaylist(query) {
    const r = await fetch(`/api/player/playlist?query=${encodeURIComponent(query)}`);
    const d = await r.json();
    return d.playlist || [];
}
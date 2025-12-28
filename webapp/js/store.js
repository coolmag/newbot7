/**
 * Реактивное хранилище состояния на базе Proxy.
 * UI Manager будет подписываться на изменения этого объекта.
 */
const state = {
    isPlaying: false,
    currentTrackIndex: -1,
    playlist: [],
};

const handler = {
    set(target, property, value) {
        target[property] = value;
        // В будущем здесь будет вызов рендера UI
        // console.log(`[Store] State changed: ${property} =`, value);
        if (window.uiManager) {
            window.uiManager.render(property, value);
        }
        return true;
    }
};

const store = new Proxy(state, handler);

export default store;
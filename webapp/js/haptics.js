/**
 * Модуль для управления тактильной обратной связью (вибрацией)
 * в Telegram WebApp.
 */

const WebApp = window.Telegram?.WebApp;

/**
 * Вызывает короткую вибрацию.
 * @param {('light'|'medium'|'heavy'|'rigid'|'soft')} style - Стиль вибрации.
 */
export function impact(style = 'light') {
    if (WebApp && WebApp.isVersionAtLeast('6.1') && WebApp.HapticFeedback) {
        WebApp.HapticFeedback.impactOccurred(style);
    }
}

/**
 * Вызывает вибрацию-уведомление.
 * @param {('success'|'warning'|'error')} type - Тип уведомления.
 */
export function notification(type = 'success') {
    if (WebApp && WebApp.isVersionAtLeast('6.1') && WebApp.HapticFeedback) {
        WebApp.HapticFeedback.notificationOccurred(type);
    }
}
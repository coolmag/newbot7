/**
 * Модуль для управления тактильной обратной связью (вибрацией)
 * в Telegram WebApp.
 */

// Проверяем, доступен ли объект HapticFeedback
const HapticFeedback = window.Telegram?.WebApp?.HapticFeedback;

/**
 * Вызывает короткую вибрацию.
 * @param {('light'|'medium'|'heavy'|'rigid'|'soft')} style - Стиль вибрации.
 */
export function impact(style = 'light') {
    if (HapticFeedback) {
        HapticFeedback.impactOccurred(style);
    }
}

/**
 * Вызывает вибрацию-уведомление.
 * @param {('success'|'warning'|'error')} type - Тип уведомления.
 */
export function notification(type = 'success') {
    if (HapticFeedback) {
        HapticFeedback.notificationOccurred(type);
    }
}
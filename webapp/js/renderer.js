// renderer.js — интеграция 3D визуализатора с CoolMag Player
import { visualizer } from "./visualizer.js";

export function initRenderer() {
  const container = document.getElementById("visualizer");
  if (!container) {
    console.warn("⚠️ Visualizer container not found");
    return;
  }

  visualizer.init("visualizer");

  const audio = document.querySelector("audio");
  if (audio) {
    // Подключаемся к аудио, когда плеер начинает играть
    audio.addEventListener("play", () => visualizer.connectAudio(audio));
    audio.addEventListener("pause", () => {
      if (audio.context && !audio.context.suspended) audio.context.suspend();
    });
  }
}
let canvas, ctx, audioCtx, analyser, dataArray;
let stars = [];
let isRunning = false;
let animationId;

// Настройки космоса
const STAR_COUNT = 150;
const BASE_SPEED = 2;

class Star {
    constructor() {
        this.reset();
    }
    
    reset() {
        this.x = (Math.random() - 0.5) * canvas.width * 2;
        this.y = (Math.random() - 0.5) * canvas.height * 2;
        this.z = Math.random() * canvas.width;
        this.pz = this.z; // Прошлая позиция для "хвостов"
    }

    update(speed) {
        this.z -= speed;
        if (this.z < 1) {
            this.reset();
            this.z = canvas.width;
            this.pz = this.z;
        }
    }

    draw(ctx, centerX, centerY) {
        const sx = (this.x / this.z) * centerX + centerX;
        const sy = (this.y / this.z) * centerY + centerY;
        
        const r = (1 - this.z / canvas.width) * 4;
        
        // Рисуем "хвост" звезды при ускорении
        const px = (this.x / this.pz) * centerX + centerX;
        const py = (this.y / this.pz) * centerY + centerY;
        
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(sx, sy);
        ctx.strokeStyle = `rgba(0, 242, 255, ${1 - this.z / canvas.width})`;
        ctx.lineWidth = r;
        ctx.stroke();
        
        this.pz = this.z; // Обновляем прошлую Z
    }
}

function initialize(audioElement) {
    if (isRunning) return;
    
    canvas = document.getElementById('visualizer-canvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d', { alpha: false }); // Оптимизация
    
    resize();
    window.addEventListener('resize', resize);

    // Создаем звезды
    stars = Array(STAR_COUNT).fill().map(() => new Star());

    // Аудио
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!audioCtx) audioCtx = new AudioContext();
        
        // Соединяем только если еще не соединено
        if (!analyser) {
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = 256;
            const source = audioCtx.createMediaElementSource(audioElement);
            source.connect(analyser);
            analyser.connect(audioCtx.destination);
            dataArray = new Uint8Array(analyser.frequencyBinCount);
        }
        
        isRunning = true;
        animate();
    } catch (e) {
        console.warn('AudioContext restricted:', e);
    }
}

function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

function animate() {
    if (!isRunning) return;
    animationId = requestAnimationFrame(animate);

    // Получаем данные звука
    analyser.getByteFrequencyData(dataArray);
    
    // Считаем среднюю громкость (басы)
    let bass = 0;
    for(let i = 0; i < 20; i++) bass += dataArray[i];
    bass = bass / 20; // 0..255
    
    const beat = bass / 255; // 0.0 .. 1.0

    // Очистка экрана (с легким шлейфом)
    ctx.fillStyle = 'rgba(5, 5, 16, 0.4)'; 
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const cx = canvas.width / 2;
    const cy = canvas.height / 2;

    // 1. Рисуем звезды
    // Скорость зависит от баса
    const speed = BASE_SPEED + (bass * 0.5);
    
    stars.forEach(star => {
        star.update(speed);
        star.draw(ctx, cx, cy);
    });

    // 2. Рисуем пульсирующий круг в центре
    ctx.beginPath();
    ctx.arc(cx, cy, 50 + (bass * 0.5), 0, Math.PI * 2);
    ctx.strokeStyle = `rgba(188, 19, 254, ${0.3 + beat})`;
    ctx.lineWidth = 2;
    ctx.stroke();

    // 3. Отдаем бит в CSS для подсветки интерфейса
    if (beat > 0.1) {
        document.documentElement.style.setProperty('--beat-intensity', beat.toFixed(2));
    }
}

export const Visualizer = { initialize };
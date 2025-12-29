let canvas, ctx, audioCtx, analyser, dataArray;
let stars = [];
let isRunning = false;
let animationId;

// Настройки: Меньше звезд, но красивее
const STAR_COUNT = 100; // Оптимизация для мобил
const BASE_SPEED = 0.5; // Медленный, величественный полет

class Star {
    constructor() {
        this.reset(true);
    }
    
    reset(randomZ = false) {
        this.x = (Math.random() - 0.5) * canvas.width * 2;
        this.y = (Math.random() - 0.5) * canvas.height * 2;
        this.z = randomZ ? Math.random() * canvas.width : canvas.width;
        this.size = Math.random();
    }

    update(speed) {
        this.z -= speed;
        if (this.z < 1) {
            this.reset();
        }
    }

    draw(ctx, centerX, centerY, bassIntensity) {
        // Проекция 3D на 2D
        const x = (this.x / this.z) * centerX + centerX;
        const y = (this.y / this.z) * centerY + centerY;
        
        // Размер зависит от приближения
        const r = (1 - this.z / canvas.width) * (3 * this.size + bassIntensity * 2);
        
        // Прозрачность
        const alpha = (1 - this.z / canvas.width);

        ctx.beginPath();
        ctx.fillStyle = `rgba(180, 220, 255, ${alpha})`;
        ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fill();
    }
}

function initialize(audioElement) {
    if (isRunning) return;
    
    canvas = document.getElementById('visualizer-canvas');
    if (!canvas) return;
    
    // Оптимизация: отключаем альфа-канал холста, если не нужен
    ctx = canvas.getContext('2d', { alpha: false }); 
    
    resize();
    window.addEventListener('resize', resize);

    stars = Array(STAR_COUNT).fill().map(() => new Star());

    // Audio Context (безопасный старт)
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!audioCtx) audioCtx = new AudioContext();
        
        if (!analyser) {
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = 128; // Меньше нагрузка на CPU
            analyser.smoothingTimeConstant = 0.85; // Плавнее реакция
            
            // Подключаем, если еще не подключено (защита от дублей)
            if (audioElement) {
                const source = audioCtx.createMediaElementSource(audioElement);
                source.connect(analyser);
                analyser.connect(audioCtx.destination);
            }
        }
        dataArray = new Uint8Array(analyser.frequencyBinCount);
        
        isRunning = true;
        animate();
    } catch (e) {
        console.warn('Audio visualization restricted:', e);
    }
}

function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

function animate() {
    if (!isRunning) return;
    requestAnimationFrame(animate);

    // Анализ звука
    let bass = 0;
    if (analyser) {
        analyser.getByteFrequencyData(dataArray);
        // Берем басы (первые 10 частот)
        for(let i = 0; i < 10; i++) bass += dataArray[i];
        bass = bass / 10 / 255; // 0.0 ... 1.0
    }

    // Чистим экран (черный космос)
    ctx.fillStyle = '#050510'; 
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    
    // Скорость зависит от баса (рывок при ударе)
    const currentSpeed = BASE_SPEED + (bass * 8); 

    // Рисуем звезды
    stars.forEach(star => {
        star.update(currentSpeed);
        star.draw(ctx, cx, cy, bass);
    });

    // Передаем CSS переменную для пульсации интерфейса
    if (bass > 0.05) {
        document.documentElement.style.setProperty('--beat', bass.toFixed(3));
    }
}

export const Visualizer = { initialize };
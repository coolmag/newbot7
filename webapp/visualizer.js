import * as THREE from 'three';

let scene, camera, renderer, analyzer, dataArray;
let sphere, geometry, originalPositions;
let isInitialized = false;

function initialize(audioElement) {
    if (isInitialized) return;

    const canvas = document.getElementById('visualizer-canvas');
    if (!canvas) return;

    // Сцена
    scene = new THREE.Scene();
    // Легкий туман для глубины
    scene.fog = new THREE.FogExp2(0x050510, 0.035);

    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 15;

    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);

    // Создаем сферу (Icosahedron)
    const geo = new THREE.IcosahedronGeometry(6, 4); // Детализированная сфера
    geometry = new THREE.WireframeGeometry(geo);
    
    // Материал с неоновым свечением
    const material = new THREE.LineBasicMaterial({ 
        color: 0x00f2ff,
        transparent: true,
        opacity: 0.3
    });

    sphere = new THREE.LineSegments(geometry, material);
    scene.add(sphere);

    // Аудио контекст
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        const ctx = new AudioContext();
        
        // Фикс для автозапуска
        if (ctx.state === 'suspended') {
            document.body.addEventListener('touchstart', () => ctx.resume(), { once: true });
            document.body.addEventListener('click', () => ctx.resume(), { once: true });
        }

        const source = ctx.createMediaElementSource(audioElement);
        analyzer = ctx.createAnalyser();
        analyzer.fftSize = 512; // Больше деталей
        source.connect(analyzer);
        analyzer.connect(ctx.destination);
        dataArray = new Uint8Array(analyzer.frequencyBinCount);
    } catch (e) {
        console.error('[Visualizer] AudioContext Error:', e);
    }

    window.addEventListener('resize', onWindowResize);
    isInitialized = true;
    animate();
}

function onWindowResize() {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
    requestAnimationFrame(animate);

    if (analyzer && sphere) {
        analyzer.getByteFrequencyData(dataArray);

        // Расчет средней громкости (Bass)
        let sum = 0;
        const bassRange = 40; // Берем первые 40 бинов (басы)
        for(let i = 0; i < bassRange; i++) sum += dataArray[i];
        const bassLevel = sum / bassRange; // 0..255
        
        // Нормализуем (0.0 - 1.0)
        const beat = bassLevel / 255;

        // 1. Вращение
        sphere.rotation.x += 0.002;
        sphere.rotation.y += 0.003 + (beat * 0.02);

        // 2. Пульсация (Scale)
        const scale = 1 + (beat * 0.3);
        sphere.scale.set(scale, scale, scale);

        // 3. Цвет (меняется от интенсивности)
        // От синего (спокойно) к фиолетовому/розовому (громко)
        const r = beat; 
        const g = 1 - beat;
        const b = 1;
        sphere.material.color.setRGB(r, g * 0.5, b);
        sphere.material.opacity = 0.3 + (beat * 0.5);

        // 4. Передаем "бит" в CSS для подсветки интерфейса
        document.documentElement.style.setProperty('--beat-intensity', beat.toFixed(2));
    }

    renderer.render(scene, camera);
}

export const Visualizer = { initialize };
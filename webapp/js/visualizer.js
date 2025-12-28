import * as THREE from 'three';

let scene, camera, renderer, disc, analyzer, dataArray;
let isInitialized = false;

export function initializeVisualizer(audioElement) {
    if (isInitialized) return;

    const container = document.getElementById('canvas-container');
    const w = container.clientWidth;
    const h = container.clientHeight;

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    container.appendChild(renderer.domElement);

    // Геометрия винила
    const geometry = new THREE.CylinderGeometry(2, 2, 0.08, 64);
    const material = new THREE.MeshStandardMaterial({ 
        color: 0x121212, 
        roughness: 0.3, 
        metalness: 0.8 
    });
    disc = new THREE.Mesh(geometry, material);
    disc.rotation.x = Math.PI / 2.3;
    scene.add(disc);

    // Добавляем освещение для блеска
    const light1 = new THREE.PointLight(0xffffff, 50);
    light1.position.set(2, 5, 5);
    scene.add(light1);
    
    const light2 = new THREE.AmbientLight(0x404040, 2);
    scene.add(light2);

    camera.position.z = 5.5;

    // Анализатор
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaElementSource(audioElement);
    analyzer = audioCtx.createAnalyser();
    analyzer.fftSize = 64;
    source.connect(analyzer);
    analyzer.connect(audioCtx.destination);
    dataArray = new Uint8Array(analyzer.frequencyBinCount);

    isInitialized = true;
    animate();
}

function animate() {
    requestAnimationFrame(animate);
    if (analyzer) {
        analyzer.getByteFrequencyData(dataArray);
        const volume = dataArray[0] / 255;
        
        // Вращение и пульсация
        disc.rotation.y += 0.02 + volume * 0.1;
        const scale = 1 + volume * 0.15;
        disc.scale.set(scale, 1, scale);

        // Синхронизация LED ленты через CSS переменные
        document.documentElement.style.setProperty('--led-speed', `${0.5 + (1 - volume)}s`);
    }
    renderer.render(scene, camera);
}
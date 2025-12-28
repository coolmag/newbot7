import * as THREE from 'three';

let scene, camera, renderer, disc, analyzer, dataArray;
let isInitialized = false;

export function initializeVisualizer(audioElement) {
    if (isInitialized) return;

    const container = document.getElementById('canvas-container');
    const w = container.clientWidth, h = container.clientHeight;

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    container.appendChild(renderer.domElement);

    // Геометрия винила
    const geometry = new THREE.CylinderGeometry(2, 2, 0.08, 64);
    const material = new THREE.MeshStandardMaterial({ 
        color: 0x111111, roughness: 0.2, metalness: 0.9 
    });
    disc = new THREE.Mesh(geometry, material);
    disc.rotation.x = Math.PI / 2.2;
    scene.add(disc);

    // Свет (для бликов на виниле)
    const pLight = new THREE.PointLight(0xffffff, 80);
    pLight.position.set(2, 5, 5);
    scene.add(pLight);
    scene.add(new THREE.AmbientLight(0x404040, 3));

    camera.position.z = 5.5;

    // Анализатор звука
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
        
        // Вращение и реакция на бас
        disc.rotation.y += 0.02 + volume * 0.2;
        const s = 1 + volume * 0.12;
        disc.scale.set(s, 1, s);

        // Синхронизация RGB кольца (через CSS)
        document.documentElement.style.setProperty('--led-speed', `${0.2 + (1 - volume) * 2}s`);
    }
    renderer.render(scene, camera);
}
import * as THREE from 'three';

let scene, camera, renderer, disc, analyzer, dataArray;
let isInitialized = false;

export function initializeVisualizer(audioElement) {
    if (isInitialized || !audioElement) return;

    const container = document.getElementById('canvas-container');
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    // Сцена
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(width, height);
    container.appendChild(renderer.domElement);

    // Геометрия Винила (PBR Material)
    const geometry = new THREE.CylinderGeometry(2, 2, 0.08, 128);
    const material = new THREE.MeshStandardMaterial({ 
        color: 0x0a0a0a, 
        roughness: 0.15, 
        metalness: 0.9,
        emissive: 0x000000 
    });
    disc = new THREE.Mesh(geometry, material);
    disc.rotation.x = Math.PI / 2.2;
    scene.add(disc);

    // Наклейка
    const labelGeo = new THREE.CircleGeometry(0.75, 64);
    const labelMat = new THREE.MeshStandardMaterial({ color: 0xcc0000, roughness: 0.8 });
    const label = new THREE.Mesh(labelGeo, labelMat);
    label.position.y = 0.05;
    label.rotation.x = -Math.PI / 2;
    disc.add(label);

    // Освещение (Architectural Studio Lighting)
    const mainLight = new THREE.PointLight(0xffffff, 200);
    mainLight.position.set(5, 5, 5);
    scene.add(mainLight);

    const accentLight = new THREE.PointLight(0x00f2ff, 150);
    accentLight.position.set(-3, 2, 4);
    scene.add(accentLight);

    scene.add(new THREE.AmbientLight(0xffffff, 0.5));

    camera.position.set(0, 0, 6.5);

    // Анализатор частот
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioCtx.createMediaElementSource(audioElement);
        analyzer = audioCtx.createAnalyser();
        analyzer.fftSize = 128;
        source.connect(analyzer);
        analyzer.connect(audioCtx.destination);
        dataArray = new Uint8Array(analyzer.frequencyBinCount);
    } catch (e) {
        console.warn("[3D] AudioContext block by browser policy");
    }

    isInitialized = true;
    animate();
}

function animate() {
    requestAnimationFrame(animate);
    if (analyzer && disc) {
        analyzer.getByteFrequencyData(dataArray);
        const bass = dataArray[0] / 255;
        const mid = dataArray[10] / 255;

        // Кинематика диска
        disc.rotation.y += 0.02 + bass * 0.15;
        const s = 1 + bass * 0.08;
        disc.scale.set(s, 1, s);

        // Реактивный свет
        document.documentElement.style.setProperty('--led-speed', `${0.2 + (1 - bass) * 1.5}s`);
    }
    renderer.render(scene, camera);
}
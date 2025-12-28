import * as THREE from 'three';

let scene, camera, renderer, disc, analyzer, dataArray;
let isInitialized = false;

export function initializeVisualizer(audioElement) {
    if (isInitialized || !audioElement) return;

    const container = document.getElementById('turntable-3d'); // ID из NeoVinyl
    if (!container) {
        console.warn('[3D] Container #turntable-3d not found');
        return;
    }
    
    const { clientWidth: w, clientHeight: h } = container;

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100);
    camera.position.set(0, 3, 6);
    camera.lookAt(0, 0, 0);

    // Квантовый Винил (PBR Материал)
    const geometry = new THREE.CylinderGeometry(2.2, 2.2, 0.05, 128);
    const material = new THREE.MeshPhysicalMaterial({
        color: 0x050505,
        metalness: 1.0,
        roughness: 0.1,
        clearcoat: 1.0,
        reflectivity: 1.0
    });
    
    disc = new THREE.Mesh(geometry, material);
    scene.add(disc);

    // Свет (Cyberpunk Studio)
    const mainLight = new THREE.PointLight(0x00f3ff, 100);
    mainLight.position.set(5, 5, 5);
    scene.add(mainLight);

    const secondaryLight = new THREE.PointLight(0xff00ff, 80);
    secondaryLight.position.set(-5, 2, 5);
    scene.add(secondaryLight);

    // Audio Link
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const source = ctx.createMediaElementSource(audioElement);
        analyzer = ctx.createAnalyser();
        analyzer.fftSize = 64;
        source.connect(analyzer);
        analyzer.connect(ctx.destination);
        dataArray = new Uint8Array(analyzer.frequencyBinCount);
    } catch (e) {
        console.error('[3D] AudioContext initialization failed:', e);
    }


    isInitialized = true;
    animate();
}

function animate() {
    requestAnimationFrame(animate);
    if (analyzer && disc) {
        analyzer.getByteFrequencyData(dataArray);
        const bass = dataArray[0] / 255;
        
        disc.rotation.y += 0.02 + bass * 0.1;
        disc.scale.set(1 + bass * 0.05, 1, 1 + bass * 0.05);
        
        // Передача энергии в CSS переменные NeoVinyl
        document.documentElement.style.setProperty('--glow-intensity', `${0.5 + bass} `);
    }
    if (renderer && scene && camera) {
        renderer.render(scene, camera);
    }
}
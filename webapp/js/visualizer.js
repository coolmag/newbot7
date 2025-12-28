import * as THREE from 'three';

let scene, camera, renderer, analyzer, dataArray;
let particles, particleMaterial;
let isInitialized = false;

function initialize(audioElement) {
    if (isInitialized) return;

    const canvas = document.getElementById('visualizer-canvas');
    if (!canvas) return;

    // Сцена
    scene = new THREE.Scene();
    
    // Камера
    camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.z = 25;

    // Рендерер
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(window.devicePixelRatio);

    // Частицы
    const particleCount = 2000;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
        positions[i * 3] = (Math.random() - 0.5) * 50;
        positions[i * 3 + 1] = (Math.random() - 0.5) * 50;
        positions[i * 3 + 2] = (Math.random() - 0.5) * 50;
    }
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    
    particleMaterial = new THREE.PointsMaterial({
        color: 0x00f2ff,
        size: 0.1,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    });

    particles = new THREE.Points(geometry, particleMaterial);
    scene.add(particles);
    
    // Audio Link
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const source = ctx.createMediaElementSource(audioElement);
        analyzer = ctx.createAnalyser();
        analyzer.fftSize = 256;
        source.connect(analyzer);
        analyzer.connect(ctx.destination);
        dataArray = new Uint8Array(analyzer.frequencyBinCount);
    } catch (e) {
        console.error('[Visualizer] AudioContext failed:', e);
        return;
    }
    
    // Handlers
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

    if (analyzer) {
        analyzer.getByteFrequencyData(dataArray);
        
        const lowerHalf = dataArray.slice(0, (dataArray.length/2) - 1);
        const upperHalf = dataArray.slice((dataArray.length/2) - 1, dataArray.length - 1);

        const lowerAvg = lowerHalf.reduce((a, b) => a + b) / lowerHalf.length;
        const upperAvg = upperHalf.reduce((a, b) => a + b) / upperHalf.length;
        
        const bass = lowerAvg / 255;
        const treble = upperAvg / 255;

        if (particles) {
            particles.rotation.x += 0.001 + (bass * 0.001);
            particles.rotation.y += 0.002 + (treble * 0.002);
        }
        
        if (particleMaterial) {
            particleMaterial.size = 0.1 + bass * 0.2;
        }
    }
    
    renderer.render(scene, camera);
}

export const Visualizer = {
    initialize
};

import * as THREE from 'three';

let scene, camera, renderer, disc, analyzer, dataArray;
let isInitialized = false;

export function initializeVisualizer(audioElement) {
    if (isInitialized) return;

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    
    const container = document.getElementById('canvas-container');
    renderer.setSize(container.clientWidth, container.clientHeight);
    container.appendChild(renderer.domElement);

    const geometry = new THREE.CylinderGeometry(2, 2, 0.05, 64);
    const material = new THREE.MeshPhongMaterial({ color: 0x111111, shininess: 100 });
    disc = new THREE.Mesh(geometry, material);
    disc.rotation.x = Math.PI / 2.5;
    scene.add(disc);

    const light = new THREE.PointLight(0x00f2ff, 2, 50);
    light.position.set(5, 5, 5);
    scene.add(light);
    scene.add(new THREE.AmbientLight(0x404040));

    camera.position.z = 6;

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
        disc.rotation.y += 0.02 + volume * 0.1;
        const scale = 1 + volume * 0.15;
        disc.scale.set(scale, 1, scale);
        document.documentElement.style.setProperty('--led-speed', `${0.3 + (1 - volume)}s`);
    }
    renderer.render(scene, camera);
}
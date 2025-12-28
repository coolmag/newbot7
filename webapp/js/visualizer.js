import * as THREE from 'three';

let scene, camera, renderer, disc, tonearm, analyzer, dataArray;
let isInitialized = false;

export function initializeVisualizer(audioElement) {
    if (isInitialized) return;

    const container = document.getElementById('canvas-container');
    const w = container.clientWidth, h = container.clientHeight;

    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 1000);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    container.appendChild(renderer.domElement);

    // 1. Пластинка
    const discGeo = new THREE.CylinderGeometry(2, 2, 0.05, 64);
    const discMat = new THREE.MeshStandardMaterial({ color: 0x0a0a0a, roughness: 0.3, metalness: 0.8 });
    disc = new THREE.Mesh(discGeo, discMat);
    disc.rotation.x = Math.PI / 2.3;
    scene.add(disc);

    // 2. Наклейка (Красная)
    const labelGeo = new THREE.CircleGeometry(0.7, 32);
    const labelMat = new THREE.MeshStandardMaterial({ color: 0xff0000 });
    const label = new THREE.Mesh(labelGeo, labelMat);
    label.position.y = 0.03; label.rotation.x = -Math.PI / 2;
    disc.add(label);

    // 3. Тонарм (Игла)
    const armGroup = new THREE.Group();
    const armGeo = new THREE.CylinderGeometry(0.04, 0.04, 2, 8);
    const armMat = new THREE.MeshStandardMaterial({ color: 0x222222 });
    const arm = new THREE.Mesh(armGeo, armMat);
    arm.position.y = 1; armGroup.add(arm);
    armGroup.position.set(1.8, 0.4, 1.8);
    scene.add(armGroup);
    tonearm = armGroup;

    scene.add(new THREE.PointLight(0xffffff, 150, 100).clone().set(5, 5, 5));
    scene.add(new THREE.AmbientLight(0xffffff, 2));

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
        tonearm.rotation.z = Math.sin(Date.now() * 0.001) * 0.05;
        document.documentElement.style.setProperty('--led-speed', `${0.2 + (1 - volume) * 2}s`);
    }
    renderer.render(scene, camera);
}
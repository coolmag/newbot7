// visualizer.js — Финальная версия 3D винилового плеера с RGB подсветкой и частицами
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js";

let scene, camera, renderer, vinyl, glowRing, particles, analyser, dataArray, audioCtx, source, controls;
let bass = 0, colorShift = 0, isPlaying = false;

const visualizerContainer = document.getElementById("visualizer");
const audioElement = document.getElementById("player");

function initScene() {
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.set(0, 2, 6);

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  visualizerContainer.appendChild(renderer.domElement);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.enableZoom = false;
  controls.autoRotate = false;

  const ambient = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambient);
  const pointLight = new THREE.PointLight(0xffffff, 1.5, 100);
  pointLight.position.set(5, 5, 5);
  scene.add(pointLight);

  const vinylGeometry = new THREE.CylinderGeometry(2.2, 2.2, 0.05, 64, 1, true);
  const vinylMaterial = new THREE.MeshStandardMaterial({
    color: 0x111111,
    metalness: 0.8,
    roughness: 0.3,
    side: THREE.DoubleSide,
  });
  vinyl = new THREE.Mesh(vinylGeometry, vinylMaterial);
  vinyl.rotation.x = Math.PI / 2;
  scene.add(vinyl);

  const centerGeometry = new THREE.CylinderGeometry(0.15, 0.15, 0.05, 32);
  const centerMaterial = new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    metalness: 1.0,
    roughness: 0.1,
    clearcoat: 1.0,
    emissive: 0x202020,
  });
  const center = new THREE.Mesh(centerGeometry, centerMaterial);
  center.position.y = 0.03;
  vinyl.add(center);

  const glowGeometry = new THREE.RingGeometry(2.4, 2.6, 128);
  const glowMaterial = new THREE.ShaderMaterial({
    uniforms: {
      time: { value: 0 },
      color: { value: new THREE.Color(0xff0000) },
      intensity: { value: 1.0 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main(){
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 color;
      uniform float time;
      uniform float intensity;
      varying vec2 vUv;
      void main(){
        float glow = sin(time*2.0 + vUv.x*10.0) * 0.5 + 0.5;
        glow = pow(glow, 3.0);
        gl_FragColor = vec4(color * glow * intensity, 1.0);
      }
    `,
    transparent: true,
    side: THREE.DoubleSide,
  });
  glowRing = new THREE.Mesh(glowGeometry, glowMaterial);
  glowRing.rotation.x = Math.PI / 2;
  scene.add(glowRing);

  const particleCount = 400;
  const positions = new Float32Array(particleCount * 3);
  const speeds = [];
  for (let i = 0; i < particleCount; i++) {
    const angle = Math.random() * 2 * Math.PI;
    const radius = Math.random() * 0.5 + 0.2;
    positions[i * 3] = Math.cos(angle) * radius;
    positions[i * 3 + 1] = 0;
    positions[i * 3 + 2] = Math.sin(angle) * radius;
    speeds.push(Math.random() * 0.02 + 0.005);
  }
  const particleGeometry = new THREE.BufferGeometry();
  particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const particleMaterial = new THREE.PointsMaterial({
    color: 0xffffff,
    size: 0.05,
    transparent: true,
    opacity: 0.9,
  });
  particles = new THREE.Points(particleGeometry, particleMaterial);
  particles.userData.speeds = speeds;
  scene.add(particles);

  window.addEventListener("resize", onResize);
  animate();
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function initAudio() {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  source = audioCtx.createMediaElementSource(audioElement);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  const bufferLength = analyser.frequencyBinCount;
  dataArray = new Uint8Array(bufferLength);
  source.connect(analyser);
  analyser.connect(audioCtx.destination);
}

function analyzeAudio() {
  analyser.getByteFrequencyData(dataArray);
  let bassSum = 0;
  for (let i = 0; i < 10; i++) bassSum += dataArray[i];
  bass = bassSum / 10 / 255;
}

function animate() {
  requestAnimationFrame(animate);
  if (isPlaying && analyser) analyzeAudio();
  vinyl.rotation.z += 0.02 + bass * 0.05;
  colorShift += 0.01;
  const hue = (colorShift * 30) % 360;
  glowRing.material.uniforms.time.value += 0.02;
  glowRing.material.uniforms.color.value.setHSL(hue / 360, 1, 0.5);
  glowRing.material.uniforms.intensity.value = 1 + bass * 3;

  const pos = particles.geometry.attributes.position;
  const speeds = particles.userData.speeds;
  for (let i = 0; i < pos.count; i++) {
    let x = pos.getX(i);
    let z = pos.getZ(i);
    const len = Math.sqrt(x * x + z * z);
    const angle = Math.atan2(z, x);
    const newLen = len + speeds[i] * (0.2 + bass * 5);
    pos.setX(i, Math.cos(angle) * newLen);
    pos.setZ(i, Math.sin(angle) * newLen);
    if (newLen > 3) {
      const newAngle = Math.random() * 2 * Math.PI;
      const newR = Math.random() * 0.5 + 0.2;
      pos.setX(i, Math.cos(newAngle) * newR);
      pos.setZ(i, Math.sin(newAngle) * newR);
    }
  }
  pos.needsUpdate = true;
  controls.update();
  renderer.render(scene, camera);
}

audioElement.onplay = () => {
  if (!audioCtx) initAudio();
  audioCtx.resume();
  isPlaying = true;
};

audioElement.onpause = () => {
  isPlaying = false;
};

initScene();
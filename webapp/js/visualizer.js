import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { GlitchPass } from 'three/examples/jsm/postprocessing/GlitchPass.js';

class VinylVisualizer {
    constructor() {
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.composer = null;
        this.vinyl = null;
        this.tonearm = null;
        this.analyser = null;
        this.dataArray = null;
        this.isInitialized = false;
        
        this.init();
    }
    
    init() {
        // Создание сцены
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x050510);
        
        // Камера
        this.camera = new THREE.PerspectiveCamera(
            45,
            window.innerWidth / window.innerHeight,
            0.1,
            1000
        );
        this.camera.position.set(0, 2, 8);
        this.camera.lookAt(0, 0, 0);
        
        // Рендерер
        const canvas = document.getElementById('turntable-3d');
        this.renderer = new THREE.WebGLRenderer({ 
            canvas,
            antialias: true,
            alpha: true,
            powerPreference: 'high-performance'
        });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setSize(canvas.clientWidth, canvas.clientHeight);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        // Освещение
        this.setupLights();
        
        // Создание 3D-винила
        this.createVinylRecord();
        
        // Создание тонарма
        this.createTonearm();
        
        // Пост-обработка (эффекты свечения)
        this.setupPostProcessing();
        
        // Обработка ресайза
        window.addEventListener('resize', () => this.onResize());
        
        this.isInitialized = true;
    }
    
    setupLights() {
        // Основное освещение
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.3);
        this.scene.add(ambientLight);
        
        // Неоновые RGB-огни
        const colors = [0xff0000, 0x00ff00, 0x0000ff, 0xff00ff, 0xffff00];
        colors.forEach((color, i) => {
            const angle = (i / colors.length) * Math.PI * 2;
            const light = new THREE.PointLight(color, 1.5, 10);
            light.position.set(
                Math.cos(angle) * 3,
                2,
                Math.sin(angle) * 3
            );
            this.scene.add(light);
            
            // Создание свечения вокруг источника
            const glowGeometry = new THREE.SphereGeometry(0.1, 16, 16);
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.7
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            glow.position.copy(light.position);
            this.scene.add(glow);
        });
        
        // Направленный свет для теней
        const directionalLight = new THREE.DirectionalLight(0x00f3ff, 0.5);
        directionalLight.position.set(5, 5, 5);
        directionalLight.castShadow = true;
        directionalLight.shadow.mapSize.width = 2048;
        directionalLight.shadow.mapSize.height = 2048;
        this.scene.add(directionalLight);
    }
    
    createVinylRecord() {
        // Основной диск
        const vinylGeometry = new THREE.CylinderGeometry(2, 2, 0.1, 64);
        
        // Создание PBR материала для реалистичности
        const vinylMaterial = new THREE.MeshStandardMaterial({
            color: 0x111111,
            metalness: 0.9,
            roughness: 0.1,
            envMapIntensity: 1.0
        });
        
        this.vinyl = new THREE.Mesh(vinylGeometry, vinylMaterial);
        this.vinyl.castShadow = true;
        this.vinyl.receiveShadow = true;
        this.scene.add(this.vinyl);
        
        // Дорожки винила (анизотропные отражения)
        const groovesGeometry = new THREE.CylinderGeometry(1.9, 1.9, 0.11, 128);
        const groovesMaterial = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 }
            },
            vertexShader: `
                varying vec3 vNormal;
                varying vec2 vUv;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    vUv = uv;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float time;
                varying vec3 vNormal;
                varying vec2 vUv;
                
                void main() {
                    // Анизотропные отражения как на реальном виниле
                    float anisotropy = dot(vNormal, vec3(0.0, 1.0, 0.0));
                    float pattern = sin(vUv.x * 200.0 + time) * 0.5 + 0.5;
                    
                    vec3 color = mix(vec3(0.1), vec3(0.3), pattern);
                    color *= anisotropy * 2.0;
                    
                    gl_FragColor = vec4(color, 0.8);
                }
            `,
            transparent: true
        });
        
        const grooves = new THREE.Mesh(groovesGeometry, groovesMaterial);
        this.vinyl.add(grooves);
        
        // Этикетка
        const labelGeometry = new THREE.CylinderGeometry(0.4, 0.4, 0.12, 32);
        const labelMaterial = new THREE.MeshStandardMaterial({
            color: 0xcc0000,
            roughness: 0.3,
            metalness: 0.2
        });
        const label = new THREE.Mesh(labelGeometry, labelMaterial);
        label.position.y = 0.06;
        this.vinyl.add(label);
        
        // Текст на этикетке
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        canvas.width = 256;
        canvas.height = 256;
        
        context.fillStyle = '#ffffff';
        context.font = 'bold 40px Arial';
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText('NEO', 128, 100);
        context.fillText('VINYL', 128, 150);
        
        const texture = new THREE.CanvasTexture(canvas);
        const textMaterial = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true
        });
        
        const textGeometry = new THREE.CircleGeometry(0.3, 32);
        const text = new THREE.Mesh(textGeometry, textMaterial);
        text.position.y = 0.121;
        text.rotation.x = -Math.PI / 2;
        this.vinyl.add(text);
    }
    
    createTonearm() {
        const group = new THREE.Group();
        
        // Основание
        const baseGeometry = new THREE.BoxGeometry(0.2, 0.1, 0.2);
        const baseMaterial = new THREE.MeshStandardMaterial({
            color: 0x333333,
            metalness: 0.8,
            roughness: 0.2
        });
        const base = new THREE.Mesh(baseGeometry, baseMaterial);
        base.position.set(1.5, 0.05, 0);
        group.add(base);
        
        // Стойка
        const rodGeometry = new THREE.CylinderGeometry(0.02, 0.02, 1);
        const rodMaterial = new THREE.MeshStandardMaterial({
            color: 0x666666,
            metalness: 0.9,
            roughness: 0.1
        });
        const rod = new THREE.Mesh(rodGeometry, rodMaterial);
        rod.position.set(1.5, 0.6, 0);
        group.add(rod);
        
        // Головка
        const headGeometry = new THREE.BoxGeometry(0.15, 0.05, 0.1);
        const headMaterial = new THREE.MeshStandardMaterial({
            color: 0x00f3ff,
            metalness: 0.95,
            roughness: 0.05,
            emissive: 0x00f3ff,
            emissiveIntensity: 0.2
        });
        const head = new THREE.Mesh(headGeometry, headMaterial);
        head.position.set(1.5, 1.1, 0);
        group.add(head);
        
        // Игла
        const needleGeometry = new THREE.ConeGeometry(0.01, 0.15, 8);
        const needleMaterial = new THREE.MeshStandardMaterial({
            color: 0xffffff,
            metalness: 1.0,
            roughness: 0.0
        });
        const needle = new THREE.Mesh(needleGeometry, needleMaterial);
        needle.position.set(1.5, 0.95, 0.05);
        needle.rotation.x = Math.PI;
        group.add(needle);
        
        this.tonearm = group;
        this.scene.add(this.tonearm);
    }
    
    setupPostProcessing() {
        this.composer = new EffectComposer(this.renderer);
        
        const renderPass = new RenderPass(this.scene, this.camera);
        this.composer.addPass(renderPass);
        
        // Bloom эффект для неонового свечения
        const bloomPass = new UnrealBloomPass(
            new THREE.Vector2(window.innerWidth, window.innerHeight),
            1.5,  // strength
            0.4,  // radius
            0.85  // threshold
        );
        this.composer.addPass(bloomPass);
        
        // Глитч эффекты
        const glitchPass = new GlitchPass();
        glitchPass.enabled = false; // Включается по необходимости
        this.composer.addPass(glitchPass);
    }
    
    update(audioData) {
        if (!this.isInitialized) return;
        
        // Вращение винила
        if (audioData && audioData.length > 0) {
            const avgAmplitude = audioData.reduce((a, b) => a + b) / audioData.length / 255;
            const rotationSpeed = 0.01 + avgAmplitude * 0.02;
            
            this.vinyl.rotation.y += rotationSpeed;
            
            // Анимация тонарма в зависимости от звука
            if (this.tonearm) {
                const tonearmRotation = Math.sin(Date.now() * 0.001) * 0.1 * avgAmplitude;
                this.tonearm.rotation.y = tonearmRotation;
            }
        }
        
        // Обновление шейдера дорожек
        const grooves = this.vinyl.children.find(child => child.material.uniforms?.time);
        if (grooves) {
            grooves.material.uniforms.time.value = Date.now() * 0.001;
        }
        
        // Рендер
        this.composer.render();
    }
    
    onResize() {
        const canvas = document.getElementById('turntable-3d');
        const width = canvas.clientWidth;
        const height = canvas.clientHeight;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
        this.composer.setSize(width, height);
    }
    
    start(analyserNode) {
        this.analyser = analyserNode;
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        
        const animate = () => {
            requestAnimationFrame(animate);
            
            if (this.analyser) {
                this.analyser.getByteFrequencyData(this.dataArray);
                this.update(this.dataArray);
            }
        };
        
        animate();
    }
}

export async function initializeVisualizer() {
    const visualizer = new VinylVisualizer();
    return visualizer;
}
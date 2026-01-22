import { ThreeJSRenderer } from './renderer_three.js';
import { ShaderRenderer } from './renderer_shader.js';

class RayTracingApp {
    constructor() {
        this.canvas = document.getElementById('canvas');
        this.ctx = this.canvas.getContext('2d');
        this.sceneData = null;
        this.currentMode = 'threejs';
        this.renderer = null;
        this.threeRenderer = null;
        this.shaderRenderer = null;
        this.animationFrame = null;
        this.lastTime = performance.now();
        this.fps = 0;
        this.frameCount = 0;
        
        this.setupCanvas();
        this.setupControls();
        this.loadScene();
    }
    
    setupCanvas() {
        const resize = () => {
            const container = document.getElementById('canvas-container');
            this.canvas.width = container.clientWidth;
            this.canvas.height = container.clientHeight;
            if (this.renderer) {
                this.renderer.resize(this.canvas.width, this.canvas.height);
            }
        };
        
        window.addEventListener('resize', resize);
        resize();
    }
    
    setupControls() {
        // Mode selector
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.mode;
                this.setMode(mode);
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });
        
        // Camera controls
        const rotX = document.getElementById('rot-x');
        const rotY = document.getElementById('rot-y');
        const distance = document.getElementById('distance');
        
        rotX.addEventListener('input', (e) => {
            document.getElementById('rot-x-val').textContent = e.target.value;
            this.updateCamera();
        });
        
        rotY.addEventListener('input', (e) => {
            document.getElementById('rot-y-val').textContent = e.target.value;
            this.updateCamera();
        });
        
        distance.addEventListener('input', (e) => {
            document.getElementById('dist-val').textContent = parseFloat(e.target.value).toFixed(1);
            this.updateCamera();
        });
        
        // Ray tracing controls
        const maxBounces = document.getElementById('max-bounces');
        const resScale = document.getElementById('res-scale');
        
        maxBounces.addEventListener('input', (e) => {
            document.getElementById('bounces-val').textContent = e.target.value;
            if (this.shaderRenderer) {
                this.shaderRenderer.setMaxBounces(parseInt(e.target.value));
            }
        });
        
        resScale.addEventListener('input', (e) => {
            document.getElementById('res-val').textContent = parseFloat(e.target.value).toFixed(2);
            if (this.shaderRenderer) {
                this.shaderRenderer.setResolutionScale(parseFloat(e.target.value));
            }
        });
        
        // Human rotation
        const humanRot = document.getElementById('human-rotation');
        humanRot.addEventListener('input', (e) => {
            document.getElementById('human-rot-val').textContent = e.target.value;
            if (this.renderer) {
                this.renderer.setHumanRotation(parseFloat(e.target.value));
            }
        });
        
        // Reload scene
        document.getElementById('reload-scene').addEventListener('click', () => {
            this.loadScene();
        });
    }
    
    async loadScene() {
        try {
            const response = await fetch('scene.json');
            this.sceneData = await response.json();
            this.initRenderers();
        } catch (error) {
            console.error('Failed to load scene:', error);
            // Fallback scene data
            this.sceneData = this.getDefaultScene();
            this.initRenderers();
        }
    }
    
    getDefaultScene() {
        return {
            camera: { position: [0.0, 1.5, 5.0], look_at: [0.0, 1.5, 0.0], fov: 60.0 },
            room: { size: [8.0, 6.0, 8.0], center: [0.0, 3.0, 0.0] },
            light: { position: [-3.5, 5.5, -3.5], radius: 0.3, intensity: [15.0, 14.0, 12.0] },
            mirrors: [
                { position: [0.0, 1.5, -3.9], normal: [0.0, 0.0, 1.0], size: [2.0, 3.0], reflectivity: 0.95 },
                { position: [3.9, 1.5, 0.0], normal: [-1.0, 0.0, 0.0], size: [2.0, 3.0], reflectivity: 0.95 }
            ],
            human_models: [
                { position: [1.5, 0.0, 1.0], rotation: 0.0, scale: 1.0, color: [0.9, 0.7, 0.6] },
                { position: [-1.5, 0.0, -1.0], rotation: 45.0, scale: 1.0, color: [0.8, 0.6, 0.5] }
            ]
        };
    }
    
    initRenderers() {
        if (!this.sceneData) return;
        
        this.threeRenderer = new ThreeJSRenderer(this.canvas, this.sceneData);
        this.shaderRenderer = new ShaderRenderer(this.canvas, this.sceneData);
        
        this.setMode(this.currentMode);
    }
    
    setMode(mode) {
        this.currentMode = mode;
        document.getElementById('mode-display').textContent = 
            mode === 'threejs' ? 'Three.js Preview' : 'Shader Ray Tracing';
        
        if (mode === 'threejs') {
            this.renderer = this.threeRenderer;
        } else {
            this.renderer = this.shaderRenderer;
        }
        
        if (this.renderer) {
            this.renderer.init();
            this.startRenderLoop();
        }
    }
    
    updateCamera() {
        if (!this.renderer) return;
        
        const rotX = parseFloat(document.getElementById('rot-x').value) * Math.PI / 180;
        const rotY = parseFloat(document.getElementById('rot-y').value) * Math.PI / 180;
        const dist = parseFloat(document.getElementById('distance').value);
        
        this.renderer.setCameraRotation(rotX, rotY, dist);
    }
    
    startRenderLoop() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        
        const render = (time) => {
            this.frameCount++;
            if (time - this.lastTime >= 1000) {
                this.fps = this.frameCount;
                this.frameCount = 0;
                this.lastTime = time;
                document.getElementById('fps').textContent = this.fps;
            }
            
            if (this.renderer) {
                this.renderer.render();
            }
            
            this.animationFrame = requestAnimationFrame(render);
        };
        
        this.lastTime = performance.now();
        this.animationFrame = requestAnimationFrame(render);
    }
}

// Start app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        new RayTracingApp();
    });
} else {
    new RayTracingApp();
}


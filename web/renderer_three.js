import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js';
import { OrbitControls } from 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js';

export class ThreeJSRenderer {
    constructor(canvas, sceneData) {
        this.canvas = canvas;
        this.sceneData = sceneData;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.humanMeshes = [];
        this.rotX = 0;
        this.rotY = 0;
        this.distance = 5.0;
        this.humanRotation = 0;
    }
    
    init() {
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1a2e);
        
        // Camera
        const aspect = this.canvas.width / this.canvas.height;
        this.camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1000);
        this.updateCameraPosition();
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ 
            canvas: this.canvas,
            antialias: true 
        });
        this.renderer.setSize(this.canvas.width, this.canvas.height);
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        // Controls
        this.controls = new OrbitControls(this.camera, this.canvas);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        this.controls.target.set(0, 1.5, 0);
        
        this.buildScene();
    }
    
    buildScene() {
        // Clear existing
        while(this.scene.children.length > 0) {
            this.scene.remove(this.scene.children[0]);
        }
        this.humanMeshes = [];
        
        const room = this.sceneData.room;
        const roomSize = room.size;
        const roomCenter = room.center;
        
        // Room walls (simplified - just show wireframe)
        const roomGeometry = new THREE.BoxGeometry(roomSize[0], roomSize[1], roomSize[2]);
        const roomEdges = new THREE.EdgesGeometry(roomGeometry);
        const roomLine = new THREE.LineSegments(
            roomEdges,
            new THREE.LineBasicMaterial({ color: 0x666666 })
        );
        roomLine.position.set(roomCenter[0], roomCenter[1], roomCenter[2]);
        this.scene.add(roomLine);
        
        // Floor
        const floorGeometry = new THREE.PlaneGeometry(roomSize[0], roomSize[2]);
        const floorMaterial = new THREE.MeshStandardMaterial({ 
            color: new THREE.Color(...room.floor_color || [0.6, 0.5, 0.4]),
            roughness: 0.8
        });
        const floor = new THREE.Mesh(floorGeometry, floorMaterial);
        floor.rotation.x = -Math.PI / 2;
        floor.position.set(roomCenter[0], roomCenter[1] - roomSize[1]/2, roomCenter[2]);
        floor.receiveShadow = true;
        this.scene.add(floor);
        
        // Ceiling
        const ceiling = new THREE.Mesh(floorGeometry, new THREE.MeshStandardMaterial({
            color: new THREE.Color(...room.ceiling_color || [0.9, 0.9, 0.95]),
            roughness: 0.8
        }));
        ceiling.rotation.x = Math.PI / 2;
        ceiling.position.set(roomCenter[0], roomCenter[1] + roomSize[1]/2, roomCenter[2]);
        this.scene.add(ceiling);
        
        // Walls
        const wallMaterial = new THREE.MeshStandardMaterial({
            color: new THREE.Color(...room.wall_color || [0.8, 0.8, 0.9]),
            roughness: 0.8
        });
        
        // Back wall
        const backWall = new THREE.Mesh(
            new THREE.PlaneGeometry(roomSize[0], roomSize[1]),
            wallMaterial
        );
        backWall.position.set(roomCenter[0], roomCenter[1], roomCenter[2] - roomSize[2]/2);
        this.scene.add(backWall);
        
        // Light source
        const light = this.sceneData.light;
        const lightPos = light.position;
        
        // Point light
        const pointLight = new THREE.PointLight(
            new THREE.Color(...light.color || [1.0, 0.95, 0.9]),
            light.intensity ? Math.max(...light.intensity) : 5.0,
            50
        );
        pointLight.position.set(lightPos[0], lightPos[1], lightPos[2]);
        pointLight.castShadow = true;
        pointLight.shadow.mapSize.width = 2048;
        pointLight.shadow.mapSize.height = 2048;
        this.scene.add(pointLight);
        
        // Light visual
        const lightGeometry = new THREE.SphereGeometry(light.radius, 16, 16);
        const lightMaterial = new THREE.MeshBasicMaterial({ 
            color: 0xffffaa,
            emissive: 0xffffaa
        });
        const lightMesh = new THREE.Mesh(lightGeometry, lightMaterial);
        lightMesh.position.set(lightPos[0], lightPos[1], lightPos[2]);
        this.scene.add(lightMesh);
        
        // Mirrors
        const mirrors = this.sceneData.mirrors || [];
        mirrors.forEach((mirror, i) => {
            const mirrorPos = mirror.position;
            const mirrorSize = mirror.size;
            
            const mirrorGeometry = new THREE.PlaneGeometry(mirrorSize[0], mirrorSize[1]);
            const mirrorMaterial = new THREE.MeshStandardMaterial({
                color: 0x888888,
                metalness: 0.9,
                roughness: 0.1,
                envMapIntensity: 1.0
            });
            
            const mirrorMesh = new THREE.Mesh(mirrorGeometry, mirrorMaterial);
            mirrorMesh.position.set(mirrorPos[0], mirrorPos[1], mirrorPos[2]);
            
            // Orient mirror based on normal
            const normal = new THREE.Vector3(...mirror.normal);
            mirrorMesh.lookAt(
                mirrorPos[0] + normal.x,
                mirrorPos[1] + normal.y,
                mirrorPos[2] + normal.z
            );
            
            this.scene.add(mirrorMesh);
        });
        
        // Human models
        const humanModels = this.sceneData.human_models || [];
        humanModels.forEach((human, i) => {
            this.createHumanModel(human);
        });
        
        // Ambient light
        const ambientLight = new THREE.AmbientLight(0x404040, 0.3);
        this.scene.add(ambientLight);
    }
    
    createHumanModel(human) {
        const pos = human.position;
        const scale = human.scale || 1.0;
        const color = new THREE.Color(...human.color);
        
        const group = new THREE.Group();
        group.position.set(pos[0], pos[1], pos[2]);
        
        // Torso (cylinder)
        const torsoGeometry = new THREE.CylinderGeometry(0.25 * scale, 0.25 * scale, 0.8 * scale, 16);
        const torsoMaterial = new THREE.MeshStandardMaterial({ 
            color: color,
            roughness: 0.7
        });
        const torso = new THREE.Mesh(torsoGeometry, torsoMaterial);
        torso.position.y = 0.4 * scale;
        torso.castShadow = true;
        torso.receiveShadow = true;
        group.add(torso);
        
        // Head (sphere)
        const headGeometry = new THREE.SphereGeometry(0.15 * scale, 16, 16);
        const headMaterial = new THREE.MeshStandardMaterial({ 
            color: color,
            roughness: 0.7
        });
        const head = new THREE.Mesh(headGeometry, headMaterial);
        head.position.y = 1.1 * scale;
        head.castShadow = true;
        group.add(head);
        
        // Arms (simplified - cylinders)
        const armGeometry = new THREE.CylinderGeometry(0.08 * scale, 0.08 * scale, 0.6 * scale, 8);
        const armMaterial = new THREE.MeshStandardMaterial({ color: color, roughness: 0.7 });
        
        const leftArm = new THREE.Mesh(armGeometry, armMaterial);
        leftArm.position.set(-0.35 * scale, 0.5 * scale, 0);
        leftArm.rotation.z = Math.PI / 6;
        leftArm.castShadow = true;
        group.add(leftArm);
        
        const rightArm = new THREE.Mesh(armGeometry, armMaterial);
        rightArm.position.set(0.35 * scale, 0.5 * scale, 0);
        rightArm.rotation.z = -Math.PI / 6;
        rightArm.castShadow = true;
        group.add(rightArm);
        
        // Legs
        const legGeometry = new THREE.CylinderGeometry(0.1 * scale, 0.1 * scale, 0.7 * scale, 8);
        const legMaterial = new THREE.MeshStandardMaterial({ color: color, roughness: 0.7 });
        
        const leftLeg = new THREE.Mesh(legGeometry, legMaterial);
        leftLeg.position.set(-0.15 * scale, -0.35 * scale, 0);
        leftLeg.castShadow = true;
        group.add(leftLeg);
        
        const rightLeg = new THREE.Mesh(legGeometry, legMaterial);
        rightLeg.position.set(0.15 * scale, -0.35 * scale, 0);
        rightLeg.castShadow = true;
        group.add(rightLeg);
        
        this.humanMeshes.push(group);
        this.scene.add(group);
    }
    
    updateCameraPosition() {
        const rotX = this.rotX;
        const rotY = this.rotY;
        const dist = this.distance;
        
        const x = Math.sin(rotY) * Math.cos(rotX) * dist;
        const y = Math.sin(rotX) * dist + 1.5;
        const z = Math.cos(rotY) * Math.cos(rotX) * dist;
        
        this.camera.position.set(x, y, z);
        this.camera.lookAt(0, 1.5, 0);
    }
    
    setCameraRotation(rotX, rotY, distance) {
        this.rotX = rotX;
        this.rotY = rotY;
        this.distance = distance;
        this.updateCameraPosition();
    }
    
    setHumanRotation(angle) {
        this.humanRotation = angle * Math.PI / 180;
        this.humanMeshes.forEach(mesh => {
            mesh.rotation.y = this.humanRotation;
        });
    }
    
    resize(width, height) {
        if (this.camera) {
            this.camera.aspect = width / height;
            this.camera.updateProjectionMatrix();
        }
        if (this.renderer) {
            this.renderer.setSize(width, height);
        }
    }
    
    render() {
        if (this.controls) {
            this.controls.update();
        }
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }
}


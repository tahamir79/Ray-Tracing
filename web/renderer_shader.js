export class ShaderRenderer {
    constructor(canvas, sceneData) {
        this.canvas = canvas;
        this.sceneData = sceneData;
        this.gl = null;
        this.program = null;
        this.maxBounces = 4;
        this.resolutionScale = 1.0;
        this.rotX = 0;
        this.rotY = 0;
        this.distance = 5.0;
    }
    
    init() {
        this.gl = this.canvas.getContext('webgl2') || this.canvas.getContext('webgl');
        if (!this.gl) {
            console.error('WebGL not supported');
            return;
        }
        
        // For now, fallback to a simple shader-based renderer
        // Full ray tracing shader would be more complex
        this.setupSimpleShader();
    }
    
    setupSimpleShader() {
        const gl = this.gl;
        
        // Vertex shader
        const vsSource = `
            attribute vec2 a_position;
            varying vec2 v_uv;
            void main() {
                gl_Position = vec4(a_position, 0.0, 1.0);
                v_uv = (a_position + 1.0) * 0.5;
            }
        `;
        
        // Fragment shader - simplified ray marching
        const fsSource = `
            precision highp float;
            uniform vec2 u_resolution;
            uniform float u_time;
            uniform vec3 u_cameraPos;
            uniform vec3 u_cameraTarget;
            uniform float u_fov;
            uniform int u_maxBounces;
            
            varying vec2 v_uv;
            
            // Scene data
            uniform vec3 u_lightPos;
            uniform float u_lightRadius;
            uniform vec3 u_lightIntensity;
            
            // Room bounds
            uniform vec3 u_roomMin;
            uniform vec3 u_roomMax;
            
            // SDF functions
            float sdBox(vec3 p, vec3 b) {
                vec3 q = abs(p) - b;
                return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
            }
            
            float sdSphere(vec3 p, float r) {
                return length(p) - r;
            }
            
            float sdCylinder(vec3 p, float r, float h) {
                float d = length(p.xz) - r;
                return max(d, abs(p.y) - h * 0.5);
            }
            
            // Scene SDF
            float sceneSDF(vec3 p) {
                // Room (inverted - we're inside)
                float room = -sdBox(p - vec3(0.0, 3.0, 0.0), vec3(4.0, 3.0, 4.0));
                
                // Light
                float light = sdSphere(p - u_lightPos, u_lightRadius);
                
                // Human model (simplified)
                vec3 humanPos = vec3(1.5, 0.0, 1.0);
                vec3 pHuman = p - humanPos;
                float torso = sdCylinder(pHuman - vec3(0.0, 0.4, 0.0), 0.25, 0.8);
                float head = sdSphere(pHuman - vec3(0.0, 1.1, 0.0), 0.15);
                float human = min(torso, head);
                
                return min(min(room, light), human);
            }
            
            vec3 estimateNormal(vec3 p) {
                float eps = 0.001;
                return normalize(vec3(
                    sceneSDF(vec3(p.x + eps, p.y, p.z)) - sceneSDF(vec3(p.x - eps, p.y, p.z)),
                    sceneSDF(vec3(p.x, p.y + eps, p.z)) - sceneSDF(vec3(p.x, p.y - eps, p.z)),
                    sceneSDF(vec3(p.x, p.y, p.z + eps)) - sceneSDF(vec3(p.x, p.y, p.z - eps))
                ));
            }
            
            vec3 trace(vec3 ro, vec3 rd) {
                float t = 0.0;
                for (int i = 0; i < 100; i++) {
                    vec3 p = ro + rd * t;
                    float d = sceneSDF(p);
                    if (d < 0.001) {
                        vec3 n = estimateNormal(p);
                        vec3 toLight = normalize(u_lightPos - p);
                        float ndotl = max(dot(n, toLight), 0.0);
                        return vec3(0.8, 0.7, 0.6) * (0.1 + 0.9 * ndotl);
                    }
                    t += d;
                    if (t > 100.0) break;
                }
                // Sky
                float t_sky = 0.5 * (rd.y + 1.0);
                return mix(vec3(0.1, 0.12, 0.15), vec3(0.3, 0.4, 0.5), t_sky);
            }
            
            void main() {
                vec2 uv = v_uv;
                vec2 coord = (uv - 0.5) * 2.0;
                coord.x *= u_resolution.x / u_resolution.y;
                
                vec3 ro = u_cameraPos;
                vec3 forward = normalize(u_cameraTarget - u_cameraPos);
                vec3 right = normalize(cross(forward, vec3(0.0, 1.0, 0.0)));
                vec3 up = cross(right, forward);
                
                float fov = u_fov * 3.14159 / 180.0;
                float scale = tan(fov * 0.5);
                
                vec3 rd = normalize(forward + right * coord.x * scale + up * coord.y * scale);
                
                vec3 color = trace(ro, rd);
                
                gl_FragColor = vec4(color, 1.0);
            }
        `;
        
        const vertexShader = this.compileShader(gl.VERTEX_SHADER, vsSource);
        const fragmentShader = this.compileShader(gl.FRAGMENT_SHADER, fsSource);
        
        if (!vertexShader || !fragmentShader) {
            console.error('Shader compilation failed');
            return;
        }
        
        this.program = this.createProgram(vertexShader, fragmentShader);
        if (!this.program) {
            console.error('Program creation failed');
            return;
        }
        
        // Setup quad
        const positionBuffer = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
            -1, -1,  1, -1,  -1, 1,
            -1, 1,   1, -1,   1, 1
        ]), gl.STATIC_DRAW);
    }
    
    compileShader(type, source) {
        const gl = this.gl;
        const shader = gl.createShader(type);
        gl.shaderSource(shader, source);
        gl.compileShader(shader);
        
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
            console.error('Shader compile error:', gl.getShaderInfoLog(shader));
            gl.deleteShader(shader);
            return null;
        }
        
        return shader;
    }
    
    createProgram(vertexShader, fragmentShader) {
        const gl = this.gl;
        const program = gl.createProgram();
        gl.attachShader(program, vertexShader);
        gl.attachShader(program, fragmentShader);
        gl.linkProgram(program);
        
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
            console.error('Program link error:', gl.getProgramInfoLog(program));
            gl.deleteProgram(program);
            return null;
        }
        
        return program;
    }
    
    setMaxBounces(bounces) {
        this.maxBounces = bounces;
    }
    
    setResolutionScale(scale) {
        this.resolutionScale = scale;
    }
    
    setCameraRotation(rotX, rotY, distance) {
        this.rotX = rotX;
        this.rotY = rotY;
        this.distance = distance;
    }
    
    setHumanRotation(angle) {
        // Update shader uniform if needed
    }
    
    resize(width, height) {
        this.canvas.width = width;
        this.canvas.height = height;
        if (this.gl) {
            this.gl.viewport(0, 0, width, height);
        }
    }
    
    render() {
        if (!this.gl || !this.program) {
            // Fallback: draw a simple gradient
            const ctx = this.canvas.getContext('2d');
            const gradient = ctx.createLinearGradient(0, 0, this.canvas.width, this.canvas.height);
            gradient.addColorStop(0, '#1a1a2e');
            gradient.addColorStop(1, '#16213e');
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            ctx.fillStyle = '#fff';
            ctx.font = '20px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('Shader Ray Tracing (WebGL setup in progress)', 
                        this.canvas.width / 2, this.canvas.height / 2);
            return;
        }
        
        const gl = this.gl;
        
        // Calculate camera position
        const x = Math.sin(this.rotY) * Math.cos(this.rotX) * this.distance;
        const y = Math.sin(this.rotX) * this.distance + 1.5;
        const z = Math.cos(this.rotY) * Math.cos(this.rotX) * this.distance;
        const camPos = [x, y, z];
        const camTarget = [0, 1.5, 0];
        
        gl.useProgram(this.program);
        
        // Set uniforms
        const resolutionLoc = gl.getUniformLocation(this.program, 'u_resolution');
        const timeLoc = gl.getUniformLocation(this.program, 'u_time');
        const camPosLoc = gl.getUniformLocation(this.program, 'u_cameraPos');
        const camTargetLoc = gl.getUniformLocation(this.program, 'u_cameraTarget');
        const fovLoc = gl.getUniformLocation(this.program, 'u_fov');
        
        gl.uniform2f(resolutionLoc, this.canvas.width, this.canvas.height);
        gl.uniform1f(timeLoc, performance.now() / 1000.0);
        gl.uniform3f(camPosLoc, camPos[0], camPos[1], camPos[2]);
        gl.uniform3f(camTargetLoc, camTarget[0], camTarget[1], camTarget[2]);
        gl.uniform1f(fovLoc, this.sceneData.camera.fov);
        
        // Set attributes
        const positionLoc = gl.getAttribLocation(this.program, 'a_position');
        gl.enableVertexAttribArray(positionLoc);
        gl.bindBuffer(gl.ARRAY_BUFFER, gl.getParameter(gl.ARRAY_BUFFER_BINDING));
        gl.vertexAttribPointer(positionLoc, 2, gl.FLOAT, false, 0, 0);
        
        gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
}


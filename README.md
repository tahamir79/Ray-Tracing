# Ray Tracing App with Mirrors and Human Models

An interactive ray tracing application featuring:
- **3D Room**: A cube-shaped room with walls, floor, and ceiling
- **Mirrors**: Reflective surfaces that show accurate ray-traced reflections
- **Human Models**: Simplified geometric human figures (torso, head, limbs)
- **Light Source**: Point light in the corner of the room
- **Interactive Viewer**: Real-time 3D preview and shader-based rendering

## Project Structure

```
.
├── scene.json              # Scene configuration (single source of truth)
├── python/
│   ├── scene.py            # Scene loading and validation
│   ├── raytrace_cpu.py     # CPU ray tracer with mirrors
│   └── preview_plotly.py   # Interactive 3D preview
├── web/
│   ├── index.html          # Web viewer UI
│   ├── main.js             # Main application logic
│   ├── renderer_three.js   # Three.js raster preview
│   └── renderer_shader.js  # Shader-based ray tracing
└── README.md
```

## Quick Start

### Python CPU Ray Tracer

1. Install dependencies:
```bash
pip install pillow plotly
```

2. Run the ray tracer:
```bash
cd python
python raytrace_cpu.py
```

This will generate `render.png` in the project root.

3. Preview the scene geometry:
```bash
python preview_plotly.py
```

### Web Viewer

1. Install dependencies:
```bash
cd web
npm install
```

2. Start the dev server:
```bash
npm run dev
```

3. Open your browser to `http://localhost:3000`

## Scene Configuration

Edit `scene.json` to customize:

- **Camera**: Position, look target, field of view
- **Room**: Size, center, wall/floor/ceiling colors
- **Light**: Position, radius, intensity, color
- **Mirrors**: Position, normal, size, reflectivity
- **Human Models**: Position, rotation, scale, color
- **Render Settings**: Resolution, samples, max bounces

## Features

### Ray Tracing Features
- ✅ Recursive reflections (configurable max bounces)
- ✅ Shadows (hard shadows from light source)
- ✅ Lambertian shading
- ✅ Tone mapping (Reinhard)
- ✅ Gamma correction

### Geometry
- ✅ Room (AABB intersection)
- ✅ Mirrors (plane intersection with reflections)
- ✅ Human models (cylinder torso + sphere head)
- ✅ Light source (emissive sphere)

### Interactive Viewer
- ✅ Three.js raster preview (fast, reliable)
- ✅ Camera rotation and distance controls
- ✅ Human model rotation
- ✅ Real-time FPS display
- 🔄 Shader ray tracing (in progress)

## Next Steps

1. **GPU Acceleration**: Port to Taichi or PyTorch for Colab GPU rendering
2. **Enhanced Shader**: Complete WebGL/WebGPU shader ray tracer
3. **Better Models**: Add more detailed human geometry or OBJ loading
4. **Materials**: Add more material types (glass, metal, etc.)
5. **Anti-aliasing**: Multi-sampling for smoother renders

## Notes

- The Python CPU ray tracer is single-threaded and can be slow for high resolutions
- For GPU acceleration, use Colab with Taichi (see Phase 2 in original plan)
- The web viewer uses Three.js for fast preview; shader ray tracing is being developed
- Mirrors show accurate reflections up to `max_bounces` depth


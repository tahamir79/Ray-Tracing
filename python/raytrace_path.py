"""
Ray Path Visualization - Trace individual light rays from source to show their paths.
Shows proper light attenuation and beam deflection behavior.
"""
import json
import math
from PIL import Image, ImageDraw
from typing import Tuple, Optional, List, Dict, Any
from raytrace_cpu import (
    add, sub, mul, dot, length, norm, reflect, clamp01,
    ray_aabb, ray_sphere, ray_plane, ray_cylinder,
    Scene, load_scene, validate_scene
)

class RayPath:
    """Represents a traced ray path with segments and energy."""
    def __init__(self):
        self.segments: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], float]] = []
        # Each segment: (start_pos, end_pos, energy_attenuation)
        self.energy_history: List[float] = []  # Energy at each bounce
    
    def add_segment(self, start: Tuple[float, float, float], 
                   end: Tuple[float, float, float], energy: float):
        self.segments.append((start, end, energy))
        self.energy_history.append(energy)

def trace_ray_path(scene: Scene, start_pos: Tuple[float, float, float],
                   start_dir: Tuple[float, float, float],
                   max_bounces: int = 10,
                   initial_energy: float = 1.0,
                   attenuation_per_bounce: float = 0.85) -> RayPath:
    """
    Trace a ray from start position and record its complete path.
    
    Args:
        scene: Scene to trace through
        start_pos: Starting position of ray
        start_dir: Starting direction (normalized)
        max_bounces: Maximum number of bounces
        initial_energy: Starting energy (1.0 = full intensity)
        attenuation_per_bounce: Energy loss per bounce (0.85 = 15% loss)
    
    Returns:
        RayPath object with all segments
    """
    path = RayPath()
    ro = start_pos
    rd = norm(start_dir)
    energy = initial_energy
    bounce = 0
    
    # Add initial point
    path.energy_history.append(energy)
    
    while bounce < max_bounces and energy > 0.01:  # Stop if energy too low
        # Find nearest intersection
        nearest_t = None
        nearest_n = None
        nearest_material = None
        nearest_reflectivity = 0.0
        
        # Room walls
        t_room, n_room = ray_aabb(ro, rd, scene.room_min, scene.room_max)
        if t_room is not None:
            nearest_t = t_room
            nearest_n = n_room
            nearest_material = "room"
            nearest_reflectivity = 0.0
        
        # Light source (skip if we're starting from it)
        light_pos = tuple(scene.light["position"])
        light_radius = scene.light["radius"]
        if length(sub(ro, light_pos)) > light_radius * 1.1:  # Not starting from light
            t_light, n_light = ray_sphere(ro, rd, light_pos, light_radius)
            if t_light is not None and (nearest_t is None or t_light < nearest_t):
                # Hit light source - terminate
                hit = add(ro, mul(rd, t_light))
                path.add_segment(ro, hit, energy)
                break
        
        # Mirrors
        for mirror in scene.mirrors:
            t_mirror, n_mirror = scene.intersect_mirror(ro, rd, mirror)
            if t_mirror is not None and (nearest_t is None or t_mirror < nearest_t):
                nearest_t = t_mirror
                nearest_n = n_mirror
                nearest_material = "mirror"
                nearest_reflectivity = mirror.get("reflectivity", 0.95)
        
        # Human models
        for human in scene.human_models:
            t_human, n_human, part = scene.intersect_human(ro, rd, human)
            if t_human is not None and (nearest_t is None or t_human < nearest_t):
                nearest_t = t_human
                nearest_n = n_human
                nearest_material = "human"
                nearest_reflectivity = 0.0  # Diffuse, no reflection
        
        if nearest_t is None:
            # Ray escaped to sky
            hit = add(ro, mul(rd, 100.0))  # Far point
            path.add_segment(ro, hit, energy)
            break
        
        hit = add(ro, mul(rd, nearest_t))
        path.add_segment(ro, hit, energy)
        
        # Apply attenuation based on bounce count
        # After 6 bounces, start phasing out more aggressively
        if bounce >= 6:
            # Exponential decay after 6 bounces
            fade_factor = math.exp(-(bounce - 6) * 0.3)
            energy *= attenuation_per_bounce * fade_factor
        else:
            # Normal attenuation
            energy *= attenuation_per_bounce
        
        # If hitting mirror, reflect and continue
        if nearest_reflectivity > 0.01:
            reflected_rd = reflect(rd, nearest_n)
            ro = add(hit, mul(nearest_n, 1e-4))  # Offset to avoid self-intersection
            rd = reflected_rd
            bounce += 1
            # Continue tracing (don't break)
        elif nearest_material == "room":
            # Wall reflection - continue for visualization (exaggerated path)
            reflected_rd = reflect(rd, nearest_n)
            ro = add(hit, mul(nearest_n, 1e-4))
            rd = reflected_rd
            bounce += 1
            # Reduce energy more on wall bounce (walls are less reflective)
            energy *= 0.75
            # Continue tracing
        else:
            # Hit human or other diffuse object - ray stops
            break
    
    return path

def render_with_ray_path(scene_data: Dict[str, Any], 
                         ray_start: Tuple[float, float, float],
                         ray_dir: Tuple[float, float, float],
                         output_path: str = "render_path.png") -> None:
    """
    Render scene with a highlighted ray path visualization.
    """
    scene = Scene(scene_data)
    
    cam = scene_data["camera"]
    render_settings = scene_data["render"]
    
    W = render_settings["width"]
    H = render_settings["height"]
    fov = cam["fov"]
    aspect = W / H
    max_bounces = render_settings.get("max_bounces", 4)
    
    cam_pos = tuple(cam["position"])
    look_at = tuple(cam["look_at"])
    
    # Camera basis
    forward = norm(sub(look_at, cam_pos))
    world_up = (0.0, 1.0, 0.0)
    
    right = norm((
        forward[1] * world_up[2] - forward[2] * world_up[1],
        forward[2] * world_up[0] - forward[0] * world_up[2],
        forward[0] * world_up[1] - forward[1] * world_up[0]
    ))
    
    if length(right) < 0.1:
        right = (1.0, 0.0, 0.0) if abs(forward[0]) < 0.9 else (0.0, 0.0, 1.0)
        right = norm(right)
    
    up = norm((
        right[1] * forward[2] - right[2] * forward[1],
        right[2] * forward[0] - right[0] * forward[2],
        right[0] * forward[1] - right[1] * forward[0]
    ))
    
    scale = math.tan(math.radians(fov * 0.5))
    
    # First render normal scene
    img = Image.new("RGB", (W, H), color=(10, 12, 15))
    pix = img.load()
    draw = ImageDraw.Draw(img)
    
    print(f"Rendering {W}x{H} scene with ray path visualization...")
    
    # Trace the specific ray path
    ray_path = trace_ray_path(scene, ray_start, ray_dir, max_bounces=10, 
                              initial_energy=1.0, attenuation_per_bounce=0.88)
    
    print(f"Ray path traced: {len(ray_path.segments)} segments, "
          f"final energy: {ray_path.energy_history[-1]:.3f}")
    
    # Render normal scene (simplified for path visualization)
    for y in range(H):
        if y % 100 == 0:
            print(f"Progress: {y}/{H} ({100*y//H}%)")
        
        py = (1.0 - 2.0 * (y + 0.5) / H) * scale
        for x in range(W):
            px = (2.0 * (x + 0.5) / W - 1.0) * scale * aspect
            
            rd = norm(add(add(mul(right, px), mul(up, py)), forward))
            
            # Simple scene rendering (can use full trace if needed)
            color = scene.trace(cam_pos, rd, max_bounces)
            color = (color[0] / (1.0 + color[0]), 
                    color[1] / (1.0 + color[1]), 
                    color[2] / (1.0 + color[2]))
            inv_gamma = 1.0 / 2.2
            color = (pow(clamp01(color[0]), inv_gamma),
                    pow(clamp01(color[1]), inv_gamma),
                    pow(clamp01(color[2]), inv_gamma))
            
            r = int(clamp01(color[0]) * 255)
            g = int(clamp01(color[1]) * 255)
            b = int(clamp01(color[2]) * 255)
            
            pix[x, y] = (r, g, b)
    
    # Project ray path segments onto image
    # Simple perspective projection
    def project_point(p3d: Tuple[float, float, float]) -> Optional[Tuple[int, int]]:
        """Project 3D point to 2D screen coordinates."""
        # Vector from camera to point
        to_point = sub(p3d, cam_pos)
        proj_dist = dot(to_point, forward)
        
        if proj_dist < 0.1:  # Behind camera
            return None
        
        # Project onto camera plane
        proj_point = add(cam_pos, mul(forward, proj_dist))
        offset = sub(p3d, proj_point)
        
        # Convert to screen space
        screen_x = dot(offset, right) / proj_dist / scale
        screen_y = -dot(offset, up) / proj_dist / scale  # Negative for correct Y
        
        # Convert to pixel coordinates
        px = int((screen_x + 1.0) * 0.5 * W)
        py = int((screen_y + 1.0) * 0.5 * H)
        
        if 0 <= px < W and 0 <= py < H:
            return (px, py)
        return None
    
    # Draw ray path segments with energy-based color/intensity
    for i, (start, end, energy) in enumerate(ray_path.segments):
        start_2d = project_point(start)
        end_2d = project_point(end)
        
        if start_2d and end_2d:
            # Color based on energy: bright yellow/white when high, fading to red/orange
            if energy > 0.7:
                color = (255, 255, 200)  # Bright yellow-white
            elif energy > 0.4:
                color = (255, 200, 100)  # Yellow-orange
            elif energy > 0.2:
                color = (255, 150, 50)   # Orange
            else:
                color = (200, 100, 50)    # Red-orange (fading)
            
            # Line width based on energy
            width = max(1, int(energy * 3))
            
            # Draw line segment
            draw.line([start_2d, end_2d], fill=color, width=width)
            
            # Draw point at end of segment
            if i < len(ray_path.segments) - 1:  # Not the last segment
                draw.ellipse([end_2d[0]-2, end_2d[1]-2, end_2d[0]+2, end_2d[1]+2], 
                           fill=color, outline=color)
    
    # Highlight light source position
    light_pos_2d = project_point(tuple(scene.light["position"]))
    if light_pos_2d:
        # Draw bright glow for light source
        for radius in [8, 6, 4]:
            alpha = 255 if radius == 4 else 180
            draw.ellipse([light_pos_2d[0]-radius, light_pos_2d[1]-radius,
                         light_pos_2d[0]+radius, light_pos_2d[1]+radius],
                        fill=(255, 255, 200, alpha), outline=(255, 255, 150))
    
    img.save(output_path)
    print(f"Saved ray path visualization: {output_path}")

if __name__ == "__main__":
    import os
    from datetime import datetime
    
    scene_path = "../scene.json" if os.path.exists("../scene.json") else "scene.json"
    scene_data = load_scene(scene_path)
    validate_scene(scene_data)
    
    renders_dir = "../renders" if os.path.exists("../scene.json") else "renders"
    os.makedirs(renders_dir, exist_ok=True)
    
    # Start ray from light source
    light_pos = tuple(scene_data["light"]["position"])
    
    # Create an interesting ray path: from light, toward mirror, then bouncing
    # This will show multiple reflections
    mirror_pos = tuple(scene_data["mirrors"][0]["position"])
    
    # Ray direction from light toward mirror (will bounce and create interesting path)
    # Offset slightly to create a path that bounces around
    target = (mirror_pos[0] + 0.3, mirror_pos[1] + 0.2, mirror_pos[2] + 0.1)
    ray_dir = norm(sub(target, light_pos))
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"raypath_{timestamp}.png"
    output_path = os.path.join(renders_dir, filename)
    
    render_with_ray_path(scene_data, light_pos, ray_dir, output_path)


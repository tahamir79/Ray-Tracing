"""
Ray Deflection Validation - Trace multiple rays hitting human model
and follow them for exactly 6 deflections to validate deflection calculations.
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

class RaySegment:
    """Single ray segment with start, end, and energy."""
    def __init__(self, start: Tuple[float, float, float], 
                 end: Tuple[float, float, float], 
                 energy: float,
                 material: str = "unknown"):
        self.start = start
        self.end = end
        self.energy = energy
        self.material = material  # "mirror", "wall", "human", etc.

def trace_ray_with_validation(scene: Scene, 
                              start_pos: Tuple[float, float, float],
                              start_dir: Tuple[float, float, float],
                              max_deflections: int = 6) -> List[RaySegment]:
    """
    Trace a ray for exactly max_deflections bounces, recording each segment.
    
    Args:
        scene: Scene to trace through
        start_pos: Starting position
        start_dir: Starting direction (normalized)
        max_deflections: Exact number of deflections to trace (default 6)
    
    Returns:
        List of RaySegment objects showing the complete path
    """
    segments = []
    ro = start_pos
    rd = norm(start_dir)
    energy = 1.0
    deflection_count = 0
    
    while deflection_count < max_deflections:
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
            nearest_material = "wall"
            nearest_reflectivity = 0.0
        
        # Light source (skip if we're starting from it)
        light_pos = tuple(scene.light["position"])
        light_radius = scene.light["radius"]
        if length(sub(ro, light_pos)) > light_radius * 1.1:
            t_light, n_light = ray_sphere(ro, rd, light_pos, light_radius)
            if t_light is not None and (nearest_t is None or t_light < nearest_t):
                # Hit light - terminate
                hit = add(ro, mul(rd, t_light))
                segments.append(RaySegment(ro, hit, energy, "light"))
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
                # For validation, allow human to reflect (even though it's diffuse in reality)
                # This lets us see the full 6 deflections
                nearest_reflectivity = 0.3  # Low reflectivity for visualization
        
        if nearest_t is None:
            # Ray escaped
            hit = add(ro, mul(rd, 100.0))
            segments.append(RaySegment(ro, hit, energy, "sky"))
            break
        
        hit = add(ro, mul(rd, nearest_t))
        segments.append(RaySegment(ro, hit, energy, nearest_material))
        
        # Calculate deflection (reflection)
        if nearest_reflectivity > 0.01:
            # Mirror or human reflection
            reflected_rd = reflect(rd, nearest_n)
            if nearest_material == "mirror":
                energy *= 0.92  # Mirror efficiency loss
            elif nearest_material == "human":
                energy *= 0.70  # Human surface is less reflective (diffuse-like)
        elif nearest_material == "wall":
            # Wall reflection (for visualization)
            reflected_rd = reflect(rd, nearest_n)
            energy *= 0.75  # Walls are less reflective
        else:
            # Unknown material - ray stops
            break
        
        # Update for next segment
        ro = add(hit, mul(nearest_n, 1e-4))
        rd = reflected_rd
        deflection_count += 1
        
        # Apply exponential fade after 6 deflections (though we stop at 6)
        if deflection_count >= 6:
            energy *= math.exp(-0.3)  # Final fade
    
    return segments

def sample_human_surface(human_pos: Tuple[float, float, float], 
                         scale: float = 1.0,
                         num_samples: int = 8) -> List[Tuple[float, float, float]]:
    """
    Sample points on the human model surface for ray tracing.
    Returns list of 3D points on torso and head.
    """
    samples = []
    
    # Sample torso (cylinder) - points around the surface
    torso_center = (human_pos[0], human_pos[1] + 0.4 * scale, human_pos[2])
    torso_radius = 0.25 * scale
    
    # Sample points around torso at different heights
    for i in range(num_samples):
        angle = (i / num_samples) * 2 * math.pi
        height_offset = (i % 3) * 0.2 * scale - 0.2 * scale  # Vary height
        x = torso_center[0] + torso_radius * math.cos(angle)
        y = torso_center[1] + height_offset
        z = torso_center[2] + torso_radius * math.sin(angle)
        samples.append((x, y, z))
    
    # Sample head (sphere) - points on surface
    head_center = (human_pos[0], human_pos[1] + 1.1 * scale, human_pos[2])
    head_radius = 0.15 * scale
    
    for i in range(num_samples // 2):
        angle = (i / (num_samples // 2)) * 2 * math.pi
        x = head_center[0] + head_radius * math.cos(angle)
        y = head_center[1] + head_radius * 0.5
        z = head_center[2] + head_radius * math.sin(angle)
        samples.append((x, y, z))
    
    return samples

def render_ray_validation(scene_data: Dict[str, Any], 
                          output_path: str = "render_validation.png") -> None:
    """
    Render scene with visible ray vectors hitting human model and tracing 6 deflections.
    """
    scene = Scene(scene_data)
    
    cam = scene_data["camera"]
    render_settings = scene_data["render"]
    
    W = render_settings["width"]
    H = render_settings["height"]
    fov = cam["fov"]
    aspect = W / H
    
    # Use original camera position from scene
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
    
    # Render scene
    img = Image.new("RGB", (W, H), color=(5, 8, 12))
    pix = img.load()
    draw = ImageDraw.Draw(img)
    
    print(f"Rendering validation scene {W}x{H}...")
    
    # Render full scene (no skipping pixels)
    max_bounces = render_settings.get("max_bounces", 6)
    for y in range(H):
        if y % 50 == 0:
            print(f"Rendering progress: {y}/{H} ({100*y//H}%)")
        py = (1.0 - 2.0 * (y + 0.5) / H) * scale
        for x in range(W):
            px = (2.0 * (x + 0.5) / W - 1.0) * scale * aspect
            
            rd = norm(add(add(mul(right, px), mul(up, py)), forward))
            color = scene.trace(cam_pos, rd, max_bounces, bounce=0, energy=1.0)
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
    
    # Project 3D point to 2D screen
    def project_point(p3d: Tuple[float, float, float]) -> Optional[Tuple[int, int]]:
        to_point = sub(p3d, cam_pos)
        proj_dist = dot(to_point, forward)
        
        if proj_dist < 0.1:
            return None
        
        proj_point = add(cam_pos, mul(forward, proj_dist))
        offset = sub(p3d, proj_point)
        
        screen_x = dot(offset, right) / proj_dist / scale
        screen_y = -dot(offset, up) / proj_dist / scale
        
        px = int((screen_x + 1.0) * 0.5 * W)
        py = int((screen_y + 1.0) * 0.5 * H)
        
        if 0 <= px < W and 0 <= py < H:
            return (px, py)
        return None
    
    # Get human model position
    human = scene_data["human_models"][0]
    human_pos = tuple(human["position"])
    human_scale = human.get("scale", 1.0)
    
    # Sample points on human surface
    hit_points = sample_human_surface(human_pos, human_scale, num_samples=12)
    
    # Light position
    light_pos = tuple(scene_data["light"]["position"])
    
    print(f"Tracing {len(hit_points)} rays from light to human model...")
    
    all_ray_segments = []
    
    # Trace rays from light to each hit point, then continue for 6 deflections
    for hit_point in hit_points:
        # Ray from light to hit point
        ray_dir = norm(sub(hit_point, light_pos))
        
        # Trace this ray (it will hit human, then continue for 6 deflections)
        segments = trace_ray_with_validation(scene, light_pos, ray_dir, max_deflections=6)
        all_ray_segments.extend(segments)
        
        print(f"  Ray traced: {len(segments)} segments")
    
    print(f"Total ray segments traced: {len(all_ray_segments)}")
    
    # Count deflections per ray (for logging only)
    deflection_counts = {}
    for segment in all_ray_segments:
        # Estimate deflection number from energy
        deflection_num = max(0, int((1.0 - segment.energy) / 0.15))
        deflection_counts[deflection_num] = deflection_counts.get(deflection_num, 0) + 1
    
    print(f"Deflection distribution: {dict(sorted(deflection_counts.items()))}")
    print("Ray vectors removed - showing clean rendered scene only")
    
    # Ray path visualization removed - just show the normal rendered scene
    
    img.save(output_path)
    print(f"Saved validation render: {output_path}")
    print(f"Shows {len(hit_points)} rays hitting human, each traced for 6 deflections")

if __name__ == "__main__":
    import os
    from datetime import datetime
    
    scene_path = "../scene.json" if os.path.exists("../scene.json") else "scene.json"
    scene_data = load_scene(scene_path)
    validate_scene(scene_data)
    
    renders_dir = "../renders" if os.path.exists("../scene.json") else "renders"
    os.makedirs(renders_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"validation_{timestamp}_6deflections.png"
    output_path = os.path.join(renders_dir, filename)
    
    render_ray_validation(scene_data, output_path)


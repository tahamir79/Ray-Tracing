"""
CPU Ray Tracer with mirrors, room, and human models.
Supports recursive reflections up to max_bounces.
"""
import json
import math
from PIL import Image
from typing import Tuple, Optional, List, Dict, Any
from scene import load_scene, validate_scene

# Vector math utilities
def add(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])

def sub(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

def mul(a: Tuple[float, float, float], s: float) -> Tuple[float, float, float]:
    return (a[0] * s, a[1] * s, a[2] * s)

def dot(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def length(v: Tuple[float, float, float]) -> float:
    return math.sqrt(dot(v, v))

def norm(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    l = length(v)
    if l < 1e-8:
        return (0.0, 0.0, 0.0)
    return mul(v, 1.0 / l)

def reflect(rd: Tuple[float, float, float], n: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Reflect ray direction rd off surface with normal n."""
    return sub(rd, mul(n, 2.0 * dot(rd, n)))

def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))

# Ray intersection functions
def ray_aabb(ro: Tuple[float, float, float], rd: Tuple[float, float, float],
             bmin: Tuple[float, float, float], bmax: Tuple[float, float, float]) -> Tuple[Optional[float], Optional[Tuple[float, float, float]]]:
    """Ray-Axis Aligned Bounding Box intersection."""
    inv_rd = (1.0 / rd[0] if abs(rd[0]) > 1e-8 else 1e8,
              1.0 / rd[1] if abs(rd[1]) > 1e-8 else 1e8,
              1.0 / rd[2] if abs(rd[2]) > 1e-8 else 1e8)
    
    t0 = ((bmin[0] - ro[0]) * inv_rd[0], (bmin[1] - ro[1]) * inv_rd[1], (bmin[2] - ro[2]) * inv_rd[2])
    t1 = ((bmax[0] - ro[0]) * inv_rd[0], (bmax[1] - ro[1]) * inv_rd[1], (bmax[2] - ro[2]) * inv_rd[2])
    
    tmin = max(min(t0[0], t1[0]), min(t0[1], t1[1]), min(t0[2], t1[2]))
    tmax = min(max(t0[0], t1[0]), max(t0[1], t1[1]), max(t0[2], t1[2]))
    
    if tmax < 0 or tmin > tmax:
        return None, None
    
    t_hit = tmin if tmin >= 1e-4 else tmax
    if t_hit < 1e-4:
        return None, None
    
    hit = add(ro, mul(rd, t_hit))
    
    # Determine normal
    eps = 1e-4
    if abs(hit[0] - bmin[0]) < eps:
        n = (-1.0, 0.0, 0.0)
    elif abs(hit[0] - bmax[0]) < eps:
        n = (1.0, 0.0, 0.0)
    elif abs(hit[1] - bmin[1]) < eps:
        n = (0.0, -1.0, 0.0)
    elif abs(hit[1] - bmax[1]) < eps:
        n = (0.0, 1.0, 0.0)
    elif abs(hit[2] - bmin[2]) < eps:
        n = (0.0, 0.0, -1.0)
    else:
        n = (0.0, 0.0, 1.0)
    
    return t_hit, n

def ray_sphere(ro: Tuple[float, float, float], rd: Tuple[float, float, float],
               center: Tuple[float, float, float], radius: float) -> Tuple[Optional[float], Optional[Tuple[float, float, float]]]:
    """Ray-sphere intersection."""
    oc = sub(ro, center)
    a = dot(rd, rd)
    b = 2.0 * dot(oc, rd)
    c = dot(oc, oc) - radius * radius
    disc = b * b - 4 * a * c
    
    if disc < 0:
        return None, None
    
    sdisc = math.sqrt(disc)
    t0 = (-b - sdisc) / (2 * a)
    t1 = (-b + sdisc) / (2 * a)
    
    t = None
    if t0 > 1e-4:
        t = t0
    elif t1 > 1e-4:
        t = t1
    
    if t is None:
        return None, None
    
    hit = add(ro, mul(rd, t))
    n = norm(sub(hit, center))
    return t, n

def ray_plane(ro: Tuple[float, float, float], rd: Tuple[float, float, float],
              pos: Tuple[float, float, float], normal: Tuple[float, float, float]) -> Tuple[Optional[float], Optional[Tuple[float, float, float]]]:
    """Ray-plane intersection."""
    denom = dot(rd, normal)
    if abs(denom) < 1e-8:
        return None, None
    
    t = dot(sub(pos, ro), normal) / denom
    if t < 1e-4:
        return None, None
    
    return t, normal

def ray_cylinder(ro: Tuple[float, float, float], rd: Tuple[float, float, float],
                 center: Tuple[float, float, float], radius: float, height: float) -> Tuple[Optional[float], Optional[Tuple[float, float, float]]]:
    """Ray-cylinder intersection (vertical cylinder for human torso)."""
    oc = (ro[0] - center[0], ro[1] - center[1], ro[2] - center[2])
    
    # Project to XZ plane
    a = rd[0] * rd[0] + rd[2] * rd[2]
    if abs(a) < 1e-8:
        return None, None
    
    b = 2.0 * (oc[0] * rd[0] + oc[2] * rd[2])
    c = oc[0] * oc[0] + oc[2] * oc[2] - radius * radius
    disc = b * b - 4 * a * c
    
    if disc < 0:
        return None, None
    
    sdisc = math.sqrt(disc)
    t0 = (-b - sdisc) / (2 * a)
    t1 = (-b + sdisc) / (2 * a)
    
    # Check Y bounds
    for t in [t0, t1]:
        if t < 1e-4:
            continue
        hit = add(ro, mul(rd, t))
        y_rel = hit[1] - center[1]
        if 0 <= y_rel <= height:
            n = norm((hit[0] - center[0], 0.0, hit[2] - center[2]))
            return t, n
    
    return None, None

def ray_sphere_capsule(ro: Tuple[float, float, float], rd: Tuple[float, float, float],
                       center: Tuple[float, float, float], radius: float) -> Tuple[Optional[float], Optional[Tuple[float, float, float]]]:
    """Ray-sphere intersection (for head/limbs)."""
    return ray_sphere(ro, rd, center, radius)

class Scene:
    """Scene representation with room, mirrors, lights, and human models."""
    
    def __init__(self, scene_data: Dict[str, Any]):
        self.scene_data = scene_data
        self.room = scene_data["room"]
        self.light = scene_data["light"]
        self.mirrors = scene_data.get("mirrors", [])
        self.human_models = scene_data.get("human_models", [])
        self.candles = scene_data.get("candles", [])
        
        # Room bounds
        room_size = self.room["size"]
        room_center = self.room["center"]
        self.room_min = (room_center[0] - room_size[0]/2, room_center[1] - room_size[1]/2, room_center[2] - room_size[2]/2)
        self.room_max = (room_center[0] + room_size[0]/2, room_center[1] + room_size[1]/2, room_center[2] + room_size[2]/2)
    
    def get_room_face_color(self, normal: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """Get color for room face based on normal."""
        if normal[1] < -0.9:  # Floor
            return tuple(self.room["floor_color"])
        elif normal[1] > 0.9:  # Ceiling
            return tuple(self.room["ceiling_color"])
        else:  # Walls
            return tuple(self.room["wall_color"])
    
    def intersect_mirror(self, ro: Tuple[float, float, float], rd: Tuple[float, float, float],
                         mirror: Dict[str, Any]) -> Tuple[Optional[float], Optional[Tuple[float, float, float]]]:
        """Intersect ray with mirror plane."""
        pos = tuple(mirror["position"])
        normal = tuple(mirror["normal"])
        normal = norm(normal)
        
        t, n = ray_plane(ro, rd, pos, normal)
        if t is None:
            return None, None
        
        hit = add(ro, mul(rd, t))
        
        # Check if hit is within mirror bounds (simplified - check distance from center)
        size = mirror["size"]
        # For now, accept all hits on the plane
        return t, n
    
    def intersect_candle(self, ro: Tuple[float, float, float], rd: Tuple[float, float, float],
                        candle: Dict[str, Any]) -> Tuple[Optional[float], Optional[Tuple[float, float, float]], Optional[str]]:
        """
        Intersect ray with candle model (cylinder body + flame sphere on top).
        Candle emits light from the flame.
        """
        pos = tuple(candle["position"])
        height = candle.get("height", 1.5)
        radius = candle.get("radius", 0.2)
        
        hits = []
        
        # Candle body (vertical cylinder)
        candle_center = (pos[0], pos[1] + height * 0.5, pos[2])
        t_body, n_body = ray_cylinder(ro, rd, candle_center, radius, height)
        if t_body is not None:
            hits.append((t_body, n_body, "candle_body"))
        
        # Flame (emissive sphere on top)
        flame_center = (pos[0], pos[1] + height + 0.15, pos[2])
        flame_radius = 0.12
        t_flame, n_flame = ray_sphere(ro, rd, flame_center, flame_radius)
        if t_flame is not None:
            hits.append((t_flame, n_flame, "candle_flame"))
        
        if not hits:
            return None, None, None
        
        hits.sort(key=lambda x: x[0])
        return hits[0]
    
    def intersect_human(self, ro: Tuple[float, float, float], rd: Tuple[float, float, float],
                       human: Dict[str, Any]) -> Tuple[Optional[float], Optional[Tuple[float, float, float]], Optional[str]]:
        """
        Intersect ray with realistic human model using simple polygons.
        Model includes: head, torso, arms, legs, hands, feet.
        """
        pos = tuple(human["position"])
        scale = human.get("scale", 1.0)
        rotation = human.get("rotation", 0.0) * math.pi / 180.0  # Convert to radians
        
        # Rotation matrix for Y-axis rotation
        cos_r = math.cos(rotation)
        sin_r = math.sin(rotation)
        
        def rotate_and_translate(offset: Tuple[float, float, float]) -> Tuple[float, float, float]:
            """Rotate offset around Y-axis then translate to position"""
            x, y, z = offset
            x_rot = x * cos_r - z * sin_r
            z_rot = x * sin_r + z * cos_r
            return (pos[0] + x_rot, pos[1] + y, pos[2] + z_rot)
        
        hits = []
        
        # Head (sphere)
        head_center = (pos[0], pos[1] + 1.1 * scale, pos[2])
        head_radius = 0.15 * scale
        t_head, n_head = ray_sphere(ro, rd, head_center, head_radius)
        if t_head is not None:
            hits.append((t_head, n_head, "head"))
        
        # Torso (cylinder) - main body
        torso_center = (pos[0], pos[1] + 0.4 * scale, pos[2])
        torso_radius = 0.25 * scale
        torso_height = 0.8 * scale
        t_torso, n_torso = ray_cylinder(ro, rd, torso_center, torso_radius, torso_height)
        if t_torso is not None:
            hits.append((t_torso, n_torso, "torso"))
        
        # Left arm (upper) - use sphere for visibility
        left_arm_upper_center = rotate_and_translate((-0.35 * scale, 0.5 * scale, 0.0))
        t_left_arm_u, n_left_arm_u = ray_sphere(ro, rd, left_arm_upper_center, 0.1 * scale)
        if t_left_arm_u is not None:
            hits.append((t_left_arm_u, n_left_arm_u, "arm"))
        
        # Left arm (lower/forearm)
        left_arm_lower_center = rotate_and_translate((-0.5 * scale, 0.2 * scale, 0.0))
        t_left_arm_l, n_left_arm_l = ray_sphere(ro, rd, left_arm_lower_center, 0.08 * scale)
        if t_left_arm_l is not None:
            hits.append((t_left_arm_l, n_left_arm_l, "arm"))
        
        # Right arm (upper)
        right_arm_upper_center = rotate_and_translate((0.35 * scale, 0.5 * scale, 0.0))
        t_right_arm_u, n_right_arm_u = ray_sphere(ro, rd, right_arm_upper_center, 0.1 * scale)
        if t_right_arm_u is not None:
            hits.append((t_right_arm_u, n_right_arm_u, "arm"))
        
        # Right arm (lower/forearm)
        right_arm_lower_center = rotate_and_translate((0.5 * scale, 0.2 * scale, 0.0))
        t_right_arm_l, n_right_arm_l = ray_sphere(ro, rd, right_arm_lower_center, 0.08 * scale)
        if t_right_arm_l is not None:
            hits.append((t_right_arm_l, n_right_arm_l, "arm"))
        
        # Left leg (thigh) - use vertical cylinder (works correctly)
        left_leg_upper_center = rotate_and_translate((-0.15 * scale, -0.2 * scale, 0.0))
        t_left_leg_u, n_left_leg_u = ray_cylinder(ro, rd, left_leg_upper_center, 0.12 * scale, 0.4 * scale)
        if t_left_leg_u is not None:
            hits.append((t_left_leg_u, n_left_leg_u, "leg"))
        
        # Left leg (lower/shin)
        left_leg_lower_center = rotate_and_translate((-0.15 * scale, -0.6 * scale, 0.0))
        t_left_leg_l, n_left_leg_l = ray_cylinder(ro, rd, left_leg_lower_center, 0.1 * scale, 0.4 * scale)
        if t_left_leg_l is not None:
            hits.append((t_left_leg_l, n_left_leg_l, "leg"))
        
        # Right leg (thigh)
        right_leg_upper_center = rotate_and_translate((0.15 * scale, -0.2 * scale, 0.0))
        t_right_leg_u, n_right_leg_u = ray_cylinder(ro, rd, right_leg_upper_center, 0.12 * scale, 0.4 * scale)
        if t_right_leg_u is not None:
            hits.append((t_right_leg_u, n_right_leg_u, "leg"))
        
        # Right leg (lower/shin)
        right_leg_lower_center = rotate_and_translate((0.15 * scale, -0.6 * scale, 0.0))
        t_right_leg_l, n_right_leg_l = ray_cylinder(ro, rd, right_leg_lower_center, 0.1 * scale, 0.4 * scale)
        if t_right_leg_l is not None:
            hits.append((t_right_leg_l, n_right_leg_l, "leg"))
        
        # Hands (spheres at end of arms)
        left_hand_center = rotate_and_translate((-0.65 * scale, 0.05 * scale, 0.0))
        t_left_hand, n_left_hand = ray_sphere(ro, rd, left_hand_center, 0.07 * scale)
        if t_left_hand is not None:
            hits.append((t_left_hand, n_left_hand, "hand"))
        
        right_hand_center = rotate_and_translate((0.65 * scale, 0.05 * scale, 0.0))
        t_right_hand, n_right_hand = ray_sphere(ro, rd, right_hand_center, 0.07 * scale)
        if t_right_hand is not None:
            hits.append((t_right_hand, n_right_hand, "hand"))
        
        # Feet (spheres at end of legs)
        left_foot_center = rotate_and_translate((-0.15 * scale, -0.9 * scale, 0.1 * scale))
        t_left_foot, n_left_foot = ray_sphere(ro, rd, left_foot_center, 0.08 * scale)
        if t_left_foot is not None:
            hits.append((t_left_foot, n_left_foot, "foot"))
        
        right_foot_center = rotate_and_translate((0.15 * scale, -0.9 * scale, 0.1 * scale))
        t_right_foot, n_right_foot = ray_sphere(ro, rd, right_foot_center, 0.08 * scale)
        if t_right_foot is not None:
            hits.append((t_right_foot, n_right_foot, "foot"))
        
        if not hits:
            return None, None, None
        
        # Return nearest hit
        hits.sort(key=lambda x: x[0])
        return hits[0]
    
    def trace(self, ro: Tuple[float, float, float], rd: Tuple[float, float, float],
              max_bounces: int = 4, bounce: int = 0, energy: float = 1.0) -> Tuple[float, float, float]:
        """
        Recursive ray tracing with reflections and proper light energy attenuation.
        Supports infinite ray tracing (very high max_bounces) with energy-based termination.
        
        Args:
            ro: Ray origin
            rd: Ray direction (normalized)
            max_bounces: Maximum recursion depth (use high value like 50+ for "infinite")
            bounce: Current bounce count
            energy: Current ray energy (1.0 = full, decreases with bounces)
        """
        # Stop if energy too low (natural termination) or max bounces reached
        # For "infinite" tracing, energy will naturally terminate rays
        if bounce >= max_bounces or energy < 0.005:
            return (0.0, 0.0, 0.0)
        
        # Apply exponential attenuation after 6 bounces (phase out light particle)
        if bounce >= 6:
            fade_factor = math.exp(-(bounce - 6) * 0.25)  # Exponential decay
            energy *= fade_factor
        
        # Find nearest intersection
        nearest_t = None
        nearest_n = None
        nearest_material = None
        nearest_color = None
        nearest_reflectivity = 0.0
        
        # Room walls
        t_room, n_room = ray_aabb(ro, rd, self.room_min, self.room_max)
        if t_room is not None:
            nearest_t = t_room
            nearest_n = n_room
            nearest_material = "room"
            nearest_color = self.get_room_face_color(n_room)
            nearest_reflectivity = 0.0
        
        # Light source
        light_pos = tuple(self.light["position"])
        light_radius = self.light["radius"]
        t_light, n_light = ray_sphere(ro, rd, light_pos, light_radius)
        if t_light is not None and (nearest_t is None or t_light < nearest_t):
            # If we hit the light, return its emission (bright, subtle glow)
            # Make light source appear brighter than rest of room
            intensity = tuple(self.light["intensity"])
            # Boost intensity slightly for visual refinement
            boost = 1.15  # 15% brighter for subtle enhancement
            return (intensity[0] * boost, intensity[1] * boost, intensity[2] * boost)
        
        # Mirrors
        for mirror in self.mirrors:
            t_mirror, n_mirror = self.intersect_mirror(ro, rd, mirror)
            if t_mirror is not None and (nearest_t is None or t_mirror < nearest_t):
                nearest_t = t_mirror
                nearest_n = n_mirror
                nearest_material = "mirror"
                nearest_color = (0.0, 0.0, 0.0)
                nearest_reflectivity = mirror.get("reflectivity", 0.95)
        
        # Candles (emissive light sources)
        for candle in self.candles:
            t_candle, n_candle, part = self.intersect_candle(ro, rd, candle)
            if t_candle is not None and (nearest_t is None or t_candle < nearest_t):
                nearest_t = t_candle
                nearest_n = n_candle
                if part == "candle_flame":
                    # Flame emits light
                    intensity = tuple(candle.get("flame_intensity", [8.0, 6.0, 4.0]))
                    return intensity
                else:
                    # Candle body (wax)
                    nearest_material = "candle"
                    nearest_color = tuple(candle.get("wax_color", [0.9, 0.9, 0.95]))
                    nearest_reflectivity = 0.0
        
        # Human models (kept for backward compatibility)
        for human in self.human_models:
            t_human, n_human, part = self.intersect_human(ro, rd, human)
            if t_human is not None and (nearest_t is None or t_human < nearest_t):
                nearest_t = t_human
                nearest_n = n_human
                nearest_material = "human"
                nearest_color = tuple(human["color"])
                nearest_reflectivity = 0.0
        
        if nearest_t is None:
            # Sky
            t = 0.5 * (rd[1] + 1.0)
            return (0.1 * (1-t) + 0.3*t, 0.12 * (1-t) + 0.4*t, 0.15 * (1-t) + 0.5*t)
        
        hit = add(ro, mul(rd, nearest_t))
        
        # Handle reflections with proper energy attenuation
        if nearest_reflectivity > 0.01:
            reflected_rd = reflect(rd, nearest_n)
            # Offset slightly to avoid self-intersection
            reflected_ro = add(hit, mul(nearest_n, 1e-4))
            
            # Calculate energy loss on reflection (mirror efficiency)
            # Real mirrors lose ~5-10% energy per reflection
            reflection_efficiency = 0.92  # 8% energy loss per mirror bounce
            new_energy = energy * reflection_efficiency
            
            reflected_color = self.trace(reflected_ro, reflected_rd, max_bounces, bounce + 1, new_energy)
            # Apply reflectivity and energy scaling
            return mul(reflected_color, nearest_reflectivity * energy)
        
        # Lighting calculation
        light_pos = tuple(self.light["position"])
        to_light = sub(light_pos, hit)
        dist_to_light = length(to_light)
        ldir = norm(to_light)
        
        # Shadow ray
        shadow_ro = add(hit, mul(nearest_n, 1e-4))
        shadow_t, _ = ray_sphere(shadow_ro, ldir, light_pos, self.light["radius"])
        blocked = shadow_t is not None and shadow_t < dist_to_light - self.light["radius"] - 1e-3
        
        # Also check if shadow ray hits room or humans
        if not blocked:
            t_room_shadow, _ = ray_aabb(shadow_ro, ldir, self.room_min, self.room_max)
            if t_room_shadow is not None and t_room_shadow < dist_to_light:
                blocked = True
        
        if not blocked:
            # Check candles for shadow
            for candle in self.candles:
                t_candle_shadow, _, _ = self.intersect_candle(shadow_ro, ldir, candle)
                if t_candle_shadow is not None and t_candle_shadow < dist_to_light:
                    blocked = True
                    break
        
        if not blocked:
            # Check humans for shadow (backward compatibility)
            for human in self.human_models:
                t_human_shadow, _, _ = self.intersect_human(shadow_ro, ldir, human)
                if t_human_shadow is not None and t_human_shadow < dist_to_light:
                    blocked = True
                    break
        
        # Lambertian shading with proper light energy calculation
        ndotl = clamp01(dot(nearest_n, ldir))
        light_intensity = tuple(self.light["intensity"])
        
        # Inverse square law for light falloff (proper physics)
        dist_factor = 1.0 / max(0.1, dist_to_light * dist_to_light)
        
        # Atmospheric/medium attenuation (light loses energy traveling through air)
        # Very subtle for short distances, more noticeable for longer paths
        medium_attenuation = math.exp(-dist_to_light * 0.02)  # Small absorption
        
        ambient = 0.1
        direct = 0.0 if blocked else ndotl * dist_factor * medium_attenuation
        
        # Combine colors with energy consideration
        # Current ray energy affects contribution (for recursive paths)
        col = (
            nearest_color[0] * (ambient + direct * light_intensity[0] * energy),
            nearest_color[1] * (ambient + direct * light_intensity[1] * energy),
            nearest_color[2] * (ambient + direct * light_intensity[2] * energy)
        )
        
        return col

def tone_map_reinhard(c: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Reinhard tone mapping."""
    return (c[0] / (1.0 + c[0]), c[1] / (1.0 + c[1]), c[2] / (1.0 + c[2]))

def gamma_correct(c: Tuple[float, float, float], gamma: float = 2.2) -> Tuple[float, float, float]:
    """Gamma correction."""
    inv_gamma = 1.0 / gamma
    return (pow(clamp01(c[0]), inv_gamma), pow(clamp01(c[1]), inv_gamma), pow(clamp01(c[2]), inv_gamma))

def render(scene_data: Dict[str, Any], output_path: str = "render.png") -> None:
    """Main rendering function."""
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
    
    # Right vector = forward × world_up
    right = norm((
        forward[1] * world_up[2] - forward[2] * world_up[1],
        forward[2] * world_up[0] - forward[0] * world_up[2],
        forward[0] * world_up[1] - forward[1] * world_up[0]
    ))
    
    # If forward is parallel to world_up, use alternative
    if length(right) < 0.1:
        right = (1.0, 0.0, 0.0) if abs(forward[0]) < 0.9 else (0.0, 0.0, 1.0)
        right = norm(right)
    
    # Up vector = right × forward
    up = norm((
        right[1] * forward[2] - right[2] * forward[1],
        right[2] * forward[0] - right[0] * forward[2],
        right[0] * forward[1] - right[1] * forward[0]
    ))
    
    scale = math.tan(math.radians(fov * 0.5))
    
    img = Image.new("RGB", (W, H))
    pix = img.load()
    
    print(f"Rendering {W}x{H} image with {max_bounces} max bounces...")
    
    for y in range(H):
        if y % 50 == 0:
            print(f"Progress: {y}/{H} ({100*y//H}%)")
        
        py = (1.0 - 2.0 * (y + 0.5) / H) * scale
        for x in range(W):
            px = (2.0 * (x + 0.5) / W - 1.0) * scale * aspect
            
            # Camera ray (proper camera basis)
            rd = norm(add(add(mul(right, px), mul(up, py)), forward))
            
            # Trace ray with initial energy of 1.0
            color = scene.trace(cam_pos, rd, max_bounces, bounce=0, energy=1.0)
            
            # Tone mapping and gamma
            color = tone_map_reinhard(color)
            color = gamma_correct(color)
            
            # Convert to 0-255
            r = int(clamp01(color[0]) * 255)
            g = int(clamp01(color[1]) * 255)
            b = int(clamp01(color[2]) * 255)
            
            pix[x, y] = (r, g, b)
    
    img.save(output_path)
    print(f"Saved {output_path}")

if __name__ == "__main__":
    import os
    from datetime import datetime
    
    # Try to find scene.json in parent directory or current directory
    scene_path = "../scene.json" if os.path.exists("../scene.json") else "scene.json"
    scene_data = load_scene(scene_path)
    validate_scene(scene_data)
    
    # Create renders directory
    renders_dir = "../renders" if os.path.exists("../scene.json") else "renders"
    os.makedirs(renders_dir, exist_ok=True)
    
    # Generate descriptive filename
    cam = scene_data["camera"]
    render_settings = scene_data["render"]
    num_humans = len(scene_data.get("human_models", []))
    num_mirrors = len(scene_data.get("mirrors", []))
    max_bounces = render_settings.get("max_bounces", 4)
    
    # Create filename with timestamp and scene info
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"render_{timestamp}_b{max_bounces}_h{num_humans}_m{num_mirrors}_{render_settings['width']}x{render_settings['height']}.png"
    output_path = os.path.join(renders_dir, filename)
    
    render(scene_data, output_path)


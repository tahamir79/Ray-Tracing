"""Scene loading and validation from scene.json"""
import json
from typing import Dict, List, Tuple, Any

def load_scene(json_path: str = "scene.json") -> Dict[str, Any]:
    """Load scene configuration from JSON file."""
    with open(json_path, 'r') as f:
        return json.load(f)

def validate_scene(scene: Dict[str, Any]) -> None:
    """Basic validation of scene structure."""
    assert "camera" in scene, "Scene must have camera"
    assert "room" in scene, "Scene must have room"
    assert "light" in scene, "Scene must have light"
    assert "render" in scene, "Scene must have render settings"
    
    # Validate camera
    cam = scene["camera"]
    assert "position" in cam and len(cam["position"]) == 3
    assert "look_at" in cam and len(cam["look_at"]) == 3
    assert "fov" in cam
    
    # Validate room
    room = scene["room"]
    assert "size" in room and len(room["size"]) == 3
    assert "center" in room and len(room["center"]) == 3
    
    # Validate light
    light = scene["light"]
    assert "position" in light and len(light["position"]) == 3
    assert "intensity" in light and len(light["intensity"]) == 3
    
    print("Scene validation passed!")


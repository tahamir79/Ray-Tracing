"""
Interactive 3D preview of the scene using Plotly.
Helps verify geometry before rendering.
"""
import json
import plotly.graph_objects as go
import plotly.express as px
from scene import load_scene, validate_scene

def create_scene_preview(scene_data: dict):
    """Create interactive 3D plot of scene."""
    fig = go.Figure()
    
    room = scene_data["room"]
    room_size = room["size"]
    room_center = room["center"]
    
    # Room wireframe (simplified - show corners)
    corners = [
        [room_center[0] - room_size[0]/2, room_center[1] - room_size[1]/2, room_center[2] - room_size[2]/2],
        [room_center[0] + room_size[0]/2, room_center[1] - room_size[1]/2, room_center[2] - room_size[2]/2],
        [room_center[0] + room_size[0]/2, room_center[1] + room_size[1]/2, room_center[2] - room_size[2]/2],
        [room_center[0] - room_size[0]/2, room_center[1] + room_size[1]/2, room_center[2] - room_size[2]/2],
        [room_center[0] - room_size[0]/2, room_center[1] - room_size[1]/2, room_center[2] + room_size[2]/2],
        [room_center[0] + room_size[0]/2, room_center[1] - room_size[1]/2, room_center[2] + room_size[2]/2],
        [room_center[0] + room_size[0]/2, room_center[1] + room_size[1]/2, room_center[2] + room_size[2]/2],
        [room_center[0] - room_size[0]/2, room_center[1] + room_size[1]/2, room_center[2] + room_size[2]/2],
    ]
    
    # Draw room edges (simplified wireframe)
    edges = [
        [0, 1], [1, 2], [2, 3], [3, 0],  # front face
        [4, 5], [5, 6], [6, 7], [7, 4],  # back face
        [0, 4], [1, 5], [2, 6], [3, 7]   # connecting edges
    ]
    
    for edge in edges:
        fig.add_trace(go.Scatter3d(
            x=[corners[edge[0]][0], corners[edge[1]][0]],
            y=[corners[edge[0]][1], corners[edge[1]][1]],
            z=[corners[edge[0]][2], corners[edge[1]][2]],
            mode='lines',
            line=dict(color='gray', width=2),
            showlegend=False
        ))
    
    # Light source
    light = scene_data["light"]
    light_pos = light["position"]
    light_radius = light["radius"]
    
    # Create sphere for light
    u = [i * 0.1 for i in range(11)]
    v = [i * 0.1 for i in range(11)]
    x_light = []
    y_light = []
    z_light = []
    for ui in u:
        for vi in v:
            x_light.append(light_pos[0] + light_radius * (ui - 0.5))
            y_light.append(light_pos[1] + light_radius * (vi - 0.5))
            z_light.append(light_pos[2] + light_radius * 0.5)
    
    fig.add_trace(go.Scatter3d(
        x=[light_pos[0]],
        y=[light_pos[1]],
        z=[light_pos[2]],
        mode='markers',
        marker=dict(size=15, color='yellow', symbol='circle'),
        name='Light'
    ))
    
    # Mirrors
    mirrors = scene_data.get("mirrors", [])
    for i, mirror in enumerate(mirrors):
        pos = mirror["position"]
        normal = mirror["normal"]
        size = mirror["size"]
        
        # Draw mirror as a plane
        # Create a small rectangle
        fig.add_trace(go.Mesh3d(
            x=[pos[0] - size[0]/2, pos[0] + size[0]/2, pos[0] + size[0]/2, pos[0] - size[0]/2],
            y=[pos[1] - size[1]/2, pos[1] - size[1]/2, pos[1] + size[1]/2, pos[1] + size[1]/2],
            z=[pos[2], pos[2], pos[2], pos[2]],
            color='cyan',
            opacity=0.5,
            name=f'Mirror {i+1}'
        ))
    
    # Human models
    human_models = scene_data.get("human_models", [])
    for i, human in enumerate(human_models):
        pos = human["position"]
        scale = human.get("scale", 1.0)
        
        # Torso (cylinder approximation - show as sphere)
        torso_y = pos[1] + 0.4 * scale
        fig.add_trace(go.Scatter3d(
            x=[pos[0]],
            y=[torso_y],
            z=[pos[2]],
            mode='markers',
            marker=dict(size=12 * scale, color='rgb(230, 180, 150)', symbol='circle'),
            name=f'Human {i+1} Torso'
        ))
        
        # Head
        head_y = pos[1] + 1.1 * scale
        fig.add_trace(go.Scatter3d(
            x=[pos[0]],
            y=[head_y],
            z=[pos[2]],
            mode='markers',
            marker=dict(size=8 * scale, color='rgb(230, 180, 150)', symbol='circle'),
            name=f'Human {i+1} Head'
        ))
    
    # Camera
    cam = scene_data["camera"]
    cam_pos = cam["position"]
    look_at = cam["look_at"]
    
    fig.add_trace(go.Scatter3d(
        x=[cam_pos[0]],
        y=[cam_pos[1]],
        z=[cam_pos[2]],
        mode='markers',
        marker=dict(size=10, color='red', symbol='diamond'),
        name='Camera'
    ))
    
    # Camera look direction
    fig.add_trace(go.Scatter3d(
        x=[cam_pos[0], look_at[0]],
        y=[cam_pos[1], look_at[1]],
        z=[cam_pos[2], look_at[2]],
        mode='lines',
        line=dict(color='red', width=3, dash='dash'),
        name='Camera Look'
    ))
    
    fig.update_layout(
        title="Scene Preview (Interactive 3D)",
        scene=dict(
            xaxis_title="X",
            yaxis_title="Y",
            zaxis_title="Z",
            aspectmode='data'
        ),
        width=1000,
        height=800
    )
    
    return fig

if __name__ == "__main__":
    scene_data = load_scene("../scene.json")
    validate_scene(scene_data)
    fig = create_scene_preview(scene_data)
    fig.show()


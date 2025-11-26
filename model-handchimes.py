import bpy
import json
import os
import math
import bmesh
import mathutils
from bpy_extras import anim_utils

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
JSON_FILE_NAME = "DanceOfTheSugarPlumFairy-Celesta-handchimes.json"

CHIME_WIDTH = 0.025      # 25mm
CHIME_HEIGHT = 0.025     # 25mm
WALL_THICKNESS = 0.003   # 3mm
CHIME_SPACING = 0.05
CHIME_PARENT_X_OFFSET = 0.0
CHIME_PARENT_Y_OFFSET = -0.575
CHIME_PARENT_Z_OFFSET = 0.09
CHIME_PARENT_Y_ROTATION = -20 # degrees
LIGHT_POWER = 1.0        # Wattage for the point lights
TARGET_FPS = 30.0        # For animation timing
MAX_VELOCITY_LIGHT_FACTOR = 2.0
MIN_VELOCITY_LIGHT_FACTOR = 1.0
LIGHT_DECAY_DURATION = 1.5 # Seconds to fade out after noteOff

CHIME_STRIKER_SPHERE_Z_OFFSET = 0.1
CHIME_STRIKER_SPHERE_X_FACTOR = 0.2

# ------------------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------------------

def main():
    # Find JSON file
    json_path = JSON_FILE_NAME
    if bpy.data.filepath:
        blend_dir = os.path.dirname(bpy.data.filepath)
        json_path = os.path.join(blend_dir, JSON_FILE_NAME)

    # Fallback for testing if blend file not saved
    if not os.path.exists(json_path):
        candidate = "/home/glenn/Projects/Audio-Visualizer-Masterclass/Course-Assets-v1.1/Tools/" + JSON_FILE_NAME
        if os.path.exists(candidate):
            json_path = candidate

    if not os.path.exists(json_path):
        print(f"ERROR: Could not find {json_path}")
        return

    print(f"Loading {json_path}...")
    with open(json_path, 'r') as f:
        notes_data = json.load(f)

    # Create Collection
    col_name = "Handchimes"
    if col_name in bpy.data.collections:
        col = bpy.data.collections[col_name]
        # Clear existing objects in collection
        print(f"Collection '{col_name}' exists. Clearing {len(col.objects)} objects...")
        obs = [o for o in col.objects]
        for ob in obs:
            bpy.data.objects.remove(ob, do_unlink=True)
    else:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)

    # Create Parent Empty
    parent_empty = bpy.data.objects.new("Handchimes_Parent", None)
    parent_empty.empty_display_type = 'PLAIN_AXES'
    col.objects.link(parent_empty)

    # Create Master Cutter Meshes
    # We need two cutters: one for the hole (cylinder) and one for the slot (cuboid).

    # 1. Master Cylinder Cutter (Hole)
    cutter_mesh_hole = bpy.data.meshes.new("Master_Cutter_Hole_Mesh")
    bm_hole = bmesh.new()

    # Cylinder along Y axis (rotated X 90)
    # Make it very long in Y to ensure it cuts through
    bmesh.ops.create_cone(
        bm_hole,
        cap_ends=True,
        cap_tris=False,
        segments=32,
        radius1=(CHIME_WIDTH/3)/2,
        radius2=(CHIME_WIDTH/3)/2,
        depth=CHIME_WIDTH * 5 # Plenty of width
    )
    bmesh.ops.rotate(bm_hole, cent=(0,0,0), matrix=mathutils.Matrix.Rotation(math.radians(90.0), 4, 'X'), verts=bm_hole.verts)

    bm_hole.to_mesh(cutter_mesh_hole)
    bm_hole.free()

    master_cutter_hole = bpy.data.objects.new("Master_Cutter_Hole", cutter_mesh_hole)
    col.objects.link(master_cutter_hole)
    master_cutter_hole.parent = parent_empty
    master_cutter_hole.hide_render = True
    master_cutter_hole.hide_viewport = True
    master_cutter_hole.display_type = 'WIRE'

    # 2. Master Slot Cutter (Cuboid)
    # Extends from center (0,0,0) to -X direction
    # Wide in Y, Thin in Z

    # Find max length again just to be safe
    max_length = 0.0
    for note in notes_data:
        if note['length'] > max_length:
            max_length = note['length']

    cutter_mesh_slot = bpy.data.meshes.new("Master_Cutter_Slot_Mesh")
    bm_slot = bmesh.new()

    slot_len = max_length + 0.1
    slot_thickness = (CHIME_WIDTH/3) * 0.99

    ret = bmesh.ops.create_cube(bm_slot, size=1.0)
    slot_verts = ret['verts']

    # Scale: X=Length, Y=Width (Huge), Z=Thickness
    bmesh.ops.scale(bm_slot, vec=(slot_len, CHIME_WIDTH * 5, slot_thickness), verts=slot_verts)

    # Translate: Move so +X face is at 0. (Center is at -slot_len/2)
    bmesh.ops.translate(bm_slot, vec=(-slot_len/2, 0, 0), verts=slot_verts)

    bm_slot.to_mesh(cutter_mesh_slot)
    bm_slot.free()

    master_cutter_slot = bpy.data.objects.new("Master_Cutter_Slot", cutter_mesh_slot)
    col.objects.link(master_cutter_slot)
    master_cutter_slot.parent = parent_empty
    master_cutter_slot.hide_render = True
    master_cutter_slot.hide_viewport = True
    master_cutter_slot.display_type = 'WIRE'

    print(f"Master Cutters created. Hole Verts: {len(cutter_mesh_hole.vertices)}, Slot Verts: {len(cutter_mesh_slot.vertices)}")

    # Create Chimes
    for i, note in enumerate(notes_data):
        length = note['length']
        name = note['name']

        y_pos = -i * CHIME_SPACING

        # Create Mesh and Object
        mesh = bpy.data.meshes.new(f"ChimeMesh_{name}")
        obj = bpy.data.objects.new(f"Chime_{name}", mesh)
        col.objects.link(obj)

        # Create Geometry using BMesh
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)

        # Scale
        # Cube is 1x1x1. We want (length, CHIME_WIDTH, CHIME_HEIGHT)
        bmesh.ops.scale(bm, vec=(length, CHIME_WIDTH, CHIME_HEIGHT), verts=bm.verts)

        # Translate
        # Center is at 0,0,0. Move to (-length/2, y_pos, 0)
        bmesh.ops.translate(bm, vec=(-length/2, y_pos, 0), verts=bm.verts)

        # Delete End Faces (X axis)
        # Update normals to be sure
        bm.normal_update()
        faces_to_delete = [f for f in bm.faces if abs(f.normal.x) > 0.5]
        bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')

        # Write to mesh
        bm.to_mesh(mesh)
        bm.free()

        # Add Solidify Modifier
        mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
        mod.thickness = WALL_THICKNESS
        mod.offset = -1.0 # Inward, keeping outer dimensions at 25mm

        # Create Cutter Instances

        # 1. Hole Cutter
        cutter_hole = master_cutter_hole.copy()
        cutter_hole.name = f"Cutter_Hole_{name}"
        cutter_hole.location = (-length/2, y_pos, 0)
        col.objects.link(cutter_hole)
        cutter_hole.parent = parent_empty

        mod_bool_hole = obj.modifiers.new(name="DrillHole", type='BOOLEAN')
        mod_bool_hole.object = cutter_hole
        mod_bool_hole.operation = 'DIFFERENCE'
        mod_bool_hole.solver = 'FLOAT'

        # 2. Slot Cutter
        cutter_slot = master_cutter_slot.copy()
        cutter_slot.name = f"Cutter_Slot_{name}"
        cutter_slot.location = (-length/2, y_pos, 0)
        col.objects.link(cutter_slot)
        cutter_slot.parent = parent_empty

        mod_bool_slot = obj.modifiers.new(name="CutSlot", type='BOOLEAN')
        mod_bool_slot.object = cutter_slot
        mod_bool_slot.operation = 'DIFFERENCE'
        mod_bool_slot.solver = 'FLOAT'

        # Create and Assign Material
        mat = bpy.data.materials.new(name=f"Mat_{name}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            # Set Emission Color (Rich Dark Green)
            # Try "Emission Color" (Blender 4.0+) or "Emission" (Older)
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (0.0, 0.5, 0.0, 1.0)
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = (0.0, 0.5, 0.0, 1.0)

            # Driver for Emission Strength
            if "Emission Strength" in bsdf.inputs:
                d_mat = bsdf.inputs["Emission Strength"].driver_add("default_value")
                var_mat = d_mat.driver.variables.new()
                var_mat.name = "strength"
                var_mat.type = 'SINGLE_PROP'
                var_mat.targets[0].id = obj
                var_mat.targets[0].data_path = '["vibrate_strength"]'
                d_mat.driver.expression = f"strength * {LIGHT_POWER}"

        obj.data.materials.append(mat)

        # Set Parent
        obj.parent = parent_empty

        # Add Custom Property for Vibration Strength (used for light intensity)
        obj["vibrate_strength"] = 0.0
        obj.keyframe_insert(data_path='["vibrate_strength"]', frame=0)

        # Animate Strength based on Events
        events = note.get('events', [])
        sorted_events = sorted(events, key=lambda e: e['time'])

        # Time scaling (assuming FPS mode like piano strings)
        time_scale = TARGET_FPS
        time_offset = 0.0

        current_strength = 0.0

        for event in sorted_events:
            # Use float frame for sub-frame accuracy
            frame = event['time'] * time_scale + time_offset

            if event['type'] == 'noteOn':
                # Calculate strength based on velocity
                # vel is usually 0.0 to 1.0
                vel = event.get('vel', 0.5)
                # Map vel to [MIN, MAX]
                target_strength = MIN_VELOCITY_LIGHT_FACTOR + (MAX_VELOCITY_LIGHT_FACTOR - MIN_VELOCITY_LIGHT_FACTOR) * vel

                # Keyframe 0 at frame-1, target_strength at frame
                obj["vibrate_strength"] = 0.0
                obj.keyframe_insert(data_path='["vibrate_strength"]', frame=max(0, frame - 1))
                obj["vibrate_strength"] = target_strength
                obj.keyframe_insert(data_path='["vibrate_strength"]', frame=frame)

                current_strength = target_strength

            elif event['type'] == 'noteOff':
                # Start decay at 'frame'
                obj["vibrate_strength"] = current_strength
                obj.keyframe_insert(data_path='["vibrate_strength"]', frame=frame)

                # End decay at 'frame + decay_frames'
                decay_frames = LIGHT_DECAY_DURATION * TARGET_FPS

                obj["vibrate_strength"] = 0.0
                obj.keyframe_insert(data_path='["vibrate_strength"]', frame=frame + decay_frames)

                current_strength = 0.0

        # Create Point Light
        # Center position: x = -length/2, y = y_pos, z = 0
        bpy.ops.object.light_add(type='POINT', location=(-length/2, y_pos, 0))
        light_obj = bpy.context.active_object
        light_obj.name = f"Light_{name}"

        light_data = light_obj.data
        light_data.color = (0.0, 0.5, 0.0) # Rich Dark Green
        light_data.energy = LIGHT_POWER

        # Driver for Power to match vibrate_strength
        d = light_data.driver_add("energy")
        var = d.driver.variables.new()
        var.name = "strength"
        var.type = 'SINGLE_PROP'
        var.targets[0].id = obj
        var.targets[0].data_path = '["vibrate_strength"]'
        d.driver.expression = f"strength * {LIGHT_POWER}"

        # Parent Light to Empty
        light_obj.parent = parent_empty

        # Move Light to Collection
        for c in light_obj.users_collection:
            c.objects.unlink(light_obj)
        col.objects.link(light_obj)

    # Apply Parent Transformations
    parent_empty.location = (CHIME_PARENT_X_OFFSET, CHIME_PARENT_Y_OFFSET, CHIME_PARENT_Z_OFFSET)
    # Blender uses radians for rotation_euler
    parent_empty.rotation_euler = (0, math.radians(CHIME_PARENT_Y_ROTATION), 0)

    print(f"Generated {len(notes_data)} handchimes in collection '{col_name}'.")

    # --------------------------------------------------------------------------
    # Create Celesta Spheres
    # --------------------------------------------------------------------------

    celesta_col_name = "Celesta"
    if celesta_col_name in bpy.data.collections:
        celesta_col = bpy.data.collections[celesta_col_name]
        print(f"Collection '{celesta_col_name}' exists. Clearing {len(celesta_col.objects)} objects...")
        obs = [o for o in celesta_col.objects]
        for ob in obs:
            bpy.data.objects.remove(ob, do_unlink=True)
    else:
        celesta_col = bpy.data.collections.new(celesta_col_name)
        bpy.context.scene.collection.children.link(celesta_col)

    # Create Celesta Parent Empty
    celesta_parent = bpy.data.objects.new("Celesta_Parent", None)
    celesta_parent.empty_display_type = 'PLAIN_AXES'
    celesta_col.objects.link(celesta_parent)

    # Set Parent Transformations (Same location, NO rotation)
    celesta_parent.location = (CHIME_PARENT_X_OFFSET, CHIME_PARENT_Y_OFFSET, CHIME_PARENT_Z_OFFSET)
    celesta_parent.rotation_euler = (0, 0, 0)

    # Create Master Sphere
    # Diameter = CHIME_WIDTH -> Radius = CHIME_WIDTH / 2
    bpy.ops.mesh.primitive_uv_sphere_add(radius=CHIME_WIDTH/2, location=(0,0,0))
    master_sphere = bpy.context.active_object
    master_sphere.name = "Master_Celesta_Sphere"

    # Set Smooth Shading
    bpy.ops.object.shade_smooth()

    # Create Chrome Material
    mat_chrome = bpy.data.materials.new(name="Mat_Chrome")
    mat_chrome.use_nodes = True
    bsdf = mat_chrome.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        # Metallic = 1.0, Roughness = 0.0 (Mirror)
        bsdf.inputs["Metallic"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 0.0
        # Base Color = White/Light Grey
        bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)

    master_sphere.data.materials.append(mat_chrome)

    # Move Master to Collection and Hide
    for c in master_sphere.users_collection:
        c.objects.unlink(master_sphere)
    celesta_col.objects.link(master_sphere)
    master_sphere.parent = celesta_parent
    master_sphere.hide_render = True
    master_sphere.hide_viewport = True

    sphere_count = 0

    # Animation Constants
    TOTAL_FRAMES = 3121
    AUDIO_DURATION = 104.0
    X_VELOCITY = (AUDIO_DURATION * CHIME_STRIKER_SPHERE_X_FACTOR) # Total distance traveled
    # Actually, velocity is distance / time.
    # User said: "value + 20.8 (if my calculations are correct)".
    # 104 * 0.2 = 20.8. So total distance is 20.8.
    # Rate is 0.2 units/sec.

    # Physics Constants for Bounce
    Z_DROP = CHIME_STRIKER_SPHERE_Z_OFFSET
    # Z_FLOOR (Local) = Global_Floor (0) - Parent_Z + Radius
    Z_FLOOR = -0.0001 - CHIME_PARENT_Z_OFFSET + (CHIME_WIDTH / 2)

    # Approximate frames for fall (0.2m drop)
    # t = sqrt(2d/g) = sqrt(0.4/9.8) = 0.2s = 6 frames
    FALL_FRAMES = 6
    BOUNCE_FRAMES = 12 # Up and down to floor

    # Pre-calculate rotation math
    theta = math.radians(CHIME_PARENT_Y_ROTATION)
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    sphere_radius = CHIME_WIDTH / 2
    chime_half_height = CHIME_HEIGHT / 2

    for i, note in enumerate(notes_data):
        length = note['length'] # Need length for centering
        y_pos = -i * CHIME_SPACING
        events = note.get('events', [])

        # Calculate Strike Point
        # We want to strike the chime at exactly the sphere radius distance
        # from the downward-angled end (which is at local x = -length).

        local_x = -length + sphere_radius
        local_z = chime_half_height

        # Surface point in Parent Space (relative to Parent Origin)
        surf_x = local_x * cos_theta + local_z * sin_theta
        surf_z = -local_x * sin_theta + local_z * cos_theta

        # Sphere Center at Impact (in Parent Space)
        # Normal is rotated Z axis: (sin(theta), 0, cos(theta))
        strike_x = surf_x + sin_theta * sphere_radius
        strike_z = surf_z + cos_theta * sphere_radius

        for event in events:
            if event['type'] == 'noteOn':
                note_time = event['time']
                # Use float frame for exact sub-frame timing to prevent penetration
                strike_frame = note_time * TARGET_FPS

                # Calculate X Start Position
                # We want X(t_strike) = strike_x
                # X(t) = x_start - V * t
                # V = CHIME_STRIKER_SPHERE_X_FACTOR (units/sec)
                # strike_x = x_start - (V * note_time)
                # x_start = strike_x + (V * note_time)

                x_start = strike_x + (CHIME_STRIKER_SPHERE_X_FACTOR * note_time)

                # Calculate X End Position (at t = AUDIO_DURATION)
                # X(duration) = x_start - (V * duration)
                x_end = x_start - (CHIME_STRIKER_SPHERE_X_FACTOR * AUDIO_DURATION)

                # Debug print for the specific sphere mentioned by user
                if sphere_count == 281:
                    print(f"DEBUG Sphere 281: Time={note_time:.4f}s, Frame={strike_frame}")
                    print(f"DEBUG Sphere 281: Length={length}, Strike_X={strike_x:.4f}, Strike_Z={strike_z:.4f}")
                    print(f"DEBUG Sphere 281: X_Start={x_start:.4f}, X_End={x_end:.4f}")
                    print(f"DEBUG Sphere 281: Z_Floor={Z_FLOOR:.4f}")

                # Create Sphere Instance
                sphere = master_sphere.copy()
                sphere.data = master_sphere.data # Linked Mesh
                sphere.name = f"Celesta_Sphere_{note['name']}_{strike_frame}"

                # Initial Location (Frame 1)
                sphere.location = (x_start, y_pos, Z_DROP)

                celesta_col.objects.link(sphere)
                sphere.parent = celesta_parent

                # Ensure it's visible (master is hidden)
                sphere.hide_render = False
                sphere.hide_viewport = False

                # --------------------------------------------------------------
                # Animation
                # --------------------------------------------------------------

                # X Animation (Linear Motion)
                sphere.location.x = x_start
                sphere.keyframe_insert(data_path="location", index=0, frame=1)

                sphere.location.x = x_end
                sphere.keyframe_insert(data_path="location", index=0, frame=TOTAL_FRAMES)

                # Set linear interpolation for X location only
                if sphere.animation_data and sphere.animation_data.action:
                    action = sphere.animation_data.action
                    slot = sphere.animation_data.action_slot

                    # Get the channelbag for this slot
                    channelbag = anim_utils.action_ensure_channelbag_for_slot(action, slot)

                    # Find the X location fcurve
                    fcurve = channelbag.fcurves.find('location', index=0)
                    if fcurve:
                        for keyframe in fcurve.keyframe_points:
                            keyframe.interpolation = 'LINEAR'

                # Z Animation (Bounce)
                # 1. Start (Hovering/Falling start)
                sphere.location.z = Z_DROP
                sphere.keyframe_insert(data_path="location", index=2, frame=max(1, strike_frame - FALL_FRAMES))

                # 2. Strike (Touching Chime)
                sphere.location.z = strike_z
                sphere.keyframe_insert(data_path="location", index=2, frame=strike_frame)

                # 3. Bounce Peak (Small bounce up)
                sphere.location.z = strike_z + 0.05
                sphere.keyframe_insert(data_path="location", index=2, frame=strike_frame + (BOUNCE_FRAMES // 2))

                # 4. Floor (Land)
                sphere.location.z = Z_FLOOR
                sphere.keyframe_insert(data_path="location", index=2, frame=strike_frame + BOUNCE_FRAMES)

                # Z keyframes keep their default cubic interpolation for natural bounce

                # --------------------------------------------------------------
                # Apply Interpolation Fixes (Consolidated)
                # --------------------------------------------------------------
                if sphere.animation_data and sphere.animation_data.action:
                    action = sphere.animation_data.action
                    # Use getattr for safety
                    fcurves = getattr(action, "fcurves", [])

                    for fc in fcurves:
                        if fc.data_path == "location":
                            # X Axis: Linear
                            if fc.array_index == 0:
                                for kp in fc.keyframe_points:
                                    kp.interpolation = 'LINEAR'

                            # Z Axis: Vector Handles at Strike
                            elif fc.array_index == 2:
                                for kp in fc.keyframe_points:
                                    # Check if this keyframe is the strike frame (within tolerance)
                                    if abs(kp.co[0] - strike_frame) < 0.01:
                                        kp.handle_left_type = 'VECTOR'
                                        kp.handle_right_type = 'VECTOR'

                sphere_count += 1

    print(f"Generated {sphere_count} Celesta spheres in collection '{celesta_col_name}'.")

if __name__ == "__main__":
    main()

# ------------------------------------------------------------------------------
# STRIKER PLANE COORDINATES
# ------------------------------------------------------------------------------
# To create a perfect "cliff edge" for the Striker Plane where the spheres
# drop off exactly 0.2s (6 frames) before impact:
#
# Vertex 1 (Left / Low Note D5 Side):
# X: -0.156790
# Y: -0.562500
# Z:  0.177272
#
# Vertex 2 (Right / High Note C8 Side):
# X: -0.004137
# Y: -2.137500
# Z:  0.177272
# ------------------------------------------------------------------------------

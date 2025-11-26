import bpy
import json
import math
import os

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------
JSON_FILE_NAME = "DanceOfTheSugarPlumFairy-Violins-piano-strings.json"

# SYNC MODE
# "RANGE": Map the first and last notes to specific frames (stretches/shrinks time).
# "FPS":   Use a fixed frame rate (1 second MIDI = N frames). Trust the MIDI timing.
SYNC_MODE = "FPS"

# CONFIGURATION FOR "RANGE" MODE:
# Find the frame number in Blender where the FIRST note is heard
FIRST_NOTEON_EVENT_FRAME_NUMBER = 0
# Find the frame number in Blender where the LAST note is heard
LAST_NOTEON_EVENT_FRAME_NUMBER = 3050

# CONFIGURATION FOR "FPS" MODE:
TARGET_FPS = 30.0

STRING_SPACING_X = 0.05  # Distance between strings (meters)
POST_HEIGHT = 0.0508     # 2 inches in meters
POST_RADIUS = 0.005      # 5mm radius for posts
AMPLITUDE_FACTOR = 0.02  # Vibration amplitude as fraction of string length
LIGHT_POWER = 500.0       # Wattage for the area lights
MAX_VELOCITY_LIGHT_FACTOR = 2.0
MIN_VELOCITY_LIGHT_FACTOR = 1.0
LIGHT_DECAY_DURATION = 1.5 # Seconds to fade out after noteOff
CREATE_AREA_LIGHTS = False

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

def get_freq_from_note_name(note_name):
    """ Calculates frequency from note name (e.g., 'A4' -> 440) """
    # Note name format: "C#3", "Bb4", "G7"
    # Standard MIDI: A4 = 69 = 440Hz

    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    # Handle flats by converting to sharps (simple logic)
    if 'b' in note_name:
        # This is a bit hacky, but works for standard naming if consistent
        # Better to rely on the MIDI number if we had it in the top level object,
        # but we can infer it or parse the name.
        # The JSON generator uses sharps for output "C#", but let's be safe.
        pass

    # Parse name
    # Last char is octave usually, unless it's -1 (e.g. C-1)
    try:
        if note_name[-2] == '-':
            octave = int(note_name[-2:])
            note_str = note_name[:-2]
        else:
            octave = int(note_name[-1])
            note_str = note_name[:-1]
    except:
        print(f"Could not parse note: {note_name}")
        return 440.0

    try:
        note_index = notes.index(note_str)
    except ValueError:
        # Try handling flat
        if note_str.endswith('b'):
            base = note_str[:-1]
            if base in notes:
                idx = notes.index(base)
                note_index = (idx - 1) % 12
            else:
                note_index = 0
        else:
            note_index = 0

    # MIDI number calculation
    # C-1 is 0. C4 is 60.
    # (Octave + 1) * 12 + note_index
    midi_num = (octave + 1) * 12 + note_index

    freq = 440.0 * (2 ** ((midi_num - 69) / 12.0))
    return freq

def create_master_objects(master_col):
    # Master Peg
    if "Master_Peg" in bpy.data.objects:
        master_peg = bpy.data.objects["Master_Peg"]
    else:
        bpy.ops.mesh.primitive_cylinder_add(radius=POST_RADIUS, depth=POST_HEIGHT, location=(0, 0, 0))
        master_peg = bpy.context.active_object
        master_peg.name = "Master_Peg"

        # Add dummy material slot to master mesh so instances can override it
        if not master_peg.data.materials:
            mat = bpy.data.materials.new(name="Master_Peg_Mat")
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                if "Emission Color" in bsdf.inputs:
                    bsdf.inputs["Emission Color"].default_value = (0.0, 0.0, 1.0, 1.0)
                elif "Emission" in bsdf.inputs:
                    bsdf.inputs["Emission"].default_value = (0.0, 0.0, 1.0, 1.0)
            master_peg.data.materials.append(mat)

        # Move to master collection
        for col in master_peg.users_collection:
            col.objects.unlink(master_peg)
        master_col.objects.link(master_peg)

    # Master Sphere
    if "Master_Sphere" in bpy.data.objects:
        master_sphere = bpy.data.objects["Master_Sphere"]
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(radius=POST_RADIUS, location=(0, 0, 0))
        master_sphere = bpy.context.active_object
        master_sphere.name = "Master_Sphere"

        # Add dummy material slot to master mesh so instances can override it
        if not master_sphere.data.materials:
            mat = bpy.data.materials.new(name="Master_Sphere_Mat")
            mat.use_nodes = True
            bsdf = mat.node_tree.nodes.get("Principled BSDF")
            if bsdf:
                if "Emission Color" in bsdf.inputs:
                    bsdf.inputs["Emission Color"].default_value = (0.0, 0.0, 1.0, 1.0)
                elif "Emission" in bsdf.inputs:
                    bsdf.inputs["Emission"].default_value = (0.0, 0.0, 1.0, 1.0)
            master_sphere.data.materials.append(mat)

        # Move to master collection
        for col in master_sphere.users_collection:
            col.objects.unlink(master_sphere)
        master_col.objects.link(master_sphere)

    return master_peg, master_sphere

def create_post(master_peg, master_sphere, x, y, height, name, target_col, parent_obj):
    # Create Peg Instance
    peg = master_peg.copy()
    peg.data = master_peg.data # Ensure linked data
    peg.location = (x, y, height / 2)
    peg.name = name
    target_col.objects.link(peg)
    peg.parent = parent_obj

    # Create Sphere Instance (Cap)
    sphere = master_sphere.copy()
    sphere.data = master_sphere.data
    sphere.location = (x, y, height)
    sphere.name = name.replace("Post", "Cap")
    target_col.objects.link(sphere)
    sphere.parent = parent_obj

    return peg

def create_piano_string(name, note_name, y_pos, length, diameter, events, freq, time_scale, time_offset, target_col, lights_col, parent_obj, lights_parent_obj):
    # Create Curve Data
    curve_data = bpy.data.curves.new(name=name, type='CURVE')
    curve_data.dimensions = '3D'
    curve_data.bevel_depth = diameter / 2
    curve_data.bevel_resolution = 4

    # Create Spline
    spline = curve_data.splines.new(type='NURBS')
    spline.points.add(2)  # Already has 1, add 2 more = 3 points

    # Set points: (x, y, z, w)
    # Start
    spline.points[0].co = (0, y_pos, POST_HEIGHT, 1)
    # Middle
    spline.points[1].co = (-length / 2, y_pos, POST_HEIGHT, 1)
    # End
    spline.points[2].co = (-length, y_pos, POST_HEIGHT, 1)

    spline.use_endpoint_u = True

    # Create Object
    obj = bpy.data.objects.new(name, curve_data)
    target_col.objects.link(obj)
    obj.parent = parent_obj

    # Add Custom Property for Vibration Strength
    # This drives BOTH the string vibration amplitude and the area light intensity
    obj["vibrate_strength"] = 0.0
    obj.keyframe_insert(data_path='["vibrate_strength"]', frame=0)

    # Add Custom Properties for Driver
    obj["note_freq"] = freq
    obj["vibrate_amplitude"] = length * AMPLITUDE_FACTOR

    # Add Driver to Middle Point Y
    # Note: We can't easily drive a specific point coordinate directly via UI usually,
    # but we can via Python API using the data path.
    # Path: points[1].co[1]

    fcurve = curve_data.driver_add("splines[0].points[1].co", 1)
    driver = fcurve.driver
    driver.type = 'SCRIPTED'

    # Variable: strength
    var_strength = driver.variables.new()
    var_strength.name = "strength"
    var_strength.type = 'SINGLE_PROP'
    var_strength.targets[0].id = obj
    var_strength.targets[0].data_path = '["vibrate_strength"]'

    # Variable: freq
    var_freq = driver.variables.new()
    var_freq.name = "freq"
    var_freq.type = 'SINGLE_PROP'
    var_freq.targets[0].id = obj
    var_freq.targets[0].data_path = '["note_freq"]'

    # Variable: amplitude
    var_amp = driver.variables.new()
    var_amp.name = "amp"
    var_amp.type = 'SINGLE_PROP'
    var_amp.targets[0].id = obj
    var_amp.targets[0].data_path = '["vibrate_amplitude"]'

    # Variable: fps
    var_fps = driver.variables.new()
    var_fps.name = "fps"
    var_fps.type = 'SINGLE_PROP'
    var_fps.targets[0].id_type = 'SCENE'
    var_fps.targets[0].id = bpy.context.scene
    var_fps.targets[0].data_path = "render.fps"

    # Expression
    # y_pos + strength * amplitude * sin(frame * 2 * pi * freq / fps)
    # Note: 'pi' is available in driver namespace
    driver.expression = f"{y_pos} + strength * amp * sin(frame * 2 * pi * freq / fps)"

    # Animate Strength based on Events
    # Sort events by time just in case
    sorted_events = sorted(events, key=lambda e: e['time'])

    current_strength = 0.0

    for event in sorted_events:
        # Frame = Time * Scale + Offset
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

    # Create Area Light
    if CREATE_AREA_LIGHTS:
        # Center position: x = -length/2, y = y_pos, z = 0.0001
        # Note: Area lights point -Z by default. To point UP (+Z), rotate 180 deg (pi radians) around X or Y.
        bpy.ops.object.light_add(type='AREA', location=(-length/2, y_pos, 0.0001))
        light_obj = bpy.context.active_object
        light_obj.name = f"Light_{name}"

        # Move to Lights Collection
        # Unlink from current collections (usually just the active one)
        for col in light_obj.users_collection:
            col.objects.unlink(light_obj)
        # Link to lights collection
        lights_col.objects.link(light_obj)
        light_obj.parent = lights_parent_obj

        light_obj.rotation_euler = (math.pi, 0, 0)

        light_data = light_obj.data
        light_data.shape = 'RECTANGLE'
        # size is X dimension (length of string)
        light_data.size = length + 2 * STRING_SPACING_X
        # size_y is Y dimension (width/spacing)
        light_data.size_y = STRING_SPACING_X
        light_data.color = (0.0, 0.0, 1.0) # Deep Blue
        light_data.energy = LIGHT_POWER

        # Driver for Power to match vibrate_strength
        # Expression: strength * LIGHT_POWER
        d = light_data.driver_add("energy")
        var = d.driver.variables.new()
        var.name = "strength"
        var.type = 'SINGLE_PROP'
        var.targets[0].id = obj
        var.targets[0].data_path = '["vibrate_strength"]'
        d.driver.expression = f"strength * {LIGHT_POWER}"

    # Create and Assign Emissive Material
    # Material Name: Mat_String_{name}
    mat = bpy.data.materials.new(name=f"Mat_String_{name}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        # Set Base Color to Deep Blue (so it looks blue when off)
        bsdf.inputs["Base Color"].default_value = (0.0, 0.0, 1.0, 1.0)

        # Set Emission Color (Deep Blue)
        if "Emission Color" in bsdf.inputs:
            bsdf.inputs["Emission Color"].default_value = (0.0, 0.0, 1.0, 1.0)
        elif "Emission" in bsdf.inputs:
            bsdf.inputs["Emission"].default_value = (0.0, 0.0, 1.0, 1.0)

        # Driver for Emission Strength
        if "Emission Strength" in bsdf.inputs:
            d_mat = bsdf.inputs["Emission Strength"].driver_add("default_value")
            var_mat = d_mat.driver.variables.new()
            var_mat.name = "strength"
            var_mat.type = 'SINGLE_PROP'
            var_mat.targets[0].id = obj
            var_mat.targets[0].data_path = '["vibrate_strength"]'
            d_mat.driver.expression = f"strength * {LIGHT_POWER}"

    # Assign Material to String (Data Link is fine as Curve is unique)
    if not obj.data.materials:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat

    # Assign Material to Posts and Caps (Object Link required as Mesh is shared)
    # We need to find them by name
    related_objects = [
        f"Post_Start_{note_name}",
        f"Post_End_{note_name}",
        f"Cap_Start_{note_name}", # Note: create_post names it name.replace("Post", "Cap")
        f"Cap_End_{note_name}"
    ]

    # Note: create_post was called with "Post_Start_{name}" -> Cap is "Cap_Start_{name}"

    for obj_name in related_objects:
        if obj_name in bpy.data.objects:
            related_obj = bpy.data.objects[obj_name]
            # Ensure slot exists (we added dummy to master, so it should exist)
            if not related_obj.material_slots:
                # Should not happen if master has slot, but just in case
                related_obj.data.materials.append(bpy.data.materials.new(name="Dummy"))

            # Set Link to Object
            related_obj.material_slots[0].link = 'OBJECT'
            related_obj.material_slots[0].material = mat

    return obj

# ------------------------------------------------------------------------------
# Main Execution
# ------------------------------------------------------------------------------

def main():
    # Find JSON file
    # Assuming script is run from Blender text editor, we might need absolute path
    # or relative to the blend file.
    # For this script, we'll try to find it in the same directory as the blend file
    # or fallback to a hardcoded path if unsaved.

    json_path = JSON_FILE_NAME
    if bpy.data.filepath:
        blend_dir = os.path.dirname(bpy.data.filepath)
        json_path = os.path.join(blend_dir, JSON_FILE_NAME)

    # Fallback for testing if blend file not saved, assuming specific path from prompt context
    if not os.path.exists(json_path):
        # Try the path from the user's workspace context
        candidate = "/home/glenn/Projects/Audio-Visualizer-Masterclass/Course-Assets-v1.1/Tools/" + JSON_FILE_NAME
        if os.path.exists(candidate):
            json_path = candidate

    if not os.path.exists(json_path):
        print(f"ERROR: Could not find {json_path}")
        return

    print(f"Loading {json_path}...")
    with open(json_path, 'r') as f:
        notes_data = json.load(f)

    # Setup Scene
    # clear_scene()
    # bpy.context.scene.render.fps = FPS # Removed as per request to ignore FPS for timing

    # Calculate Time Scale
    max_time = 0.0
    min_time = float('inf')
    first_note_info = ""
    last_note_info = ""

    for note in notes_data:
        for event in note['events']:
            if event['type'] == 'noteOn':
                if event['time'] > max_time:
                    max_time = event['time']
                    last_note_info = f"Note: {note['name']}, Track: {event.get('trackName', 'Unknown')}"
                if event['time'] < min_time:
                    min_time = event['time']
                    first_note_info = f"Note: {note['name']}, Track: {event.get('trackName', 'Unknown')}"

    if max_time == 0:
        print("Warning: No noteOn events found or max time is 0.")
        time_scale = 1.0
        time_offset = 0.0
    else:
        if SYNC_MODE == "FPS":
            time_scale = TARGET_FPS
            time_offset = 0.0
            print(f"--------------------------------------------------")
            print(f"DEBUG INFO FOR SYNC (FPS MODE):")
            print(f"Target FPS: {TARGET_FPS}")
            print(f"First NoteOn Time: {min_time:.4f}s")
            print(f"Last NoteOn Time:  {max_time:.4f}s")
            print(f"Estimated Last Frame: {int(max_time * time_scale)}")
            print(f"--------------------------------------------------")
        else:
            # Calculate Scale and Offset to map [min_time, max_time] -> [FIRST_FRAME, LAST_FRAME]
            # Target_Frame = Time * Scale + Offset
            # FIRST_FRAME = min_time * Scale + Offset
            # LAST_FRAME = max_time * Scale + Offset
            # Subtracting: (LAST_FRAME - FIRST_FRAME) = (max_time - min_time) * Scale

            midi_duration = max_time - min_time
            target_duration = LAST_NOTEON_EVENT_FRAME_NUMBER - FIRST_NOTEON_EVENT_FRAME_NUMBER

            if midi_duration == 0:
                time_scale = 1.0
            else:
                time_scale = target_duration / midi_duration

            # Offset = FIRST_FRAME - min_time * Scale
            time_offset = FIRST_NOTEON_EVENT_FRAME_NUMBER - (min_time * time_scale)

            print(f"--------------------------------------------------")
            print(f"DEBUG INFO FOR SYNC (RANGE MODE):")
            print(f"First NoteOn Time: {min_time:.4f}s ({first_note_info})")
            print(f"Last NoteOn Time:  {max_time:.4f}s ({last_note_info})")
            print(f"Target First Frame: {FIRST_NOTEON_EVENT_FRAME_NUMBER}")
            print(f"Target Last Frame:  {LAST_NOTEON_EVENT_FRAME_NUMBER}")
            print(f"Calculated Scale:   {time_scale:.4f} frames/second")
            print(f"Calculated Offset:  {time_offset:.4f} frames")
            print(f"--------------------------------------------------")

    # --------------------------------------------------------------------------
    # Collection Management (Idempotency)
    # --------------------------------------------------------------------------

    # Define the collections we manage
    col_names = {
        "main": "PianoStrings",
        "masters": "PianoStrings_Masters",
        "lights": "Piano String Area Lights"
    }

    collections = {}

    for key, name in col_names.items():
        if name in bpy.data.collections:
            col = bpy.data.collections[name]
            print(f"Collection '{name}' exists. Clearing {len(col.objects)} objects...")
            obs = [o for o in col.objects]
            for ob in obs:
                bpy.data.objects.remove(ob, do_unlink=True)
            collections[key] = col
        else:
            col = bpy.data.collections.new(name)
            bpy.context.scene.collection.children.link(col)
            collections[key] = col

    # Create Masters
    master_peg, master_sphere = create_master_objects(collections["masters"])

    # Create Parent Empties
    # PianoStrings Parent
    piano_strings_parent = bpy.data.objects.new("PianoStrings_Parent", None)
    piano_strings_parent.empty_display_type = 'PLAIN_AXES'
    collections["main"].objects.link(piano_strings_parent)

    # Piano String Area Lights Parent
    lights_parent = bpy.data.objects.new("PianoStringAreaLights_Parent", None)
    lights_parent.empty_display_type = 'PLAIN_AXES'
    collections["lights"].objects.link(lights_parent)

    # Create Strings
    for i, note_obj in enumerate(notes_data):
        name = note_obj['name']
        length = note_obj['length']
        diameter = note_obj['diameter']
        events = note_obj['events']

        y_pos = -i * STRING_SPACING_X

        # Calculate Frequency
        freq = get_freq_from_note_name(name)

        # Create Posts
        create_post(master_peg, master_sphere, 0, y_pos, POST_HEIGHT, f"Post_Start_{name}", collections["main"], piano_strings_parent)
        create_post(master_peg, master_sphere, -length, y_pos, POST_HEIGHT, f"Post_End_{name}", collections["main"], piano_strings_parent)

        # Create String
        create_piano_string(f"String_{name}", name, y_pos, length, diameter, events, freq, time_scale, time_offset, collections["main"], collections["lights"], piano_strings_parent, lights_parent)

    print("Done generating piano strings!")

if __name__ == "__main__":
    main()

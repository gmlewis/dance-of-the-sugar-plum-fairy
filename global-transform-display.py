bl_info = {
    "name": "Global Transform Display",
    "author": "Your Name",
    "version": (1, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > Tool Tab",
    "description": "Display global coordinates and rotation",
    "category": "3D View",
}

import bpy
import math
from bpy.types import Panel

class VIEW3D_PT_global_transform(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_label = "Global Transform"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        if obj:
            world_pos = obj.matrix_world.translation
            world_rot = obj.matrix_world.to_euler('XYZ')

            # Convert radians to degrees
            world_rot_deg_x = math.degrees(world_rot.x)
            world_rot_deg_y = math.degrees(world_rot.y)
            world_rot_deg_z = math.degrees(world_rot.z)

            box = layout.box()
            box.label(text=f"Object: {obj.name}")

            col = box.column(align=True)
            col.label(text="Global Location:")
            row = col.row(align=True)
            row.label(text=f"X: {world_pos.x:.6f}")
            row = col.row(align=True)
            row.label(text=f"Y: {world_pos.y:.6f}")
            row = col.row(align=True)
            row.label(text=f"Z: {world_pos.z:.6f}")

            col = box.column(align=True)
            col.label(text="Global Rotation (degrees):")
            row = col.row(align=True)
            row.label(text=f"X: {world_rot_deg_x:.6f}°")
            row = col.row(align=True)
            row.label(text=f"Y: {world_rot_deg_y:.6f}°")
            row = col.row(align=True)
            row.label(text=f"Z: {world_rot_deg_z:.6f}°")
        else:
            layout.label(text="No active object")

def register():
    bpy.utils.register_class(VIEW3D_PT_global_transform)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_global_transform)

if __name__ == "__main__":
    register()
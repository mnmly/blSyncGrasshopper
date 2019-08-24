import bpy

class MNML_PT_Panel(bpy.types.Panel):
    bl_idname = 'MNML_PT_Panel'
    bl_label = 'MNML Panel'
    bl_category = 'Test Addon'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator('mnml.websocket', text='Blender WebSocket')
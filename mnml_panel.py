import bpy

class MNML_PT_Panel(bpy.types.Panel):
    bl_idname = 'MNML_PT_Panel'
    bl_label = 'MNML Panel'
    bl_category = 'MNML'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    def draw(self, context):
        layout = self.layout
        layout.row().label(text=f"Number of Connection: {context.scene.mnml_server_connection_count}")
        row = layout.row()
        row.operator('mnml.websocket', text=('Stop WebSocket Server' if context.scene.mnml_server_running else 'Start WebSocket Server'))
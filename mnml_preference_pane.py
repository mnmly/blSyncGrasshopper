import bpy

class MNML_PT_Preference(bpy.types.AddonPreferences):
    bl_idname = __package__
    port: bpy.props.IntProperty(default=1235, name="Port")
    host: bpy.props.StringProperty(default="localhost", name="Host")
    auto_start: bpy.props.BoolProperty(default=False, name="Auto Start Server")

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, 'auto_start', expand=True)
        row = layout.row()
        row.prop(self, 'host')
        row.prop(self, 'port')
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

bl_info = {
    "name" : "Blender WebSocket",
    "author" : "Hiroaki Yamane",
    "description" : "",
    "blender" : (2, 80, 0),
    "version" : (0, 0, 1),
    "location" : "",
    "warning" : "",
    "category" : "Generic"
}

import bpy
import time
import threading

from .mnml_panel import MNML_PT_Panel
from .mnml_websocket_op import MNML_OT_WebSocket
from .mnml_websocket_op import stop_server
from .mnml_preference_pane import MNML_PT_Preference


#
# classes to register
#
classes = (
    MNML_OT_WebSocket,
    MNML_PT_Panel,
    MNML_PT_Preference
)
#
# register
#
def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.mnml_server_running = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.mnml_server_connection_count = bpy.props.IntProperty(default=0)

    addons = bpy.context.preferences.addons
    name = __package__
    if name in addons:
        # TODO: It should auto start server
        if addons[name].preferences.auto_start:
            bpy.ops.mnml.websocket(host=addons[name].preferences.host,
                                   port=addons[name].preferences.port)

#
# unregister()
#    
def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.mnml_server_running
    del bpy.types.Scene.mnml_server_connection_count



# Need to check when blender quits...
checking_thread = None
running = threading.Event()
running.set()

def check_threads():
    global checking_thread
    while running.is_set():
        time.sleep(1)
        for thread in threading.enumerate():
            if thread.name == 'MainThread' and not thread.is_alive():
                stop_server()
                running.clear()

checking_thread = threading.Thread(target=check_threads, daemon=True)
checking_thread.start()

if __name__ == "__main__":
    register()
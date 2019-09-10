import re
import bpy
import json
import asyncio
import functools
import datetime
import threading
import mathutils
import websockets

connected = set()
import_log = dict()
loop = None
thread = None
server = None
stop_future = None
filepath = None
camera_info = None

def stop_server():
    global loop
    global server
    global stop_future
    global thread
    global connected

    for connection in connected:
        loop.call_soon_threadsafe(connection.close, None)

    if server != None:
        loop.call_soon_threadsafe(server.close, None)
    if loop != None and thread != None and thread.is_alive():
        loop.call_soon_threadsafe(stop_future.set_result, None)
        loop.call_soon_threadsafe(thread.join)

class MNML_OT_WebSocket(bpy.types.Operator):
    
    """Websocket server"""       # Use this as a tooltip for menu items and buttons.
    bl_idname = "mnml.websocket"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Run WebSocket Server"   # Display name in the interface.

    _timer = None
    _running = False

    host: bpy.props.StringProperty(name="Host", default='localhost')
    port: bpy.props.IntProperty(name="Port", default=1235, min=1000, max=99999)

    def execute(self, context):        # execute() is called when running the operator.
        running = context.scene.mnml_server_running
        if running:
            self._running = False
            self.stop_server()
        else:
            self._running = True
            self.start_server(self.host, self.port)
        context.scene.mnml_server_running = self._running
        self.report({'INFO'}, f'Server is running at {self.host}:{self.port}' if self._running else 'Server is stopped')
        return {'FINISHED'} 


    def invoke(self, context, event):
        self.report({'INFO'}, f'INVOKED')
        self.execute(context)
        self._timer = context.window_manager.event_timer_add(1/30, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        self._timer = None
        return None

    def look_at(self, obj_camera, point):
        loc_camera = obj_camera.matrix_world.to_translation()
        direction = point - loc_camera
        # point the cameras '-Z' and use its 'Y' as up
        rot_quat = direction.to_track_quat('-Z', 'Y')

        # assume we're using euler rotation
        obj_camera.rotation_euler = rot_quat.to_euler()


    def modal(self, context, event):
        global filepath
        global import_log
        global camera_info

        # Update Camera
        if camera_info != None:
            camera_name = camera_info['name']
            if camera_name in bpy.data.objects:
                obj_camera = bpy.data.objects[camera_name]
                p = camera_info['position']
                t = camera_info['target']
                location = [float(p[0]), float(p[1]), float(p[2])]
                target = [float(t[0]), float(t[1]), float(t[2])]
                obj_camera.location = location
                obj_camera.data.lens = camera_info['focalLength']
                self.look_at(obj_camera, mathutils.Vector(target))
            camera_info = None

        # Alembic
        collections = bpy.data.collections

        # print(f"{datetime.datetime.now()} --- {event.type}: {filepath}")
        if context.scene.mnml_server_connection_count != len(connected):
            context.scene.mnml_server_connection_count = len(connected)

        if filepath == None:
            # Set flag for importing files       
            for (collection_name, _filepaths) in import_log.items():
                if collection_name in collections and len(collections[collection_name].objects) > 0:
                    # importing has done!
                    if len(import_log[collection_name]) > 1:
                        _path = import_log[collection_name][-1]
                        filepath = _path + '#' + collection_name
                        import_log[collection_name] = [_path]
                    elif len(import_log[collection_name]) == 1:
                        import_log[collection_name] = []
                        # Adjust splines
                        curves = [curve for curve in collections[collection_name].objects if curve.type =='CURVE']
                        self.repair_curves(curves, context)

        if filepath != None:

            [_path, collection_name] = filepath.split('#')

            # collection_name must be parsed, it not, kill it.
            if collection_name == None:
                filepath = None
                return {'PASS_THROUGH'}

            # Logs importing history
            if collection_name in import_log:
                import_log[collection_name].append(_path)
            else:
                import_log[collection_name] = [_path]
            self.import_alembic(context, _path, collection_name)
            filepath = None

        return {'PASS_THROUGH'}

    # Repair inaccurately represented curves from Blender imports
    def repair_curves(self, curves, context):
        mat = bpy.data.materials.get('Line')
        if mat is None:
            mat = bpy.data.materials.new(name='Line')
        for curve in curves:
            for spline in curve.data.splines:
                result = re.search('d(\d+)$', curve.name)
                is_closed = re.search('_closed_', curve.name)
                if result != None:
                    degree = int(result.groups()[0])
                    spline.order_u = degree + 1
                    spline.order_v = degree + 1
                if spline.order_u <= 2:
                    spline.type = 'POLY'
                else:
                    num_points = len(spline.points)
                    spline.resolution_v = spline.resolution_u = 10 * num_points
                if is_closed:
                    spline.use_cyclic_u = spline.use_cyclic_v = True
            curve.data.bevel_depth = context.scene.mnml_properties['import_spline_thickness']
            curve.data.materials.append(mat)

    def import_alembic(self, context, path, collection_name):

        # remove previously created collection
        if collection_name in bpy.data.collections:
            old_collection = bpy.data.collections[collection_name]
            for obj in old_collection.objects:
                bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.collections[0].children.unlink(old_collection)
            bpy.data.collections.remove(old_collection, do_unlink=True)
        new_collection = bpy.data.collections.new(collection_name)
        bpy.data.collections[0].children.link(new_collection)

        # Select it as active layer before imports
        index = bpy.data.collections[0].children.find(collection_name)
        context.view_layer.active_layer_collection = context.view_layer.layer_collection.children[0].children[index]
        return bpy.ops.wm.alembic_import(filepath=path, as_background_job=True)

    def start_server(self, host, port):

        global loop
        global thread
        global stop_future

        asyncio.set_event_loop(None)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stop_future = loop.create_future()

        thread = threading.Thread(target=self.run_loop, args=[loop, self.echo_server, self.handler, host, port, stop_future])
        thread.start()

    def stop_server(self):
        stop_server()

    async def handler(self, websocket, path):

        global connected
        global filepath
        global loop
        global camera_info

        connected.add(websocket)

        try:
            while loop.is_running():
                async for message in websocket:
                    j = json.loads(message)
                    if j['action'] == 'update':
                        filepath = j['filepath'] + "#" + j['collectionName']
                    elif j['action'] == 'camera':
                        camera_info = j['info']
            raise Exception('loop ended')
        finally:
            connected.remove(websocket)
            print(f'Remaining Connection: {len(connected)}')

    async def echo_server(self, handler, host, port, stop_future):
        async with websockets.serve(handler, host, port):
            await stop_future

    def run_loop(self, _loop, serve, handler, host, port, stop):
        global server
        server = serve(handler, host, port, stop)
        _loop.run_until_complete(server)
        _loop.close()
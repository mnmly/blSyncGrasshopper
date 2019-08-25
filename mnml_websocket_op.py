import bpy
import json
import asyncio
import functools
import datetime
import threading
import websockets
from queue import Queue


connected = set()
loop = None
thread = None
server = None
stop_future = None
filepath = None

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

    port: bpy.props.IntProperty(name="Port", default=1235, min=1000, max=99999)
    host: bpy.props.StringProperty(name="Host", default='localhost')

    def execute(self, context):        # execute() is called when running the operator.
        running = context.scene.mnml_server_running
        if running:
            self._running = False
            self.stop_server()
        else:
            self._running = True
            self.start_server()
        context.scene.mnml_server_running = self._running
        self.report({'INFO'}, f'Server is running at {self.host}:{self.port}' if self._running else 'Server is stopped')


    def invoke(self, context, event):
        print('invoke')
        self.execute(context)
        self._timer = context.window_manager.event_timer_add(1/30, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        self._timer = None
        return None

    def modal(self, context, event):
        global filepath
        # print(f"{datetime.datetime.now()} --- {event.type}: {filepath}")
        if context.scene.mnml_server_connection_count != len(connected):
            context.scene.mnml_server_connection_count = len(connected)
        if filepath != None:
            _filepath = filepath
            filepath = None
            [_path, collection_name] = _filepath.split(':')
            if collection_name != None:
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
            res = bpy.ops.wm.alembic_import(filepath=_path, as_background_job=True)
            print(res)
        return {'PASS_THROUGH'}

    def start_server(self):

        global loop
        global thread
        global stop_future

        asyncio.set_event_loop(None)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stop_future = loop.create_future()

        thread = threading.Thread(target=self.run_loop, args=[loop, self.echo_server, self.handler, self.host, self.port, stop_future])
        thread.start()

    def stop_server(self):
        stop_server()

    async def handler(self, websocket, path):

        global connected
        global filepath
        global loop

        connected.add(websocket)

        try:
            while True:
                async for message in websocket:
                    j = json.loads(message)
                    if j['action'] == 'update':
                        filepath = j['filepath'] + ":" + j['collection_name']
                    await asyncio.wait([ws.send(message) for ws in connected])
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
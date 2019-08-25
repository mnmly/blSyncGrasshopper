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
    if server != None:
        loop.call_soon_threadsafe(server.close, None)
    if loop != None and thread != None and thread.is_alive():
        loop.call_soon_threadsafe(stop_future.set_result, None)
        loop.call_soon_threadsafe(thread.join)

class MNML_OT_WebSocket(bpy.types.Operator):
    
    """My Object Moving Script"""       # Use this as a tooltip for menu items and buttons.
    bl_idname = "mnml.websocket"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Run WebSocket Server"   # Display name in the interface.

    _timer = None 

    port: bpy.props.IntProperty(name="Port", default=1235, min=1000, max=99999)
    host: bpy.props.StringProperty(name="Host", default='localhost')
    running: bpy.props.BoolProperty(name="Running", default=False)
    prev_object_count: bpy.props.IntProperty(name="Previous object count", default=0)

    def execute(self, context):        # execute() is called when running the operator.
        if self.running:
            self.stop_server()
            self.running = False
        else:
            self.start_server()
            self.running = True
        self.report({'INFO'}, f'Server is running at {self.host}:{self.port}' if self.running else 'Server is stopped')

    def invoke(self, context, event):
        print('invoke')
        self.execute(context)
        self._timer = context.window_manager.event_timer_add(1/30, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

     def cancel(self, context):
        context.window_manager.modal_handler_add(self)
        context.window_manager.event_timer_remove(self._timer)
        self._timer = None
        return {'CANCELLED'}

    def modal(self, context, event):
        global filepath
        # print(f"{datetime.datetime.now()} --- {event.type}: {filepath}")
        if filepath != None:
            _filepath = filepath
            filepath = None
            [_path, namesString] = _filepath.split(':')
            names = namesString.split(',')
            for name in names:
                if name in bpy.data.objects:
                    bpy.data.objects.remove(bpy.data.objects[name])
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
        print(websocket)
        dir(websocket)

        try:
            while True:
                async for message in websocket:
                    j = json.loads(message)
                    if j['action'] == 'update':
                        filepath = j['filepath'] + ":" + ",".join(j['objects'])
                    print(message)
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
import bpy
import asyncio
import threading
import websockets

connected = set()
loop = None
thread = None
stop_future = None

def stop_server():
    global loop
    if loop != None and thread != None and thread.is_alive():
        loop.call_soon_threadsafe(stop_future.set_result, None)
        loop.call_soon_threadsafe(thread.join)

class MNML_OT_WebSocket(bpy.types.Operator):
    
    """My Object Moving Script"""       # Use this as a tooltip for menu items and buttons.
    bl_idname = "mnml.websocket"        # Unique identifier for buttons and menu items to reference.
    bl_label = "Run WebSocket Server"   # Display name in the interface.

    port: bpy.props.IntProperty(name="Port", default=1235, min=1000, max=99999)
    host: bpy.props.StringProperty(name="Host", default='localhost')
    running: bpy.props.BoolProperty(name="Running", default=False)

    def execute(self, context):        # execute() is called when running the operator.
        if self.running:
            self.stop_server()
            self.running = False
        else:
            self.start_server()
            self.running = True
        self.report({'INFO'}, f'Server is running at {self.host}:{self.port}' if self.running else 'Server is stopped')
        return {'FINISHED'}            # Lets Blender know the operator finished successfully.

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
        data = await websocket.recv()
        connected.add(websocket)
        await asyncio.wait([ws.send(data) for ws in connected])

    async def echo_server(self, handler, host, port, stop_future):
        async with websockets.serve(handler, host, port):
            await stop_future

    def run_loop(self, _loop, serve, handler, host, port, stop):
        _loop.run_until_complete(serve(handler, host, port, stop))
        _loop.close()
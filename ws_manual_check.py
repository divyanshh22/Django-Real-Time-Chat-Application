import asyncio
import websockets
import json

async def run_ws_check():
    try:
        uri = 'ws://127.0.0.1:8000/ws/chat/testuser/'
        async with websockets.connect(uri) as ws:
            print('Connected!')
            await ws.send(json.dumps({'type': 'message', 'text': 'hello'}))
            resp = await ws.recv()
            print('Received:', resp)
    except Exception as e:
        print('Error:', e)

if __name__ == '__main__':
    asyncio.run(run_ws_check())
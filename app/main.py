import redis
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
import json
import random
from datetime import datetime
from fastapi.responses import FileResponse

app = FastAPI()

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=6379,
    decode_responses=True
)

@app.get("/")
async def get():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    index_path = os.path.join(base_dir, "frontend", "index.html")
    return FileResponse(index_path)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_data = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        user_name = f"Guest_{random.randint(1000, 9999)}"
        self.user_data[websocket] = user_name
        redis_client.sadd("online_users", user_name)

        # Send recent chat history
        history = redis_client.lrange("chat_history", 0, -1)
        for msg in history:
            await websocket.send_text(json.dumps({
                "type": "history",
                "data": json.loads(msg)
            }))

        # Broadcast connection
        await self.broadcast_system_message(f"{user_name} has joined the chat.")
        await self.send_personal_message(
            f"Welcome to the chat! You are connected as {user_name}.",
            websocket
        )
        await self.broadcast_stats()

    def disconnect(self, websocket: WebSocket):
        user_name = self.user_data.get(websocket, "Unknown")
        redis_client.srem("online_users", user_name)

        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        if websocket in self.user_data:
            del self.user_data[websocket]

        return user_name

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(json.dumps({
            "type": "system",
            "message": message
        }))

    async def broadcast_chat_message(self, message: str, sender: WebSocket):
        sender_name = self.user_data.get(sender, "Unknown")
        cur_time = datetime.now().strftime("%I:%M:%S %p")

        # Create message object
        message_data = {
            "username": sender_name,
            "message": message,
            "time": cur_time
        }

        # Store message in Redis
        redis_client.rpush("chat_history", json.dumps(message_data))

        # Keep only the last 50 messages
        redis_client.ltrim("chat_history", -50, -1)

        # Broadcast to connected users
        for connection in self.active_connections:
            await connection.send_text(json.dumps({
                "type": "chat",
                "username": sender_name,
                "message": message,
                "time": cur_time,
                "isSelf": sender == connection
            }))

    async def broadcast_system_message(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(json.dumps({
                "type": "system",
                "message": message
            }))

    async def broadcast_stats(self):
        count = redis_client.scard("online_users")

        for connection in self.active_connections:
            await connection.send_text(json.dumps({
                "type": "stats",
                "count": count
            }))

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast_chat_message(data, websocket)
    except WebSocketDisconnect:
        user_name = manager.disconnect(websocket)
        await manager.broadcast_system_message(f"{user_name} has left the chat.")
        await manager.broadcast_stats()

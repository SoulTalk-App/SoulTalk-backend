import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.jwt_service import jwt_service

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    def register(self, user_id: str, websocket: WebSocket):
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket registered: user {user_id}")

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        logger.info(f"WebSocket disconnected: user {user_id}")

    async def send_to_user(self, user_id: str, data: dict):
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                logger.warning(f"Failed to send WS message to user {user_id}")
                self.disconnect(user_id)


connection_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint. Client must send a valid JWT access token
    as the first message after connecting.
    """
    await websocket.accept()

    # Wait for auth token as first message
    try:
        token = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    payload = jwt_service.decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    connection_manager.register(user_id, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(user_id)

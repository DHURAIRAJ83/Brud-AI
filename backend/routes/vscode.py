"""
VS Code Extension Workspace Gateway Route
------------------------------------------
Handles WebSocket connections from the VS Code Sidebar Extension,
routes workspace commands (open_file, search_code, run_tests),
processes chat stream events from VS Code view, and registers VS Code device.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from models.device import DeviceModel, DeviceRegister, DeviceStatus, OSType, DeviceType, DeviceHeartbeat
from models.base import db_manager

logger = logging.getLogger(__name__)
router = APIRouter()

class VSCodeConnectionManager:
    """Manages active WebSocket connections from the VS Code extension."""
    
    def __init__(self):
        # Maps session_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # Maps session_id -> device_id (registered in registry)
        self.device_ids: Dict[str, str] = {}
        # Maps msg_id -> future (for RPC command responses)
        self._pending_responses: Dict[str, asyncio.Future] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info("VS Code Extension connected for session: %s", session_id)

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.device_ids:
            del self.device_ids[session_id]
        logger.info("VS Code Extension disconnected for session: %s", session_id)

    async def send_command(self, session_id: str, command: str, params: dict, timeout: float = 30.0) -> Optional[dict]:
        """Send a workspace action command to the extension and wait for a response."""
        ws = self.active_connections.get(session_id)
        if not ws:
            logger.warning("No active VS Code connection for session: %s", session_id)
            return None
        
        msg_id = f"cmd_{uuid.uuid4().hex[:8]}"
        future = asyncio.get_event_loop().create_future()
        self._pending_responses[msg_id] = future
        
        payload = {
            "type": "command",
            "id": msg_id,
            "command": command,
            "params": params
        }
        
        try:
            await ws.send_text(json.dumps(payload))
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except Exception as e:
            logger.error("Error sending command %s to VS Code: %s", command, e)
            return {"status": "error", "message": str(e)}
        finally:
            if msg_id in self._pending_responses:
                del self._pending_responses[msg_id]

    def resolve_response(self, msg_id: str, data: dict):
        future = self._pending_responses.get(msg_id)
        if future and not future.done():
            future.set_result(data)

    def is_connected(self, session_id: str) -> bool:
        return session_id in self.active_connections


# Global Connection Manager
vscode_manager = VSCodeConnectionManager()


@router.websocket("/ws/vscode")
async def websocket_vscode_endpoint(websocket: WebSocket):
    """
    WebSocket handler for VS Code Extension.
    Supports registration, heartbeat checks, RPC command responses, and chat execution.
    """
    session_id = str(uuid.uuid4())
    await vscode_manager.connect(session_id, websocket)
    
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "detail": "Invalid JSON"}))
                continue
                
            msg_type = data.get("type")
            
            # 1. Registration Handler
            if msg_type == "register":
                user_id = data.get("user_id", "admin-user-123")
                session_id = data.get("session_id", session_id)
                
                # Make sure the session connection map is correct if a custom session_id is sent
                if session_id not in vscode_manager.active_connections:
                    vscode_manager.active_connections[session_id] = websocket
                
                logger.info("Registering VS Code extension device for session: %s", session_id)
                try:
                    # Register VS Code Device Model in DB
                    device_register = DeviceRegister(
                        device_name="VS Code Workspace",
                        device_type=DeviceType.VSCODE,
                        os_type=OSType.VSCODE,
                        capabilities=[
                            "vscode.open_file", "vscode.search_code", 
                            "vscode.run_tests", "vscode.create_project"
                        ]
                    )
                    # Check if device already registered for this user
                    existing = await db_manager.fetch_one(
                        "SELECT id FROM devices WHERE user_id = ? AND device_type = ?", 
                        (user_id, DeviceType.VSCODE.value)
                    )
                    
                    if existing:
                        device_id = existing["id"]
                        await DeviceModel.set_status(device_id, DeviceStatus.ONLINE)
                    else:
                        device = await DeviceModel.register(user_id, device_register)
                        device_id = device["id"]
                        await DeviceModel.set_status(device_id, DeviceStatus.ONLINE)
                        
                    # Update heartbeat timestamp
                    now = datetime.now(timezone.utc).isoformat()
                    await db_manager.execute(
                        "UPDATE devices SET last_heartbeat = ? WHERE id = ?", (now, device_id)
                    )
                    
                    vscode_manager.device_ids[session_id] = device_id
                    await websocket.send_text(json.dumps({
                        "type": "register_response",
                        "status": "success",
                        "device_id": device_id,
                        "session_id": session_id
                    }))
                except Exception as ex:
                    logger.error("VS Code registration failed: %s", ex)
                    await websocket.send_text(json.dumps({
                        "type": "register_response",
                        "status": "error",
                        "detail": str(ex)
                    }))
                    
            # 2. Command Response Resolver
            elif msg_type == "response":
                msg_id = data.get("id")
                if msg_id:
                    vscode_manager.resolve_response(msg_id, data.get("result", {}))
                    
            # 3. Heartbeat Tracker
            elif msg_type == "heartbeat":
                device_id = vscode_manager.device_ids.get(session_id)
                if device_id:
                    await DeviceModel.heartbeat(device_id, DeviceHeartbeat(
                        agent_version=data.get("agent_version", "1.0.0"),
                        system_info=data.get("system_info", {}),
                        capabilities=data.get("capabilities", [])
                    ))
                    
            # 4. Chat Message Handler
            elif msg_type == "chat_message":
                msg_text = data.get("message", "").strip()
                chat_session = data.get("session_id", session_id)
                if msg_text:
                    from routes.stream import _build_stream
                    try:
                        async for sse_chunk in _build_stream(msg_text, chat_session):
                            json_part = sse_chunk.removeprefix("data: ").strip()
                            if json_part:
                                await websocket.send_text(json.dumps({
                                    "type": "chat_token",
                                    "data": json.loads(json_part)
                                }))
                    except Exception as e:
                        await websocket.send_text(json.dumps({
                            "type": "chat_error",
                            "message": str(e)
                        }))
                        
    except WebSocketDisconnect:
        vscode_manager.disconnect(session_id)
    except Exception as e:
        logger.error("WebSocket VS Code route error: %s", e)
        vscode_manager.disconnect(session_id)


@router.get("/vscode/status", summary="Check VS Code extension connection status")
async def get_vscode_status(session_id: Optional[str] = None):
    """Returns whether VS Code is currently connected for the given session ID, or if any connection is active."""
    if session_id:
        connected = vscode_manager.is_connected(session_id)
        device_id = vscode_manager.device_ids.get(session_id, "")
        return {
            "connected": connected,
            "session_id": session_id,
            "device_id": device_id
        }
    else:
        connected = len(vscode_manager.active_connections) > 0
        sessions = list(vscode_manager.active_connections.keys())
        first_session = sessions[0] if sessions else ""
        device_id = vscode_manager.device_ids.get(first_session, "") if first_session else ""
        return {
            "connected": connected,
            "sessions": sessions,
            "device_id": device_id
        }


from pydantic import BaseModel

class VSCodeContextUpdateRequest(BaseModel):
    active_file: Optional[str] = None
    cursor_line: Optional[int] = None
    active_symbol: Optional[str] = None

@router.post("/vscode/status/context", summary="Update current VS Code focus context")
async def update_vscode_context(req: VSCodeContextUpdateRequest):
    """Updates the active workspace context (active file, cursor line, active symbol) from VS Code."""
    from ai.project_context import project_context_manager
    project_context_manager.set_context(
        active_file=req.active_file,
        cursor_line=req.cursor_line,
        active_symbol=req.active_symbol
    )
    return {"status": "success", "context": project_context_manager.get_context()}

@router.get("/vscode/status/context", summary="Get current VS Code active context")
async def get_vscode_context():
    """Retrieves the current active workspace context, checking for expiration."""
    from ai.project_context import project_context_manager
    return {"status": "success", "context": project_context_manager.get_context()}


class VSCodeExecuteRequest(BaseModel):
    command: str
    params: dict
    session_id: Optional[str] = None


@router.post("/vscode/execute", summary="Execute a command via the VS Code extension")
async def execute_vscode_command(req: VSCodeExecuteRequest):
    """Sends a command to the VS Code Extension via WebSocket and returns the result."""
    session_id = req.session_id
    if not session_id:
        if not vscode_manager.active_connections:
            return {"status": "error", "message": "No active VS Code extension connection"}
        session_id = list(vscode_manager.active_connections.keys())[0]
        
    result = await vscode_manager.send_command(session_id, req.command, req.params)
    return result



from fastapi import Query
from ai.workspace_indexer import workspace_indexer

@router.post("/vscode/index/scan", summary="Trigger a full workspace codebase re-scan")
async def scan_workspace():
    """Forces the workspace indexer to parse the codebase directory tree."""
    return await workspace_indexer.scan()


@router.get("/vscode/index/query", summary="Query the indexed codebase symbols")
async def query_workspace_index(q: str = Query(..., min_length=1, description="Symbol query")):
    """Searches indexed routes, functions, and classes matching the query term."""
    return {
        "query": q,
        "results": await workspace_indexer.query(q),
        "app_creation": workspace_indexer.find_app_creation() if "app" in q.lower() or "fastapi" in q.lower() else None
    }

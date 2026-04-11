"""ACP Multiplex sub-module.

Provides a single WebSocket endpoint that multiplexes event streams for
multiple agent sessions over one connection.

``WS /acp/multiplex`` -- send ``STREAM_OPEN`` / ``STREAM_CLOSE`` frames to
subscribe / unsubscribe from session event buses.  Events arrive as
``STREAM_DATA`` frames.  30-second ``PING`` / ``PONG`` keepalive.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from tldw_Server_API.app.api.v1.endpoints.agent_client_protocol import get_session_event_bus
from tldw_Server_API.app.core.Agent_Client_Protocol.multiplex.manager import MultiplexManager

router = APIRouter(prefix="/acp", tags=["acp-multiplex"])


@router.websocket("/multiplex")
async def acp_multiplex_ws(websocket: WebSocket) -> None:
    """Multi-session event multiplexer.

    Accepts a WebSocket, creates a :class:`MultiplexManager` backed by the
    shared session event-bus registry, and loops reading client frames until
    disconnect.
    """
    await websocket.accept()
    connection_id = uuid.uuid4().hex[:12]
    logger.info("Multiplex WS connected: {}", connection_id)

    manager = MultiplexManager(
        connection_id=connection_id,
        send_fn=websocket.send_text,
        get_bus_fn=get_session_event_bus,
    )
    manager.start()

    try:
        while True:
            raw = await websocket.receive_text()
            await manager.handle_message(raw)
    except WebSocketDisconnect:
        logger.info("Multiplex WS disconnected: {}", connection_id)
    finally:
        await manager.stop()

from abc import ABC, abstractmethod
from typing import Any, Dict, Set
import logging
from asgiref.sync import async_to_sync
from marvin.utilities.asyncio import (
    is_coro,
    run_sync,
    expose_sync_method,
    ExposeSyncMethodsMixin,
)


logger = logging.getLogger("marvin")

try:
    from fastapi import WebSocket
except ImportError:
    logger.warn("fast api not installed.")

try:
    from django_eventstream import send_event
    from channels.layers import get_channel_layer
except (
    ImportError,
    Exception,
):
    logger.warn("django event stream not install")


class BaseConnectionManager(ExposeSyncMethodsMixin):
    @expose_sync_method("connect")
    async def connect_async(self, websocket: WebSocket):
        raise NotImplementedError

    @expose_sync_method("disconnect")
    def disconnect_sync(self, websocket: WebSocket):
        raise NotImplementedError

    @expose_sync_method("broadcast")
    async def broadcast_async(
        self,
        channel_id: str,
        data: str | dict,
        event: str = "message",
        channel_type: str = "ws",
    ):
        raise NotImplementedError


class CLIConnectionManager(BaseConnectionManager):
    def __init__(self):
        self.active_connections: Dict[str, Set[Any]] = {}

    @expose_sync_method("connect")
    async def connect_async(self, websocket: WebSocket, channel: str):
        print(f"CLIConnectionManager: {channel} {websocket} connected")

    @expose_sync_method("disconnect")
    def disconnect_sync(self, websocket: WebSocket, channel: str):
        print(f"CLIConnectionManager: {channel} {websocket} disconnected")

    @expose_sync_method("broadcast")
    async def broadcast_async(
        self, channel_id, data, event: str = "message", channel_type: str = "ws"
    ):
        print(f"CLIConnectionManager: {channel_id} {data} {event} {channel_type}")


class FastApiWsConnectionManager(BaseConnectionManager):
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    @expose_sync_method("connect")
    async def connect_async(self, websocket: WebSocket, channel: str):
        await websocket.accept()
        self.active_connections[channel] = websocket

    @expose_sync_method("disconnect")
    def disconnect_sync(self, websocket: WebSocket, channel: str):
        if self.active_connections.get(channel, None):
            del self.active_connections[channel]

    @expose_sync_method("broadcast")
    async def broadcast_async(
        self, channel_id, data, event: str = "message", channel_type: str = "ws"
    ):
        conn = self.active_connections.get(channel_id, None)
        if conn:
            await conn.send_json(data)


class ChannelsConnectionManager(BaseConnectionManager):
    def __init__(self):
        self.channel_layer = get_channel_layer()

    @expose_sync_method("connect")
    async def connect_async(self, websocket: WebSocket):
        # Not needed as it's handled by the consumer
        pass

    @expose_sync_method("disconnect")
    def disconnect_sync(self, websocket: WebSocket):
        # Not needed as it's handled by the consumer
        pass

    @expose_sync_method("broadcast")
    async def broadcast_async(
        self,
        channel_id: str,
        data: str | dict,
        event: str = "message",
        channel_type: str = "ws",
    ):
        if channel_type == "sse":
            send_event(channel_id, "message", data)

        else:
            channel_message = {"event": event, "type": "channel_message", "data": data}
            # check if not in an event loop
            layer = get_channel_layer()
            group = f"channel_{str(channel_id)}"
            if is_coro():
                run_sync(layer.group_send(group, channel_message))
            else:
                async_to_sync(layer.group_send)(group, channel_message)

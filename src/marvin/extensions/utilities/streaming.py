import uuid
from typing import Literal

import humps
from asgiref.sync import async_to_sync
from marvin.extensions.utilities.serialization import to_serializable
from marvin.utilities.asyncio import is_coro
from prefect.utilities.asyncutils import run_sync
from pydantic import BaseModel, Field


try:
    from channels.layers import get_channel_layer
    from django_eventstream import send_event
except ImportError:
    from .fake_streamers import get_channel_layer, send_event


def send_app_event(
    channel_id: str | uuid.UUID = Field(description="Channel ID- sse, ws channel"),
    thread_id: str | uuid.UUID = Field(description="Thread ID"),
    data: BaseModel | dict | None = Field(description="Data to send to channel"),
    event: Literal["message", "close", "error", "final"] = "message",
    message_type: str = "message",
    channel_type="ws",
    streaming: bool = Field(
        description="Is streaming set true if incrementally patching", default=False
    ),
    camel_case: bool = Field(description="Convert to camel case", default=True),
    run_id: str = None,
    patch: bool = False,
):
    """
    Send event to channel

    Args:
        channel_id: channel id to send to
        thread_id: thread id to send to
        data: data to send to channel
        event: event name to send (message, close, error, final)
        message_type: message type (message, close, error, final)
        channel_type: channel type
        streaming: is streaming set true if incrementally patching
        camel_case: convert to camel case
    """
    # dump model to dict
    if isinstance(data, BaseModel):
        data = data.model_dump(by_alias=True)
    if isinstance(data, str):
        data = {"message": data}
    if data is None:
        data = {}

    # add message type
    data["message_type"] = message_type
    data["event"] = event
    data["streaming"] = streaming
    data["patch"] = data.get("patch", False)
    data["run_id"] = run_id

    # make streamable
    data = to_serializable(data)

    if camel_case:
        data = humps.camelize(data)
    from marvin.extensions.settings import extension_settings # noqa
    
    manager = extension_settings.transport.manager
    manager.broadcast(channel_id, data)
  


async def send_app_event_async(
    channel_id: str | uuid.UUID = Field(description="Channel ID- sse, ws channel"),
    thread_id: str | uuid.UUID = Field(description="Thread ID"),
    data: BaseModel | dict | None = Field(description="Data to send to channel"),
    event: Literal["message", "close", "error", "final"] = "message",
    message_type: str = "message",
    channel_type="ws",
    streaming: bool = Field(
        description="Is streaming set true if incrementally patching", default=False
    ),
    camel_case: bool = Field(description="Convert to camel case", default=True),
    run_id: str = None,
    patch: bool = False,
):
    """
    Send event to channel
    """

    if isinstance(data, BaseModel):
        data = data.model_dump(by_alias=True)
    if isinstance(data, str):
        data = {"message": data}
    if data is None:
        data = {}

    # add message type
    data["message_type"] = message_type
    data["event"] = event
    data["streaming"] = streaming
    data["patch"] = data.get("patch", False)
    data["run_id"] = run_id

    # make streamable
    data = to_serializable(data)

    if camel_case:
        data = humps.camelize(data)

    from marvin.extensions.settings import extension_settings # noqa
    manager = extension_settings.transport.manager
    await manager.broadcast_async(channel_id, data)
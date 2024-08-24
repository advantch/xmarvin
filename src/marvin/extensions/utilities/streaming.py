import humps
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django_eventstream import send_event
from pydantic import BaseModel

from marvin.extensions.utilities.async_utils import check_event_loop
from marvin.extensions.utilities.serialization import to_serializable
from marvin.utilities.asyncio import run_async


def send_app_event(
    channel_id: str,
    thread_id: str,
    data: BaseModel | dict | None,
    event: str = "message",
    message_type: str = "message",
    channel_type="ws",
    streaming: bool = False,
    patch: bool = False,
    camel_case: bool = True,
    run_id: str = None,
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

    send_app_event(
        channel_id,
        thread_id,
        data,
        event,
    )
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
    if channel_type == "sse":
        # sse listens to thread_id stream
        send_event(channel_id, "message", data)
    else:
        channel_message = {"event": event, "type": "channel_message", "data": data}
        # check if not in an event loop
        layer = get_channel_layer()
        group = f"channel_{str(channel_id)}"
        if check_event_loop():
            layer.group_send(group, channel_message)
        else:
            async_to_sync(layer.group_send)(group, channel_message)


async def async_send_app_event(*args, **kwargs):
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

    send_app_event(
        channel_id,
        thread_id,
        data,
        event,
    )
    """
    # dump model to dict
    await run_async(send_app_event, *args, **kwargs)

import traceback
from typing import Any, Dict

from marvin.extensions.utilities.context import RunContext
from marvin.extensions.utilities.streaming import send_app_event_async
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method
from pydantic import BaseModel

from .events.base import BaseEvent


class Dispatcher(BaseModel, ExposeSyncMethodsMixin):
    """
    Handler for events
    Append 'async' to the method name to make it async
    """

    context: RunContext
    data: Dict[str, Any] | None = None
    stack: list | None = []
    channel_type: str = "ws"

    class Config:
        arbitrary_types_allowed = True

    @expose_sync_method("dispatch")
    async def dispatch_async(
        self, event: BaseEvent | None, context: RunContext | None = None
    ):
        """
        Sends event to the channel.
        In the ui these are shown as 'actions'
        They represent an instance of a `RunStep` taken by the agent.
        This is only available during the run.
        After the run all events can be fetched from the backend.

        """
        try:
            if not event:
                return
            context = context or self.context
            run_id = context.run_id
            data = {
                "message": event.model_dump(),
                "id": str(event.id_),  # unique id for the event
                "span_id": str(event.span_id),  # span id for merging and time tracking
                "message_type": "action",
                "run_id": run_id,
            }
            self.stack.append(data)
        except Exception:
            return

    @expose_sync_method("send_stream_event")
    async def send_stream_event_async(
        self,
        data,
        message_type: str = "message",
        streaming: bool = True,
        event: str = "message",
        patch: bool = False,
    ):
        try:
            await send_app_event_async(
                str(self.context.channel_id),
                str(self.context.thread_id),
                data,
                channel_type=self.channel_type,
                message_type=message_type,
                streaming=streaming,
                run_id=self.context.run_id,
                event=event,
                patch=patch,
            )
        except Exception:
            traceback.print_exc()

    @expose_sync_method("send_error")
    async def send_error_async(self, error: str):
        """
        Sends error to the channel.
        """
        await self.send_stream_event_async(
            {
                "message": {
                    "action": "error",
                    "run_id": str(self.context.run_id),
                    "error": error,
                },
            },
            message_type="error",
            event="error",
        )

    @expose_sync_method("send_close")
    async def send_close_async(self):
        """
        Sends close to the channel.
        """
        await self.send_stream_event_async(
            {
                "message": {
                    "action": "close",
                    "run_id": str(self.context.run_id),
                },
            },
            message_type="close",
            event="close",
        )

    @expose_sync_method("run_events")
    async def run_events_async(self):
        return self.stack

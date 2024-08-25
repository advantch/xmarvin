import traceback
from datetime import datetime

from datetime import datetime
import traceback
from openai import AsyncAssistantEventHandler
from openai.types.beta.assistant_stream_event import (
    ThreadRunCancelled,
    ThreadRunCompleted,
    ThreadRunFailed,
    ThreadRunRequiresAction,
    ThreadRunStepCompleted,
)
from openai.types.beta.threads import ImageFile, Message, MessageDelta
from openai.types.beta.threads.runs import RunStep, RunStepDelta
from typing_extensions import override
from litellm.types.utils import Delta

from marvin.extensions.memory.temp_memory import Memory
from marvin.extensions.utilities.dispatch import Dispatcher
from marvin.extensions.utilities.logging import logger, pretty_log
from marvin.extensions.types import ChatMessage
from marvin.extensions.utilities.assistants_api import (
    cancel_thread_run_async,
)
from marvin.extensions.utilities.context import RunContext
from marvin.extensions.utilities.cost_tracking import calculate_credits
from marvin.extensions.utilities.mappers import (
    map_content_to_block,
    run_step_to_tool_call_message,
)
from marvin.extensions.utilities.persist_files import save_assistant_image_to_storage
from marvin.extensions.utilities.serialization import to_serializable
from marvin.extensions.utilities.unique_id import generate_uuid_from_string


class DefaultAssistantEventHandler(AsyncAssistantEventHandler):
    """
    Custom event handler for OPENAI ASSISTANTS and Internal Agents
    Compatible with V2 API for assistant.
    Compatible with internal agents that use litellm

    How it works
    - handles emitted events from a Run/LocalRun object.
    - handles streamed events from the assistant
    - persists messages and steps to the provided memory
    """

    def __init__(self, print_messages: bool = True, print_steps: bool = True, **kwargs):
        self.print_messages = print_messages
        self.print_steps = print_steps
        self.messages = []
        self.steps = []
        self.context = RunContext(**kwargs.get("context"))
        self.tool_calls = []
        self._context = kwargs.get("context")
        self.memory = kwargs.get("memory") or Memory()
        self.cache = kwargs.get("cache") or {}
        super().__init__()

        self.dispatcher = Dispatcher(context=self.context)
        self.status_stack = []
        self.previous_event = None
        self.processed_steps = []
        self.max_runs = 20
        self.openai_run_id = None
        self.openai_thread_id = kwargs.get("openai_thread_id")
        self.openai_assistant_id = kwargs.get("openai_assistant_id")
        self.persist_data = kwargs.get("persist_data", True)
        self.tool_outputs = []

    @override
    async def on_message_delta(
        self, delta: MessageDelta | Delta, snapshot: Message
    ) -> None:
        """
        Handle partial message updates from the assistant.

        Args:
            delta (MessageDelta): The message delta received from the assistant.
            snapshot (Message): The accumulated snapshot of the message.

        This function streams the message delta to the frontend and
        converts it to an internal ChatMessage for compatibility with other agents.
        """

        m = ChatMessage(
            id=generate_uuid_from_string(snapshot.id),
            role=snapshot.role,
            content=map_content_to_block(delta.content, is_delta=True),
            run_id=self.context.run_id,
            thread_id=self.context.thread_id,
            metadata={
                "streaming": False,
                "run_id": self.context.run_id,
                "type": "message",
            },
        )

        data = {"message": m}
        await self.dispatcher.send_stream_event_async(data, patch=False)

    @property
    def storage(self):
        """
        Context storage.
        If anything needs to be saved to the context, it should be saved here.
        
        For openai assistants handlers are instantiated per stream,
        context and by extension storage is persisted.
        """
        return self._context["storage"]

    async def check_run_stop(self):
        """
        Check if the run should stop.
        We need reference to the current run to do this.
        """
        run_stop_cache_key = f"run:stop:{self.context.run_id}"

        if (
            len(self.steps) > self.max_runs
            or self.cache.get(run_stop_cache_key)
            and self.openai_run_id
        ):
            run_id = self.openai_run_id
            thread_id = self.openai_thread_id
            await cancel_thread_run_async(thread_id, run_id)

    @override
    async def on_message_done(self, message: Message | ChatMessage) -> None:
        """
        Handle the completion of a message from the assistant.

        Args:
            message (Message): The completed message.

        This function saves the completed message to the database.
        """

        # save to db
        m = message
        if isinstance(message, Message):
            m = ChatMessage(
                id=generate_uuid_from_string(message.id),
                role=message.role,
                content=map_content_to_block(message.content, is_delta=False),
                run_id=message.run_id,
                thread_id=message.thread_id,
                metadata={
                    "streaming": False,
                    "run_id": self.context.run_id,
                    "type": "message",
                },
            )
        self.storage['messages'].append(m)
        await self.memory.put_async(m)
        await self.check_run_stop()

    @override
    async def on_run_step_delta(self, delta: RunStepDelta, snapshot: RunStep) -> None:
        """
        Handle partial updates of a run step.

        Args:
            delta (RunStepDelta): The run step delta received from the assistant.
            snapshot (RunStep): The accumulated snapshot of the run step.

        This function handles updates related to tool calls and dispatches events accordingly.
        """
        if self.openai_run_id is None:
            self.openai_run_id = snapshot.run_id
        details = snapshot.step_details
        if hasattr(details, "tool_calls"):
            m = run_step_to_tool_call_message(snapshot, self.context, is_delta=True)
            data = {"message": m}
            await self.dispatcher.send_stream_event_async(data, patch=False)
        # is this fast enough can we do at scale?
        await self.check_run_stop()

    @override
    async def on_run_step_done(self, run_step: RunStep) -> None:
        """
        Handle the completion of a run step.

        Args:
            run_step (RunStep): The completed run step.

        This function saves messages of type `tool call` and patches them to the frontend.
        - Saves both assistant tool call and tool output separately in the db.
        - This allows us to be compatible with both assistants and agents.
        - For assistants, we need to patch tool call with structure output as marvin only provides string output.
        """

        if not run_step.completed_at:
            run_step.completed_at = datetime.now().timestamp()
        self.steps.append(run_step)
        details = run_step.step_details

        # only save messages if there are tool calls
        # non tool call messages saved in on_message_done
        if hasattr(details, "tool_calls") and details.tool_calls:
            outputs = self.tool_outputs

            assistant_message = run_step_to_tool_call_message(
                run_step, self.context, tool_calls=outputs
            )
            # clear tool outputs
            pretty_log("clear tool outputs", len(self.tool_outputs))
            self.tool_outputs = []
            data = {"message": assistant_message}

            # pretty_log("run step done", data)
            await self.dispatcher.send_stream_event_async(data, patch=False)
            await self.memory.put_async(assistant_message, index=self.context.thread_id)

    async def on_tool_output(self, tool_output):
        """Callback that is fired when a tool output is encountered"""
        pass

    @override
    async def on_tool_call_created(self, tool_call) -> None:
        """Callback that is fired when a tool call delta is encountered"""
        pretty_log("tool call created", tool_call)

    @override
    async def on_tool_call_done(self, tool_call, raw_tool_result=None) -> None:
        """Callback that is fired when a tool call is done"""
        self.tool_calls.append(tool_call.model_dump())
        self._context["storage"]["tool_calls"] = self.tool_calls

    @override
    async def on_exception(self, exc):
        """
        Handle exceptions during the assistant run.

        Args:
            exc (Exception): The exception that occurred.

        This function logs the error, prints the traceback, and sends an error event.
        """
        logger.error(exc)
        traceback.print_exc()
        logger.info("sent error")
        self._context["storage"]["errors"].append(str(exc))
        await self.dispatcher.send_error_async(str(exc))

    @override
    async def on_event(self, event):
        """
        Handle various events during the assistant run.

        Args:
            event: The event that occurred.

        This function handles events such as ThreadRunRequiresAction, ThreadRunStepCompleted,
        ThreadRunCompleted, ThreadRunFailed, and ThreadRunCancelled, and dispatches corresponding events.
        """
        if isinstance(event, ThreadRunRequiresAction) and self.previous_event is None:
            self.previous_event = event
            logger.info("tool call event started")

        # step completed - maybe a good place to track actions
        if isinstance(event, ThreadRunStepCompleted):
            logger.info("step completed")
            self.processed_steps.append(event)

        # run completed events
        if isinstance(event, (ThreadRunCompleted,)):
            try:
                await self.dispatcher.send_close_async()
            except Exception as e:
                logger.error(f"Failed to send close {e}")

            run_credits = calculate_credits(event.data)

            metadata = {
                "credits": run_credits.model_dump(),
                "events": self.dispatcher.run_events(),
                "messages": self.messages,
            }
            event.data.metadata = metadata
            data = {
                "run": to_serializable(event.data),
                "steps": to_serializable(self.steps),
            }

            self._context["storage"]["run_metadata"] = data

            # pretty_log("run completed", data)
            await self.dispatcher.send_close_async()

        # run failed events, cancelled
        if isinstance(event, (ThreadRunFailed, ThreadRunCancelled)):
            try:
                await self.dispatcher.send_close_async()
            except Exception as e:
                logger.error(f"Failed to send close {e}")

            await self.dispatcher.send_error_async(event)
            await self.dispatcher.send_close_async()

    @override
    async def on_end(self):
        """Stream ended"""

    @override
    async def on_image_file_done(self, image_file: ImageFile) -> None:
        """Callback that is fired when an image file block is finished"""
        try:
            chat_message = await save_assistant_image_to_storage(
                context=self.context,
                image_file=image_file,
            )

            await self.dispatcher.send_stream_event_async(
                {"message": chat_message}, patch=False
            )

        except Exception as e:
            logger.error(f"AssistantHandler:Failed to save image file {e}")
            traceback.print_exc()

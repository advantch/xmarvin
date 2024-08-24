import time
import traceback
import uuid
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

import litellm
from litellm import ModelResponse, acompletion
from openai.types.beta.assistant_stream_event import (
    ThreadRunCancelled,
    ThreadRunCompleted,
    ThreadRunFailed,
    ThreadRunRequiresAction,
)
from openai.types.beta.threads.run import (
    AssistantTool,
    RequiredAction,
)
from openai.types.beta.threads.run import (
    Run as OpenAIRun,
)
from openai.types.beta.threads.runs.run_step import (
    RunStep,
    Usage,
)
from pydantic import BaseModel, Field

from marvin.beta.assistants.handlers import PrintHandler
from marvin.beta.local.assistant import LocalAssistant
from marvin.beta.local.thread import LocalThread
from marvin.extensions.event_handlers.default_assistant_event_handler import (
    DefaultAssistantEventHandler,
)
from marvin.extensions.storage.cache import cache
from marvin.extensions.tools.tool import Tool, handle_tool_call_async
from marvin.extensions.types.message import ChatMessage
from marvin.extensions.types.tools import AppFunction, AppToolCall
from marvin.extensions.utilities.mappers import (
    convert_delta_to_message_delta,
    convert_model_response_to_message,
    create_step_from_model_response,
    create_tool_calls_run_step_delta,
)
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method
from marvin.utilities.tools import output_to_string


class AppRun(OpenAIRun):
    tools: Optional[List[AssistantTool]] = None


class RunStatus(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EndRun(Exception):
    end_type: Literal["end_run", "cancel_run"] = "end_run"


# Utility functions
# Run Class
class LocalRun(BaseModel, ExposeSyncMethodsMixin):
    id: str | uuid.UUID = Field(default_factory=lambda: str(uuid.uuid4()))
    assistant_id: str | None = None
    thread_id: str | None = None
    status: RunStatus = RunStatus.STARTED
    steps: List[RunStep] = Field(default_factory=list)
    model: str | None = None
    instructions: str | None = None

    tools: Optional[List[Tool]] = Field(default_factory=list)
    llm_tools: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of tools to use for the run. These are the actual python objects to be called.",
    )
    tool_choice: str = "auto"

    file_ids: List[str] | None = Field(default_factory=list)
    assistant: LocalAssistant | None = None
    thread: LocalThread | None = None
    tool_outputs: List[Dict[str, Any]] = Field(default_factory=list)
    max_runs: int = 3
    current_run_count: int = 0
    stream: bool = True
    run: AppRun | None = None
    handler: DefaultAssistantEventHandler | None = None
    handler_kwargs: Dict[str, Any] = Field(default_factory=dict)

    metadata: Dict[str, Any] = Field(default_factory=dict)

    usage: Usage | None = Usage(completion_tokens=0, prompt_tokens=0, total_tokens=0)
    cache: Any = Field(
        default_factory=cache,
        description="Cache for the run. Replace with a redis based cached to allow for messaging.",
    )

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        _id = kwargs.get("id", None)
        _id = str(uuid.uuid4()) if _id is None else _id
        kwargs["id"] = _id
        super().__init__(**kwargs)
        self.llm_tools = (
            [t.to_openai_tool() for t in self.tools]
            if self.tools and len(self.tools) > 0
            else None
        )

    async def _check_complete(self):
        """
        Check if the run is complete by checking the cache:
        Raises EndRun if run is complete to trigger the end of the run
        """
        raise EndRun(end_type="stop_run")

    @expose_sync_method("execute")
    async def execute_async(self, message: ChatMessage | None = None):
        """
        @param message: ChatMessage | None - Message to add to the thread

        Return:
        - None

        Executes the run
         - create the run
         - add the message to the thread
         - run the loop until condition met [max_runs, is_complete]
            - if streaming send to handler
            - process the response
            - dispatch event
         - if max_runs reached or is_complete, update the run status and dispatch the appropriate event
         - finally save the run & stats.
         - raise exception if run is cancelled or failed.
        """
        tools = self.llm_tools if self.llm_tools and len(self.llm_tools) > 0 else None
        tool_dict = {"tools": tools} if tools else {}
        run_stop_cache_key = f"run:stop:{self.id}"

        self.handler = self.handler or PrintHandler()
        self.run = AppRun(
            id=str(self.id),
            assistant_id=self.assistant.id,
            model=self.model or self.assistant.model,
            instructions=self.instructions or self.assistant.instructions,
            status="in_progress",
            thread_id=self.thread.id,
            metadata=self.metadata,
            created_at=int(time.time()),
            object="thread.run",
            parallel_tool_calls=False,
            **tool_dict,
            tool_choice=self.tool_choice,
        )
        # if message is provided add it to the thread
        if message:
            await self.thread.add_message_async(message)
        is_complete = False

        # run the loop until condition met [max_runs, is_complete]
        try:
            while self.current_run_count < self.max_runs and not is_complete:
                self.current_run_count += 1
                response = await self._get_llm_response()
                # if streaming send to handler
                if self.stream:
                    chunks = []
                    async for chunk in response:
                        chunks.append(chunk)
                        _response = litellm.stream_chunk_builder(chunks)
                        await self._process_model_chunk(chunk, _response)
                    response = litellm.stream_chunk_builder(chunks)

                # finally, process the response
                run_step = create_step_from_model_response(
                    response, self.handler.context
                )
                self._current_step = run_step

                # process creation of tool calls or message
                await self._process_model_response(response)
                self._current_step.status = RunStatus.COMPLETED.value

                # dispatch event
                await self.handler.on_run_step_done(self._current_step)
                self.steps.append(self._current_step)
                # update usage
                self.usage.completion_tokens += response.usage.completion_tokens
                self.usage.prompt_tokens += response.usage.prompt_tokens
                self.usage.total_tokens += response.usage.total_tokens
                self._current_step = None

                if not hasattr(response.choices[0].message, "tool_calls"):
                    is_complete = True

            if self.current_run_count >= self.max_runs:
                self.status = RunStatus.CANCELLED
                event = ThreadRunCancelled(event="thread.run.cancelled", data=self.run)
                await self.handler.on_event(event)

            else:
                self.run.usage = self.usage
                event = ThreadRunCompleted(event="thread.run.completed", data=self.run)
                await self.handler.on_event(event)
                self.status = RunStatus.COMPLETED

        except EndRun:
            self.run.usage = self.usage
            self.run.status = RunStatus.COMPLETED.value
            self.status = RunStatus.COMPLETED
            event = ThreadRunCompleted(event="thread.run.completed", data=self.run)
            await self.handler.on_event(event)
            # clean up the cache if it exists

            if cache.get(run_stop_cache_key, None) is not None:
                cache.delete(run_stop_cache_key)

        except Exception as e:
            self.status = RunStatus.FAILED
            self.run.usage = self.usage
            self.run.status = RunStatus.FAILED.value
            traceback.print_exc()
            event = ThreadRunFailed(event="thread.run.failed", data=self.run)
            await self.handler.on_event(event)

            raise e
        finally:
            self.run.usage = self.usage
            self.run.status = RunStatus.COMPLETED.value
            event = ThreadRunCompleted(event="thread.run.completed", data=self.run)
            await self.handler.on_event(event)
            if cache.get(run_stop_cache_key, None) is not None:
                cache.delete(run_stop_cache_key)

    async def _get_llm_response(self):
        messages = await self.thread.get_messages_for_run_async()

        response = await acompletion(
            model="gpt-4o-mini",
            messages=messages,
            stream=self.stream,
            tools=self.llm_tools,
        )

        return response

    async def _process_model_response(self, response: ModelResponse):
        """
        @param response: ModelResponse

        Return:
        - None

        Process the model response and dispatch the appropriate event
        - tool calls dispatch run_step_delata event
        - message dispatch message_delta event
        - message_done dispatch message_done event
        """
        message = response.choices[0].message
        if hasattr(message, "tool_calls"):
            # set the current run to requires action
            self.run.required_action = RequiredAction(
                **{
                    "type": "submit_tool_outputs",
                    "submit_tool_outputs": {
                        "tool_calls": [t.model_dump() for t in message.tool_calls]
                    },
                }
            )
            event = ThreadRunRequiresAction(
                event="thread.run.requires_action", data=self.run
            )
            await self.handler.on_event(event)
            await self._handle_tool_calls(response)
        else:
            await self._handle_message(response)

    async def _dispatch_event(self, event, data):
        self.handler.on_event(event, data)

    async def _process_model_chunk(self, chunk, response):
        """
        Process a model chunk and dispatch the appropriate event
        - tool calls dispatch run_step_delata event
        - message dispatch message_delta event
        - message_done dispatch message_done event
        """
        try:
            # if tool calls
            if chunk.choices[0].delta.tool_calls:
                run_step = create_step_from_model_response(
                    response, self.handler.context
                )
                run_step_delta = create_tool_calls_run_step_delta(run_step)
                await self.handler.on_run_step_delta(run_step_delta, run_step)
            else:
                # convert to openai message delta & message as expected by handler
                snapshot = convert_delta_to_message_delta(chunk)
                message = convert_model_response_to_message(
                    response, self.assistant.id, self.thread.id
                )
                await self.handler.on_message_delta(snapshot, message)
        except Exception as e:
            traceback.print_exc()
            raise e

    async def _handle_message(self, response):
        """
        Handle message from the assistant
         - dispatch on message done event
        """
        message = convert_model_response_to_message(
            response, self.assistant.id, self.thread.id
        )
        await self.handler.on_message_done(message)

    async def _handle_tool_calls(self, model_response):
        """
        Handle tool calls from the assistant
         - run the tool
         - dispatch on tool call done event with tool_call and raw_tool_result
         - update the run step with the tool call
         - handler will update memory to make sure it is avaiable in the history for next call.
        """
        run_step = self._current_step

        tool_calls = []
        for choice in model_response.choices:
            tool_calls.extend(choice.message.tool_calls)
        for tool_call in tool_calls:
            if tool_call.function.name == "end_run":
                raise EndRun()

            tool_result = await handle_tool_call_async(tool_call, self.tools)
            output_string = (
                output_to_string(tool_result)
                if not hasattr(tool_result, "results_string")
                else tool_result.results_string
            )
            # modify the tool call to add the output and structured output
            # stream consumers can use this to construct UIs
            open_ai_tool_call = AppToolCall(
                id=tool_call.id,
                function=AppFunction(
                    name=tool_call.function.name,
                    arguments=tool_call.function.arguments,
                    output=output_string,
                    structured_output=tool_result,
                ),
                type="function",
            )

            await self.handler.on_tool_call_done(open_ai_tool_call)
            # update tool outputs in the run step.
            for idx, c in enumerate(run_step.step_details.tool_calls):
                if c.id == tool_call.id:
                    run_step.step_details.tool_calls[idx] = open_ai_tool_call

            self._current_step = run_step

        self._current_step = run_step

from typing import Any, Callable, Literal, Optional, Union

from openai import AsyncAssistantEventHandler
from openai.types.beta.threads import Message
from openai.types.beta.threads.run import Run as OpenAIRun
from openai.types.beta.threads.runs import RunStep as OpenAIRunStep
from pydantic import BaseModel, Field, PrivateAttr, field_validator

import marvin.utilities.openai
import marvin.utilities.tools
from marvin.extensions.types.tools import AppFunction, AppToolCall
from marvin.tools.assistants import ENDRUN_TOKEN, AssistantTool, EndRun
from marvin.types import Tool
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method
from marvin.utilities.logging import get_logger
from marvin.utilities.tools import output_to_string

from .assistants import Assistant
from .threads import Thread

logger = get_logger("Runs")


class Run(BaseModel, ExposeSyncMethodsMixin):
    """
    The Run class represents a single execution of an assistant.

    Attributes:
        thread (Thread): The thread in which the run is executed.
        assistant (Assistant): The assistant that is being run.
        model (str, optional): The model used by the assistant.
        instructions (str, optional): Replacement instructions for the run.
        additional_instructions (str, optional): Additional instructions to append
                                                 to the assistant's instructions.
        tools (list[Union[AssistantTool, Callable]], optional): Replacement tools
                                                               for the run.
        additional_tools (list[AssistantTool], optional): Additional tools to append
                                                          to the assistant's tools.
        tool_choice (Union[Literal["auto", "none", "required"], AssistantTool], optional):
                                                    The tool use behaviour for the run.
        run (OpenAIRun): The OpenAI run object.
        data (Any): Any additional data associated with the run.
        handler (AsyncAssistantEventHandler): The event handler for the run.
    """

    model_config: dict = dict(extra="forbid")

    thread: Thread
    assistant: Assistant
    event_handler_class: Optional[type[AsyncAssistantEventHandler]] = Field(
        default=None
    )
    event_handler_kwargs: dict[str, Any] = Field(default={})
    _messages: list[Message] = PrivateAttr({})
    _steps: list[OpenAIRunStep] = PrivateAttr({})
    model: Optional[str] = Field(
        None, description="Replace the model used by the assistant."
    )
    instructions: Optional[str] = Field(
        None, description="Replacement instructions to use for the run."
    )
    additional_instructions: Optional[str] = Field(
        None,
        description=(
            "Additional instructions to append to the assistant's instructions."
        ),
    )
    tools: Optional[list[Union[AssistantTool, Callable]]] = Field(
        None, description="Replacement tools to use for the run."
    )
    additional_tools: Optional[list[AssistantTool]] = Field(
        None,
        description="Additional tools to append to the assistant's tools. ",
    )
    tool_choice: Optional[Union[Literal["none", "auto", "required"], AssistantTool]] = (
        Field(
            default=None,
            description="The tool use behaviour for the run. Can be 'none', 'auto', 'required', or a specific tool.",
        )
    )
    run: OpenAIRun = Field(None, repr=False)
    data: Any = None
    handler: Any = None
    _tool_outputs: list[str] = PrivateAttr([])

    def __init__(self, *, messages: list[Message] = None, **data):
        super().__init__(**data)
        if messages is not None:
            self._messages.update({m.id: m for m in messages})

    @field_validator("tools", "additional_tools", mode="before")
    def format_tools(cls, tools: Union[None, list[Union[Tool, Callable]]]):
        if tools is not None:
            return [
                (
                    tool
                    if isinstance(tool, Tool)
                    else marvin.utilities.tools.tool_from_function(tool)
                )
                for tool in tools
            ]

    @property
    def messages(self) -> list[Message]:
        return sorted(self._messages.values(), key=lambda m: m.created_at)

    @property
    def steps(self) -> list[OpenAIRunStep]:
        return sorted(self._steps.values(), key=lambda s: s.created_at)

    @expose_sync_method("refresh")
    async def refresh_async(self):
        """Refreshes the run."""
        if not self.run:
            raise ValueError("Run has not been created yet.")
        client = marvin.utilities.openai.get_openai_client()
        self.run = await client.beta.threads.runs.retrieve(
            run_id=self.run.id, thread_id=self.thread.id
        )

    @expose_sync_method("cancel")
    async def cancel_async(self):
        """Cancels the run."""
        if not self.run:
            raise ValueError("Run has not been created yet.")
        client = marvin.utilities.openai.get_openai_client()
        await client.beta.threads.runs.cancel(
            run_id=self.run.id, thread_id=self.thread.id
        )
        await self.refresh_async()

    def _get_instructions(self, thread: Thread = None) -> Optional[str]:
        if self.instructions is None:
            instructions = self.assistant.get_instructions(thread=thread) or ""
        else:
            instructions = self.instructions

        if self.additional_instructions is not None:
            instructions = "\n\n".join([instructions, self.additional_instructions])

        return instructions or None

    def _get_model(self) -> str:
        if self.model is None:
            model = self.assistant.model
        else:
            model = self.model
        return model

    def _get_tools(self) -> list[AssistantTool]:
        tools = []
        if self.tools is None:
            tools.extend(self.assistant.get_tools())
        else:
            tools.extend(self.tools)
        if self.additional_tools is not None:
            tools.extend(self.additional_tools)
        return tools

    def _get_run_kwargs(self, thread: Thread = None, **run_kwargs) -> dict:
        if instructions := self._get_instructions(thread=thread):
            run_kwargs["instructions"] = instructions

        if tools := self._get_tools():
            run_kwargs["tools"] = [t.model_dump(mode="json") for t in tools]

        if model := self._get_model():
            run_kwargs["model"] = model

        if tool_choice := self.tool_choice:
            run_kwargs["tool_choice"] = (
                tool_choice.model_dump(mode="json")
                if isinstance(tool_choice, Tool)
                else tool_choice
            )

        return run_kwargs

    async def get_tool_outputs(self, run: OpenAIRun) -> list[str]:
        if run.status != "requires_action":
            return None, None
        if run.required_action.type == "submit_tool_outputs":
            tool_calls = []
            tool_outputs = []
            tools = self._get_tools()

            for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                try:
                    output = marvin.utilities.tools.call_function_tool(
                        tools=tools,
                        function_name=tool_call.function.name,
                        function_arguments_json=tool_call.function.arguments,
                    )

                    # cache the output for the handler to patch later.
                    # this will be consumed by the handler when on_run_step_done is called after tool processing is complete.
                    # only necessary for assistants api
                    output_string = (
                        output_to_string(output)
                        if not hasattr(output, "results_string")
                        else output.results_string
                    )
                    print(output_string)
                    if tool_call.type == "function":
                        func = AppToolCall(
                            id=tool_call.id,
                            function=AppFunction(
                                name=tool_call.function.name,
                                arguments=tool_call.function.arguments,
                                output=output_string,
                                structured_output=output,
                            ),
                            type="function",
                        )
                        self._tool_outputs.append(func)
                    # functions can raise EndRun, return an EndRun, or return the endrun token
                    # to end the run
                    if isinstance(output, EndRun):
                        raise output
                    elif output == ENDRUN_TOKEN:
                        raise EndRun()

                except EndRun as exc:
                    logger.debug(f"Ending run with data: {exc.data}")
                    raise
                except Exception as exc:
                    output = f"Error calling tool {tool_call.function.name}: {exc}"
                    logger.error(output)
                string_output = marvin.utilities.tools.output_to_string(output)
                tool_outputs.append(
                    dict(
                        tool_call_id=tool_call.id,
                        output=string_output,
                    )
                )
                tool_calls.append(tool_call)

            return tool_outputs

    async def update_handler_kwargs(self, handler: AsyncAssistantEventHandler):
        from marvin.beta.local.handlers import DefaultAssistantEventHandler

        if isinstance(handler, DefaultAssistantEventHandler):
            handler.tool_outputs = self._tool_outputs

    async def run_async(self) -> "Run":
        if self.run is not None:
            raise ValueError(
                "This run object was provided an ID; can not create a new run."
            )
        if not self.thread.id:
            await self.thread.create_async()
        client = marvin.utilities.openai.get_openai_client()
        run_kwargs = self._get_run_kwargs(thread=self.thread)

        event_handler_class = self.event_handler_class or AsyncAssistantEventHandler

        with self.assistant:
            handler = event_handler_class(**self.event_handler_kwargs)
            # custom tool patching for default event handler
            if hasattr(handler, "tool_outputs"):
                handler.tool_outputs = self._tool_outputs
            self.handler = handler

            try:
                self.assistant.pre_run_hook()

                for msg in self.messages:
                    await handler.on_message_done(msg)

                async with client.beta.threads.runs.stream(
                    thread_id=self.thread.id,
                    assistant_id=self.assistant.id,
                    event_handler=handler,
                    **run_kwargs,
                ) as stream:
                    await stream.until_done()
                    await self._update_run_from_handler(handler)

                while handler.current_run.status in ["requires_action"]:
                    tool_outputs = await self.get_tool_outputs(run=handler.current_run)

                    # Update the handler with cached tool outputs
                    # we do this so we can patch the tool outputs coming from the assistant with our own
                    # A new handler instance is created each time, so we update its context here

                    # Update the context with the latest tool outputs
                    old_context_dict = handler._context
                    _tool_outputs = self.handler.tool_outputs

                    # new handler instance
                    handler = event_handler_class(**self.event_handler_kwargs)

                    # Create a new handler instance with the updated context
                    if hasattr(self.event_handler_class, "_context"):
                        handler._context = old_context_dict
                        handler.tool_outputs = _tool_outputs

                    # upstream client to submit and handle tool outputs
                    async with client.beta.threads.runs.submit_tool_outputs_stream(
                        thread_id=self.thread.id,
                        run_id=self.run.id,
                        tool_outputs=tool_outputs,
                        event_handler=handler,
                    ) as stream:
                        await stream.until_done()
                        await self._update_run_from_handler(handler)

            except EndRun as exc:
                logger.debug(f"`EndRun` raised; ending run with data: {exc.data}")
                await self.cancel_async()
                self.data = exc.data

            except KeyboardInterrupt:
                logger.debug("Keyboard interrupt; ending run.")
                await self.cancel_async()
                raise

            except Exception as exc:
                await handler.on_exception(exc)
                raise

            if self.run.status == "failed":
                logger.debug(
                    f"Run failed. Last error was: {handler.current_run.last_error}"
                )

            self.assistant.post_run_hook(run=self)

        return self

    async def _update_run_from_handler(self, handler: AsyncAssistantEventHandler):
        self.run = handler.current_run
        try:
            messages = await handler.get_final_messages()
            self._messages.update({m.id: m for m in messages})
        except RuntimeError:
            pass

        try:
            steps = await handler.get_final_run_steps()
            self._steps.update({s.id: s for s in steps})
        except RuntimeError:
            pass

import uuid
from datetime import datetime
from typing import List, Optional, Union

import orjson
from litellm import ModelResponse
from litellm.types.utils import Delta
from openai.types.beta.threads import Message, MessageDelta
from openai.types.beta.threads.message_content import (
    ImageFileContentBlock,
    TextContentBlock,
)
from openai.types.beta.threads.runs.message_creation_step_details import MessageCreation
from openai.types.beta.threads.runs.run_step import (
    MessageCreationStepDetails,
    RunStep,
    ToolCallsStepDetails,
    Usage,
)
from openai.types.beta.threads.runs.run_step_delta import (
    RunStepDelta,
    ToolCallDeltaObject,
)
from openai.types.beta.threads.runs.tool_call_delta import FunctionToolCallDelta
from openai.types.beta.threads.text_delta import TextDelta
from openai.types.beta.threads.text_delta_block import TextDeltaBlock

from marvin.extensions.types import (
    AnyToolCall,
    AppToolCall,
    ChatMessage,
    Function,
    FunctionToolCall,
)
from marvin.extensions.utilities.context import RunContext
from marvin.extensions.utilities.unique_id import generate_uuid_from_string


def map_content_to_block(content, is_delta=False):
    """
    Map content, usually from a model response
    To a list of UI compatible message blocks.

    Message blocks can be TextContentBlock or ImageFileContentBlock

    """
    text_cls = TextContentBlock if not is_delta else TextDeltaBlock
    all_blocks = []
    if isinstance(content, str):
        c = text_cls.model_validate(content)
        all_blocks.append(c)
    elif isinstance(content, list):
        for block in content:
            if block.type == "text":
                all_blocks.append(text_cls.model_validate(block))
            if block.type == "image":
                all_blocks.append(ImageFileContentBlock.model_validate(block))
    return all_blocks


def map_model_response_to_message(
    message: ModelResponse, assistant_id, thread_id, run_id=None
):
    """
    Map a model response to the app message format
    """
    return Message(
        id=message.id,
        assistant_id=assistant_id,
        attachments=None,
        content=map_content_to_block(message.content),
        created_at=message.created_at,
        role="assistant",
        run_id=run_id,
        thread_id=thread_id,
    )


def map_tool_call_to_dict(tool_call):
    fields = tool_call.model_fields
    value = {}
    for k, v in fields.items():
        value[k] = v.value
    return value


def message_type_from_tool_call_step_details(details) -> str:
    """
    Determine tool call type from the run step details.
    function, code_interpreter, file_search
    """
    message_type = "function"
    tool_calls = getattr(details, "tool_calls", [])
    if len(tool_calls) > 0:
        message_type = tool_calls[0].type
    return message_type


def construct_tool_call_from_remote_call(tool_call):
    """
    Construct a tool call from the step details
    """
    if tool_call.type == "function":
        return AppToolCall(**orjson.loads(tool_call.model_dump_json()))
    else:
        return tool_call


def patch_step_tool_calls(step: RunStep, tool_calls: List[AnyToolCall]):
    """
    Patch the tool calls in a step details
    """
    if not hasattr(step, "step_details"):
        return []
    step_tool_calls = []

    if step.step_details.tool_calls:
        if tool_calls:
            for tool_call in step.step_details.tool_calls:
                if tool_call.id in [tool_calls.id for tool_calls in tool_calls]:
                    replacement_call = next(
                        (tc for tc in tool_calls if str(tc.id) == str(tool_call.id)),
                        None,
                    )
                    tool_call = replacement_call
                step_tool_calls.append(tool_call)
            return step_tool_calls
        else:
            return [
                construct_tool_call_from_remote_call(tool_call)
                for tool_call in step.step_details.tool_calls
            ]
    return []


def run_step_to_tool_call_message(
    run_step: RunStep,
    context: RunContext,
    is_delta: bool = False,
    tool_calls: List[AnyToolCall] = None,
) -> ChatMessage:
    """
    Convert a run step to a tool call message
    """
    details = run_step.step_details
    # if tool_calls are provided then replace with those
    patched_tool_calls = patch_step_tool_calls(run_step, tool_calls)
    message_type = message_type_from_tool_call_step_details(details)
    # we should save tool calls
    m = ChatMessage(
        id=generate_uuid_from_string(run_step.id),
        role="assistant",
        content=[],
        run_id=context.run_id,
        thread_id=context.thread_id,
        metadata={
            "type": message_type,
            "tool_calls": patched_tool_calls,
            "run_step_id": run_step.id,
            "streaming": is_delta,  # if the message is a delta, it's a stream
            "message_type": message_type,
        },
    )
    return m


def create_step_from_model_response(response: ModelResponse, context):
    step_details: Union[MessageCreationStepDetails, ToolCallsStepDetails] = None

    if (
        hasattr(response.choices[0].message, "tool_calls")
        and response.choices[0].message.tool_calls
    ):
        # Create ToolCallsStepDetails
        step_details = ToolCallsStepDetails(
            tool_calls=[
                FunctionToolCall(
                    id=tool_call.id,
                    function=Function(
                        name=tool_call.function.name,
                        arguments=tool_call.function.arguments,
                    ),
                    type="function",
                )
                for tool_call in response.choices[0].message.tool_calls
            ],
            type="tool_calls",
        )
    # see if we need this?
    else:
        # Create MessageCreationStepDetails
        message_id = str(response.id)
        step_details = MessageCreationStepDetails(
            message_creation=MessageCreation(message_id=message_id),
            type="message_creation",
        )

    if response and response.usage:
        Usage(**response.usage.model_dump())
    agent_id = str(uuid.uuid4())
    if context.agent_config:
        agent_id = str(context.agent_config.id) or str(uuid.uuid4())
    return RunStep(
        id=f"{response.id}",
        object="thread.run.step",
        created_at=int(datetime.now().timestamp()),
        run_id=str(context.run_id),
        assistant_id=agent_id,
        thread_id=str(context.thread_id),
        type=step_details.type,
        status="in_progress",
        cancelled_at=None,
        completed_at=None,
        expired_at=None,
        failed_at=None,
        last_error=None,
        step_details=step_details,
        metadata={"message_id": generate_uuid_from_string(str(response.id))},
        usage=Usage(**response.usage.model_dump()),
    )


def create_tool_calls_run_step_delta(run_step: RunStep):
    """
    Create a run step delta from a model response
    """
    return RunStepDelta(
        step_details=ToolCallDeltaObject(
            type="tool_calls",
            tool_calls=[
                FunctionToolCallDelta(**tool_call.model_dump(), index=idx)
                for idx, tool_call in enumerate(run_step.step_details.tool_calls)
            ],
        )
    )


def convert_model_response_to_message(
    response: ModelResponse,
    assistant_id: Optional[str] = None,
    thread_id: Optional[str] = None,
) -> Message:
    content = []
    if response.choices:
        for message in response.choices:
            if message.message.content:
                content = [
                    TextContentBlock(
                        type="text",
                        text={"value": message.message.content, "annotations": []},
                    )
                ]

    return Message(
        id=response.id,
        assistant_id=assistant_id,
        content=content,
        created_at=int(response.created),
        role="assistant",
        thread_id=thread_id,
        status="completed",
        object="thread.message",
    )


def convert_delta_to_message_delta(delta: Delta) -> MessageDelta:
    """
    Can be one of TextDelta or ImageDelta or ToolCallsDelta
    """
    text_delta_block = None
    if delta.choices and delta.choices[0].delta.content:
        text_delta = TextDelta(value=delta.choices[0].delta.content)
        text_delta_block = TextDeltaBlock(index=0, type="text", text=text_delta)
    return MessageDelta(
        content=[text_delta_block] if text_delta_block else None, role="assistant"
    )

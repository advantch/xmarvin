import logging
from typing import Any, Dict, List, Optional, Sequence, Type

from openai.types.beta.threads import MessageContent, TextContentBlock
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCall,
)
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from pydantic import BaseModel

from marvin.extensions.context.run_context import get_current_run
from marvin.extensions.types.message import (
    ChatMessage,
    FileMessageContent,
    ImageMessageContent,
)
from marvin.types import ImageFileContentBlock

DEFAULT_OPENAI_API_TYPE = "open_ai"
DEFAULT_OPENAI_API_BASE = "https://api.openai.com/v1"
DEFAULT_OPENAI_API_VERSION = ""


logger = logging.getLogger(__name__)


def to_openai_message_dict(
    message: ChatMessage, drop_none: bool = True, model: Optional[str] = None
) -> ChatCompletionMessageParam:
    """
    Convert app message to OpenAI message dict.
    - text -> converted to text
    - images -> convert to base64 when uploaded or generated by the LLM
    - files -> not added to message(yet) but prompt should include vector_search tool
    - tool_calls -> convert to tool calls
    """
    content = message.content if message.content else []
    if isinstance(content, list):
        c = []
        for item in content:
            if isinstance(item, TextContentBlock):
                c.append({"text": item.text.value, "type": "text"})
        content = c

    # images are added as image url content
    if message.metadata.attachments:
        for item in message.metadata.attachments:
            media_item = as_llm_message(item.file_id)
            if media_item:
                content.append(media_item)

    message_dict = {
        "role": message.role.value,
        "content": content,
    }

    # if message is assistant/llm tool call then add tool calls
    metadata = message.metadata
    if (
        metadata.tool_calls
        and len(metadata.tool_calls) > 0
        and message.role == "assistant"
    ):
        # ChatCompletionToolMessageParam
        message_dict["tool_calls"] = [t.model_dump() for t in metadata.tool_calls]

    null_keys = [key for key, value in message_dict.items() if value is None]
    if drop_none:
        for key in null_keys:
            message_dict.pop(key)
    # anthropic assistant messages must only contain 'text'?
    if model and "claude-" in model:
        # TODO check if sufficient, messages endpoint not yet supported
        # fixme https://github.com/BerriAI/litellm/blob/main/litellm/llms/prompt_templates/factory.py#L1166
        message_dict["content"] = message_dict["content"][0]["text"]

    return message_dict  # type: ignore


def split_tool_call_results_to_messages(message: dict) -> List[dict]:
    """
    Split tool calls to messages.
    Does not include the tool call message. only the results.
    """
    messages = []
    for tool_call in message.get("tool_calls", []):
        # create one assistant message
        tool_call.get("function", {}).get("output", {})
        messages.append(
            {
                "role": "tool",
                "content": tool_call.get("function", {}).get("output", {}),
                "tool_call_id": tool_call.get("id", ""),
            }
        )
    return messages


def format_message_for_completion_endpoint(
    messages: Sequence[ChatMessage],
    drop_none: bool = False,
    model: Optional[str] = None,
) -> List[ChatCompletionMessageParam]:
    """
    Convert chat message to completions endpoint messages.
    """

    history = []
    for idx, message in enumerate(messages):
        formatted = to_openai_message_dict(message, drop_none=drop_none, model=model)
        history.append(formatted)
        if message.metadata.tool_calls and message.role == "assistant":
            tool_call_results = split_tool_call_results_to_messages(formatted)
            history.extend(tool_call_results)
        else:
            history.append(formatted)
    return history


def from_openai_message(openai_message: ChatCompletionMessage) -> ChatMessage:
    """Convert openai message dict to generic message."""
    role = openai_message.role
    # NOTE: Azure OpenAI returns function calling messages without a content key
    content = openai_message.content

    metadata: Dict[str, Any] = {}
    if openai_message.tool_calls is not None:
        tool_calls: List[ChatCompletionMessageToolCall] = openai_message.tool_calls
        metadata.update(tool_calls=tool_calls)

    return ChatMessage(role=role, content=content, metadata=metadata)


def from_openai_messages(
    openai_messages: Sequence[ChatCompletionMessage],
) -> List[ChatMessage]:
    """Convert openai message dicts to generic messages."""
    return [from_openai_message(message) for message in openai_messages]


def from_openai_message_dict(message_dict: dict) -> ChatMessage:
    """Convert openai message dict to generic message."""
    role = message_dict["role"]
    # NOTE: Azure OpenAI returns function calling messages without a content key
    content = message_dict.get("content", None)

    metadata = message_dict.copy()
    metadata.pop("role")
    metadata.pop("content", None)

    return ChatMessage(role=role, content=content, metadata=metadata)


def from_openai_message_dicts(message_dicts: Sequence[dict]) -> List[ChatMessage]:
    """Convert openai message dicts to generic messages."""
    return [from_openai_message_dict(message_dict) for message_dict in message_dicts]


def to_openai_tool(
    pydantic_class: Type[BaseModel], description: Optional[str] = None
) -> Dict[str, Any]:
    """Convert pydantic class to OpenAI tool."""
    schema = pydantic_class.model_json_schema()
    schema_description = schema.get("description", None) or description
    return {
        "type": "function",
        "function": {
            "name": schema["title"],
            "description": schema_description,
            "parameters": schema,
        },
    }


def as_llm_message(file_id: str):
    ctx = get_current_run()
    storage = ctx.stores.data_source_store
    data_source = storage.get(file_id)
    if data_source:
        return ImageFileContentBlock(
            **{
                "type": "image_url",
                "image_url": {
                    "url": data_source.url,
                },
            }
        )
    return None


def get_openai_assistant_attachments(message: ChatMessage) -> List[MessageContent]:
    from marvin.extensions.settings import extension_settings  # noqa

    ctx = get_current_run()
    storage = ctx.stores.data_source_store

    attachments: List[MessageContent] = []
    if not message.metadata or not message.metadata.attachments:
        return attachments

    for attachment in message.metadata.attachments:
        if isinstance(attachment, FileMessageContent):
            file_content = storage.get_file_content_by_file_id(attachment.file_id)
            if file_content:
                attachments.append(
                    {
                        "type": "file",
                        "file_id": attachment.file_id,
                        "content": file_content,
                    }
                )
    return attachments


def get_openai_assistant_messages(message: ChatMessage) -> List[MessageContent]:
    content: List[MessageContent] = []
    ctx = get_current_run()
    storage = ctx.stores.data_source_store
    if isinstance(message.content, list):
        for text_message in message.content:
            if isinstance(text_message, TextContentBlock):
                content.append({"type": "text", "text": text_message.text.value})

    if message.metadata and message.metadata.attachments:
        for attachment in message.metadata.attachments:
            if isinstance(attachment, ImageMessageContent):
                image_content = storage.get(attachment.file_id)
                if image_content:
                    content.append(
                        {
                            "type": "image_file",
                            "image_file": {
                                "file_id": attachment.file_id,
                            },
                        }
                    )

    return content

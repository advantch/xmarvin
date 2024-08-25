import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional, Union
from uuid import UUID

import humps
from marvin.extensions.utilities.logging import logger
from marvin.extensions.types.base import BaseModelConfig
from marvin.extensions.types.data_source import DataSource
from marvin.extensions.types.tools import (
    AppCodeInterpreterTool,
    AppFileSearchTool,
    AppToolCall,
)
from openai.types.beta.threads.message_content import (
    ImageFileContentBlock,
    TextContentBlock,
)
from openai.types.beta.threads.message_content_delta import (
    ImageFileDeltaBlock,
    ImageURLDeltaBlock,
    TextDeltaBlock,
)
from openai.types.beta.threads.runs.function_tool_call import (
    Function as OpenAIFunction,
)
from openai.types.beta.threads.runs.function_tool_call import (
    FunctionToolCall as OpenAIFunctionToolCall,
)
from pydantic import BaseModel, Field


class Function(OpenAIFunction):
    pass


class FunctionToolCall(OpenAIFunctionToolCall):
    raw_output: dict | None = None


class MessageRole(str, Enum):
    """Message role."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"
    TOOL = "tool"
    CHATBOT = "chatbot"


class FileMessageContent(BaseModel):
    """
    Extends File message type for our use case
    """

    type: Literal["file"]
    file_id: Optional[str] = None
    metadata: Optional[DataSource] = None

    class Config(BaseModelConfig):
        pass



class ImageMessageContent(BaseModel):
    """
    Extends Image message type for our use case
    """

    type: Literal["image"]
    file_id: Optional[str] = None
    metadata: Optional[DataSource] = None

    class Config(BaseModelConfig):
        pass


AttachmentItem = Union[ImageMessageContent, FileMessageContent]


class Metadata(BaseModel):
    """
    Store metadata for a message.
    Attachments are used to store images and files instead of directly in the message content.
    Allows us to easily construct messages in UI
    """

    streaming: bool = False
    run_id: str | UUID | None = None
    id: str | UUID | None = None
    tool_calls: list[
        Union[AppToolCall, AppCodeInterpreterTool, AppFileSearchTool]
    ] | None | Any = None
    raw_tool_output: Any | None = None
    name: str | None = None
    type: str | None = "message"
    attachments: list[AttachmentItem] | None = None
    created: datetime = Field(default_factory=datetime.now)

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"
        alias_generator = humps.camelize
        populate_by_name = True


MessageContentType = Union[
    ImageMessageContent,  # attachment
    FileMessageContent,  # attachment
    TextContentBlock,  # openai
    ImageFileDeltaBlock,  # openai delta
    ImageFileContentBlock,  # openai
    TextDeltaBlock,  # openai delta
    ImageURLDeltaBlock,  # openai delta
]


class ChatMessage(BaseModel):
    """
    Chat message for the app

    Rich container for handling all message types.
        user - user message
        assistant(agent) - assistant message including (tool calls)
        function - function message
        tool - tool message

    Images & File types
        - handled as attachments in metadata
    """

    role: MessageRole = MessageRole.USER
    content: str | list[MessageContentType] | None = None
    id: str | UUID = Field(default_factory=uuid.uuid4)
    run_id: str | UUID | None = None
    thread_id: str | UUID | None = None
    metadata: Metadata = Metadata()

    class Config(BaseModelConfig):
        pass

    def __str__(self) -> str:
        return f"{self.role.value}: {self.content}"

    def requires_search(self) -> bool:
        check_requires_search = False
        if self.metadata.attachments:
            for attachment in self.metadata.attachments:
                if attachment.type == "file":
                    check_requires_search = True
                    break
        return check_requires_search

    def get_text_content(self):
        if isinstance(self.content, TextContentBlock):
            return self.content.text.value
        if isinstance(self.content, str):
            return self.content
        return ""

    def as_llm_message(self):
        """As litellm message"""
        from marvin.extensions.utilities.message_parsing import to_openai_message_dict
        return to_openai_message_dict(self)

    def append_content(self, text: str):
        if isinstance(self.content, TextContentBlock):
            self.content.text = self.content.text + "\n\n" + text
        elif isinstance(self.content, list):
            if not isinstance(self.content[0], TextContentBlock):
                logger.info("Can only update text content for TextContentBlock")
                return
            self.content[0].text.value = self.content[0].text.value + "\n\n" + text

    # def get_openai_assistant_attachments(self) -> list[MessageContent]:
    #     attachments: list[MessageContent] = []
    #     # only relevant for files
    #     for attachment in self.metadata.attachments:
    #         if isinstance(attachment, FileMessageContent):
    #             # sync to openai and return reference
    #             message = attachment.as_openai_llm_message()
    #             if message:
    #                 attachments.append(message)
    #     return attachments

    # def get_openai_assistant_messages(self) -> list[MessageContent]:
    #     # image messages should be included
    #     content: list[MessageContent] = []

    #     for text_message in self.content:
    #         if isinstance(text_message, TextContentBlock):
    #             # api only accepts TextContentBlockParam - i.e. text should be string
    #             content.append(
    #                 {"text": text_message.text.value, "type": text_message.type}
    #             )

    #     for attachment in self.metadata.attachments:
    #         if isinstance(attachment, ImageMessageContent):
    #             message = attachment.as_openai_llm_message()
    #             if message:
    #                 content.append(message)
    #     return content

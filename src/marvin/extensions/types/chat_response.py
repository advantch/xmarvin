import uuid
from typing import Any, Optional

from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import BaseModel, Field


class CompletionResponse(BaseModel):
    """
    Completion response.

    Fields:
        text: Text content of the response if not streaming, or if streaming,
            the current extent of streamed text.
        metadata: Additional information on the response(i.e. token
            counts, function calling information).
        raw: Optional raw JSON that was parsed to populate text, if relevant.
        delta: New text that just streamed in (only relevant when streaming).
    """

    text: str
    metadata: dict = Field(default_factory=dict)
    raw: Optional[dict] = None
    delta: Optional[str] = None

    def __str__(self) -> str:
        return self.text


class ChatResponse(BaseModel):
    """Chat response."""

    message: ChatCompletion | ChatCompletionChunk | Any
    raw: Optional[dict] = None
    delta: Optional[str] = None
    metadata: dict | None = Field(default_factory=dict)
    is_function: bool = False
    message_id: str | uuid.UUID | None = None

    def __str__(self) -> str:
        return str(self.message)

    class Config:
        allow_extra = True
        arbitrary_types_allowed = True
        extra = "allow"

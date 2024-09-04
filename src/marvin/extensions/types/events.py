from datetime import datetime
from typing import Any, Dict
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from marvin.extensions.types.base import BaseModelConfig
from marvin.extensions.types.message import ChatMessage


class BaseEvent(BaseModel):
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(), alias="timestamp"
    )
    id_: str = Field(default_factory=lambda: str(uuid4()), description="Event ID")
    span_id: str = Field(default_factory=str, description="Span ID")
    merge_id: str = Field(default_factory=lambda: str(uuid4()), description="Merge ID")
    parent_id: str | None = Field(None, description="Parent Event ID")

    class Config:
        arbitrary_types_allowed = True
        defer_build = False

    @classmethod
    def class_name(cls):
        """Return class name."""
        return "BaseEvent"

    def dict(self, **kwargs: Any) -> Dict[str, Any]:
        data = super().model_dump(**kwargs)
        data["class_name"] = self.class_name()
        return data


class StreamChatMessageEvent(BaseEvent):
    """
    Streaming chat message event.
    This is only data structure used for communication with outside systems.
    - UI
    - Sandboxes
    - Remote Agents
    """

    message: ChatMessage | None = Field(default=None, description="Chat message")
    message_type: str | None = Field(default=None, description="Message type")
    run_id: str | UUID | None = Field(default=None, description="Run ID")
    id: str | None = Field(default=None, description="Event ID")
    event: str | None = Field(default=None, description="Event")
    streaming: bool | None = Field(default=None, description="Streaming")
    type: str | None = Field(default=None, description="Type")

    class Config(BaseModelConfig):
        pass

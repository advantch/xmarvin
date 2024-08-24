from uuid import UUID

from apps.ai.agent.monitoring.events import BaseEvent
from apps.common.schema import BaseSchemaConfig
from marvin.extensions.types.message import ChatMessage


class StreamChatMessageEvent(BaseEvent):
    """
    Streaming chat message event.
    Only data structure used for communication with outside systems.
    - UI
    - Code Interpreter ETC
    """

    message: ChatMessage | None = None
    message_type: str | None = None
    run_id: str | UUID | None = None
    id: str | None = None
    event: str | None = None
    streaming: bool | None = None
    type: str | None = None

    class Config(BaseSchemaConfig):
        pass

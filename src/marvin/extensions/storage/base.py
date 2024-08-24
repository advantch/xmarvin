"""Base interface class for storing chat history per user."""

from abc import abstractmethod
from typing import Any, List, Optional

from pydantic import BaseModel

from marvin.extensions.types import ChatMessage
from marvin.utilities.asyncio import ExposeSyncMethodsMixin


class BaseChatStore(BaseModel, ExposeSyncMethodsMixin):
    class Config:
        allow_extra = True
        arbitrary_types_allowed = True
        extra = "allow"

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "BaseChatStore"

    @abstractmethod
    async def set_messages_async(
        self, key: str, messages: List[ChatMessage], **kwargs
    ) -> None:
        """Set messages for a key."""
        ...

    @abstractmethod
    async def get_messages_async(self, key: str, **kwargs) -> List[ChatMessage]:
        """Get messages for a key."""
        ...

    @abstractmethod
    async def add_message_async(self, key: str, message: ChatMessage, **kwargs) -> None:
        """Add a message for a key."""
        ...

    @abstractmethod
    async def delete_messages_async(
        self, key: str, **kwargs
    ) -> Optional[List[ChatMessage]]:
        """Delete messages for a key."""
        ...

    @abstractmethod
    async def delete_message_async(self, key: str, idx: int) -> Optional[ChatMessage]:
        """Delete specific message for a key."""
        ...

    @abstractmethod
    async def delete_last_message_async(self, key: str) -> Optional[ChatMessage]:
        """Delete last message for a key."""
        ...

    @abstractmethod
    async def get_keys_async(self) -> List[str]:
        """Get all keys."""
        ...

    async def add_files_async(self, key: str, files: List[Any]) -> List[Any]:
        """Add files for a key."""
        raise NotImplementedError("add_files_async is not implemented")


class BaseThreadStore(BaseModel, ExposeSyncMethodsMixin):
    @abstractmethod
    async def get_or_add_thread_async(
        self, thread_id: str, tenant_id: str
    ) -> "BaseThreadStore":
        """Get or create a thread."""
        ...

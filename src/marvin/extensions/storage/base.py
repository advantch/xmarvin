"""Base interface class for storing chat history per user."""

from abc import abstractmethod
from io import BytesIO
from typing import Any, List, Optional
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional, Union
from uuid import UUID

from marvin.extensions.types import ChatMessage
from marvin.utilities.asyncio import ExposeSyncMethodsMixin
from pydantic import BaseModel


class BaseChatStore(ABC, ExposeSyncMethodsMixin):
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


class BaseThreadStore(ABC, ExposeSyncMethodsMixin):
    @abstractmethod
    async def get_or_add_thread_async(
        self, thread_id: str, tenant_id: str
    ) -> "BaseThreadStore":
        """Get or create a thread."""
        ...


class BaseFileStorage(ABC, ExposeSyncMethodsMixin):
    @abstractmethod
    async def save_file(self, file: BinaryIO, file_id: Union[str, UUID], metadata: Optional[dict] = None) -> dict:
        """Save a file to storage and return its metadata."""
        pass

    @abstractmethod
    async def get_file(self, file_id: Union[str, UUID]) -> BinaryIO:
        """Retrieve a file from storage."""
        pass

    @abstractmethod
    async def delete_file(self, file_id: Union[str, UUID]) -> None:
        """Delete a file from storage."""
        pass

    @abstractmethod
    async def get_file_metadata(self, file_id: Union[str, UUID]) -> dict:
        """Retrieve metadata for a file."""
        pass


class BaseRunStorage(ABC, ExposeSyncMethodsMixin):
    @abstractmethod
    async def create(self, **kwargs) -> "BaseRunStorage":
        """Create a run."""
        ...

    
    @abstractmethod
    async def update(self, **kwargs) -> "BaseRunStorage":
        """Update a run."""
        ...

class BaseAgentStorage(ABC, ExposeSyncMethodsMixin):
    @abstractmethod
    async def get_agent_config(self, agent_id: str) -> "BaseAgentStorage":
        """Get agent config."""
        ...
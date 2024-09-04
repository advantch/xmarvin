"""Base interface classes for interacting with local storage objects."""

from abc import ABC, abstractmethod
from typing import Any, BinaryIO, List, Optional, TypeVar, Generic, Dict
from marvin.extensions.types.data_source import DataSource
from marvin.utilities.asyncio import expose_sync_method, ExposeSyncMethodsMixin
from marvin.extensions.types import ChatMessage, ChatThread, PersistedRun, AgentConfig
from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseStorage(ABC, Generic[T], ExposeSyncMethodsMixin):
    model: BaseModel = Field(
        ..., description="The model type for the storage. Required."
    )

    @expose_sync_method("list")
    async def list_async(self, **filters) -> List[T]:
        """List items with optional filters."""
        pass

    @expose_sync_method("create")
    async def create_async(self, key: str, value: T) -> None:
        """Set a value for a key."""
        pass

    @expose_sync_method("get")
    async def get_async(self, key: str) -> Optional[T]:
        """Get a value for a key."""
        pass

    @expose_sync_method("update")
    async def update_async(self, key: str, value: T) -> T:
        """Update a value for a key."""
        pass

    @expose_sync_method("filter")
    async def filter_async(self, **filters) -> List[T]:
        """Filter items based on given criteria."""
        pass


class BaseChatStore(BaseStorage[List[ChatMessage]]):
    model = ChatMessage

    @expose_sync_method("set_messages")
    async def set_messages_async(self, messages: List[ChatMessage]) -> None:
        for message in messages:
            await self.create_async(message)

    @expose_sync_method("get_messages")
    async def get_messages_async(self, **filters) -> List[ChatMessage]:
        """
        Memory expects messages to be store by a key. e.g. thread_id.
        This is up to the storage layer to implement.
        """
        return await self.filter_async(**filters) or []

    @expose_sync_method("add_message")
    async def add_message_async(self, key: str, message: ChatMessage) -> None:
        messages = await self.get_messages_async(key)
        messages.append(message)
        await self.set_messages_async(messages)

    # Preserve existing methods
    async def delete_messages_async(self, key: str) -> Optional[List[ChatMessage]]:
        raise NotImplementedError("Method delete_messages_async not implemented")

    async def delete_message_async(self, key: str, idx: int) -> Optional[ChatMessage]:
        raise NotImplementedError("Method delete_message_async not implemented")

    async def delete_last_message_async(self, key: str) -> Optional[ChatMessage]:
        raise NotImplementedError("Method delete_last_message_async not implemented")

    async def get_keys_async(self) -> List[str]:
        raise NotImplementedError("Method get_keys_async not implemented")


class BaseThreadStore(BaseStorage[ChatThread]):
    model = ChatThread

    @expose_sync_method("get_or_add_thread")
    @abstractmethod
    async def get_or_add_thread_async(
        self,
        thread_id: str,
        tenant_id: str,
        tags: List[str] | None = None,
        name: str | None = None,
        user_id: str | None = None,
    ) -> ChatThread:
        pass


class BaseRunStorage(BaseStorage[PersistedRun]):
    model = PersistedRun

    @expose_sync_method("get_or_create")
    async def get_or_create_async(self, id: str) -> tuple[PersistedRun, bool]:
        raise NotImplementedError("Method get_or_create_async not implemented")

    @expose_sync_method("init_db_run")
    async def init_db_run_async(
        self,
        run_id: str,
        thread_id: str | None = None,
        tenant_id: str | None = None,
        remote_run: Any = None,
        agent_id: str | None = None,
        user_message: str | None = None,
        tags: List[str] | None = None,
    ) -> PersistedRun:
        raise NotImplementedError("Method init_db_run_async not implemented")


class BaseAgentStorage(BaseStorage[AgentConfig]):
    model = AgentConfig


class BaseFileStorage(BaseStorage[DataSource]):
    model: BaseModel = DataSource

    @expose_sync_method("save_file")
    async def save_file_async(
        self, file: BinaryIO, file_id: str, metadata: Optional[dict] = None
    ) -> dict:
        """Save a file to storage and return its metadata."""
        raise NotImplementedError("Method save_file_async not implemented")

    @expose_sync_method("get_file")
    async def get_file_async(self, file_id: str) -> BinaryIO:
        """Retrieve a file from storage."""
        raise NotImplementedError("Method get_file_async not implemented")

    @expose_sync_method("sync_with_openai_assistant")
    async def sync_with_openai_assistant_async(self, assistant_id: str) -> List[dict]:
        """Sync files with a remote OpenAI assistant."""
        raise NotImplementedError(
            "Method sync_with_openai_assistant_async not implemented"
        )

    @expose_sync_method("upload_to_openai")
    async def upload_to_openai_async(self, file_id: str, purpose: str) -> dict:
        """Upload a file to OpenAI."""
        raise NotImplementedError("Method upload_to_openai_async not implemented")

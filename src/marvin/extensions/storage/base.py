"""Base interface classes for interacting with local storage objects."""

from abc import ABC, abstractmethod
from typing import Any, BinaryIO, List, Optional, Union
from uuid import UUID

from marvin.beta.assistants.threads import Thread
from marvin.extensions.types import ChatMessage
from marvin.extensions.types.run import PersistedRun
from marvin.extensions.types.thread import ChatThread
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method

class BaseStorage(ABC, ExposeSyncMethodsMixin):
    @abstractmethod
    def get(self, key: str) -> Any:
        """Get a value for a key."""
        ...

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Set a value for a key."""
        ...
        
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
    """
    Storage for threads
    """

    @abstractmethod
    async def get_or_add_thread_async(
        self, thread_id: str, tenant_id: str
    ) -> ChatThread:
        """Get or create a thread."""
        raise NotImplementedError("get_or_add_thread_async is not implemented")

    @expose_sync_method("remote_thread")
    async def remote_thread_async(
        self, thread_id: str | UUID, tenant_id: str | None = "default"
    ) -> Thread:
        """Get the remote thread."""
        # first check if the thread exists locally
        thread = await self.get_or_add_thread_async(thread_id, tenant_id)
        if thread and thread.external_id:
            return Thread(id=thread.external_id)
        try:
            remote_thread = Thread()
            remote_thread = await remote_thread.create_async()
            thread.external_id = remote_thread.id
            return remote_thread
        except Exception as e:
            raise Exception(f"Unable to sync remote thread: {e}")


class BaseFileStorage(ABC, ExposeSyncMethodsMixin):
    @abstractmethod
    async def save_file(
        self, file: BinaryIO, file_id: Union[str, UUID], metadata: Optional[dict] = None
    ) -> dict:
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

    @abstractmethod
    async def sync_with_openai_assistant(self, assistant_id: str) -> List[dict]:
        """Sync files with a remote OpenAI assistant."""
        ...

    @abstractmethod
    async def upload_to_openai(self, file_id: Union[str, UUID], purpose: str) -> dict:
        """Upload a file to OpenAI."""
        ...


class BaseRunStorage(ABC, ExposeSyncMethodsMixin):
    async def update(self, **kwargs) -> "BaseRunStorage":
        """Update a run."""
        run = await self.get_or_create_async(id=self.id)
        m = run.model_dump()
        m.update(kwargs)
        run = PersistedRun.model_validate(m)
        return await self.save_async(run)

    @abstractmethod
    async def get_or_create_async(self, id: str) -> tuple[PersistedRun, bool]:
        """Get or create a run."""
        ...

    @abstractmethod
    async def save_async(self, run: PersistedRun) -> PersistedRun:
        """Save a run."""
        ...

    async def init_db_run_async(
        self,
        run_id: str,
        thread_id: str | None = None,
        tenant_id: str | None = None,
        remote_run: Any = None,
        agent_id: str | None = None,
        user_message: str | None = None,
        tags: list[str] | None = None,
    ) -> PersistedRun:
        """Initialize a run."""
        run, created = await self.get_or_create_async(id=run_id)
        if created:
            run.thread_id = thread_id
            run.tenant_id = tenant_id
            run.agent_id = agent_id
            if user_message:
                run.data["user_message"] = user_message
            if tags:
                run.tags = tags
            run.status = "started"

        if remote_run:
            run.external_id = remote_run.id

        return await self.save_async(run)


class BaseAgentStorage(ABC, ExposeSyncMethodsMixin):
    @abstractmethod
    async def get_agent_config(self, agent_id: str) -> "BaseAgentStorage":
        """Get agent config."""
        ...

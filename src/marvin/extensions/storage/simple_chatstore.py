import datetime
import json
import os
from typing import Any, Dict, List, Optional

import fsspec
from marvin.extensions.storage.base import (
    BaseAgentStorage,
    BaseChatStore,
    BaseRunStorage,
    BaseThreadStore,
)
from marvin.extensions.types import ChatMessage
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.types.run import PersistedRun
from marvin.extensions.types.thread import ChatThread
from marvin.extensions.utilities.logging import pretty_log
from marvin.utilities.asyncio import expose_sync_method
from pydantic import Field


class SimpleChatStore(BaseChatStore):
    """Simple chat store."""

    store: Dict[str, List[ChatMessage]] = {}

    class Config:
        allow_extra = True
        arbitrary_types_allowed = True
        extra = "allow"

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "SimpleChatStore"

    @expose_sync_method("set_messages")
    async def set_messages_async(
        self, key: str, messages: List[ChatMessage], **kwargs
    ) -> None:
        """Set messages for a key."""
        self.store[key] = messages

    @expose_sync_method("get_messages")
    async def get_messages_async(self, key: str, **kwargs) -> List[ChatMessage]:
        """Get messages for a key."""
        print(self.store, type(self.store))
        return self.store.get(key, [])

    @expose_sync_method("add_message")
    async def add_message_async(
        self, key: str, message: ChatMessage, idx: Optional[int] = None
    ) -> None:
        """Add a message for a key."""
        if idx is None:
            self.store.setdefault(key, []).append(message)
        else:
            self.store.setdefault(key, []).insert(idx, message)

    @expose_sync_method("delete_messages")
    async def delete_messages_async(self, key: str) -> Optional[List[ChatMessage]]:
        """Delete messages for a key."""
        if key not in self.store:
            return None
        return self.store.pop(key)

    @expose_sync_method("delete_message")
    async def delete_message_async(self, key: str, idx: int) -> Optional[ChatMessage]:
        """Delete specific message for a key."""
        if key not in self.store:
            return None
        if idx >= len(self.store[key]):
            return None
        return self.store[key].pop(idx)

    @expose_sync_method("delete_last_message")
    async def delete_last_message_async(self, key: str) -> Optional[ChatMessage]:
        """Delete last message for a key."""
        if key not in self.store:
            return None
        return self.store[key].pop()

    @expose_sync_method("get_keys")
    async def get_keys_async(self) -> List[str]:
        """Get all keys."""
        return list(self.store.keys())

    @expose_sync_method("persist")
    async def persist_async(
        self,
        persist_path: str = "chat_store.json",
        fs: Optional[fsspec.AbstractFileSystem] = None,
    ) -> None:
        """Persist the docstore to a file."""
        fs = fs or fsspec.filesystem("file")
        dirpath = os.path.dirname(persist_path)
        if not fs.exists(dirpath):
            fs.makedirs(dirpath)

        with fs.open(persist_path, "w") as f:
            f.write(json.dumps(self.json()))

    @classmethod
    async def from_persist_path_async(
        cls,
        persist_path: str = "chat_store.json",
        fs: Optional[fsspec.AbstractFileSystem] = None,
    ) -> "SimpleChatStore":
        """Create a SimpleChatStore from a persist path."""
        fs = fs or fsspec.filesystem("file")
        if not fs.exists(persist_path):
            return cls()
        with fs.open(persist_path, "r") as f:
            data = json.load(f)
        return cls.validate_json(data)


class SimpleThreadStore(BaseThreadStore):
    """
    Thread storage that saves to the database.
    """

    store: Dict[str, List[Any]] = {}
    thread_id: str | None = None

    @expose_sync_method("get_or_add_thread")
    async def get_or_add_thread_async(
        self,
        thread_id: str,
        tenant_id: str,
        tags: list[str] | None = None,
        name: str | None = None,
        user_id: str | None = None,
    ) -> ChatThread:
        thread = self.store.get(thread_id, None)
        pretty_log(thread, thread_id)
        if thread is None:
            data = ChatThread(
                id=thread_id,
                tenant_id=tenant_id,
                tags=tags,
                name=name,
                user_id=user_id,
            )
            self.store[thread_id] = data.model_dump()
            return data
        else:
            pretty_log(thread)
            return ChatThread.model_validate(thread)


class SimpleRunStore(BaseRunStorage):
    """Simple run storage."""
    runs: Dict[str, PersistedRun] = {}

    @expose_sync_method("get_or_create")
    async def get_or_create_async(self, id: str) -> tuple[PersistedRun, bool]:
        if id not in self.runs:
            run = PersistedRun(id=id)
            self.runs[id] = run
            return run, True
        return self.runs[id], False

    @expose_sync_method("save")
    async def save_async(self, run: PersistedRun) -> PersistedRun:
        run.modified = datetime.datetime.now().timestamp()
        self.runs[run.id] = run
        return run

    @expose_sync_method("init_db_run")
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
        return await super().init_db_run_async(
            run_id, thread_id, tenant_id, remote_run, agent_id, user_message, tags
        )


class SimpleAgentStorage(BaseAgentStorage):
    """Simple agent storage."""

    store: Dict[str, List[Any]] = {}

    def get_agent_config(self, agent_id: str) -> AgentConfig:
        """Get agent config."""
        return self.store.get(agent_id, None)

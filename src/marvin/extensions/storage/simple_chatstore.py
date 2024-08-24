import json
import os
from typing import Any, Dict, List, Optional

import fsspec
from marvin.extensions.storage.base import BaseChatStore, BaseThreadStore
from marvin.extensions.types import ChatMessage
from marvin.utilities.asyncio import expose_sync_method
from pydantic import Field


class SimpleChatStore(BaseChatStore):
    """Simple chat store."""

    store: Dict[str, List[ChatMessage]] = Field(default_factory=dict)

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

    store: Dict[str, List[Any]] = Field(default_factory=dict)

    @expose_sync_method("get_or_add_thread")
    async def get_or_add_thread_async(
        self,
        thread_id: str,
        tenant_id: str,
        tags: list[str] | None = None,
        name: str | None = None,
        user_id: str | None = None,
    ) -> "SimpleThreadStore":
        thread = self.store.get(thread_id, None)
        if thread is None:
            data = {
                "id": thread_id,
                "tenant_id": tenant_id,
                "tags": tags,
                "name": name,
                "user_id": user_id,
            }
            thread = self.store[thread_id] = data
        return thread

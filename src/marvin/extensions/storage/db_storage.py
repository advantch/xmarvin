from typing import Dict, List, Optional
from uuid import UUID

import orjson
from apps.ai.models import ChatThread
from apps.ai.models import Message as MessageModel
from pydantic import Field

from marvin.extensions.storage.base import BaseChatStore, BaseThreadStore
from marvin.extensions.types import ChatMessage
from marvin.utilities.asyncio import expose_sync_method
from marvin.utilities.logging import logger


class DbChatStore(BaseChatStore):
    """Database chat store."""

    store: Dict[str, List[ChatMessage]] = Field(default_factory=dict)
    run_id: Optional[str | UUID] = None
    thread_id: Optional[str | UUID] = None
    tenant_id: Optional[str | UUID] = None

    class Config:
        allow_extra = True
        arbitrary_types_allowed = True
        extra = "allow"

    def __str__(self):
        return f"DbChatStore(thread_id={self.thread_id}, run_id={self.run_id}, tenant_id={self.tenant_id})"

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "DBChatStore"

    @expose_sync_method("set_messages")
    async def set_messages_async(self, key: str, messages: list[ChatMessage]) -> None:
        """Set messages for a key."""
        await MessageModel.objects.acreate_many(
            messages,
            thread_id=self.thread_id,
            run_id=self.run_id,
            tenant_id=self.tenant_id,
        )

    @expose_sync_method("get_messages")
    async def get_messages_async(self, key: str, **kwargs) -> List[ChatMessage]:
        """Get messages for a key."""
        messages = (
            MessageModel.objects.filter(thread_id=self.thread_id)
            .order_by("created")
            .all()
        )
        message_dicts = []
        async for message in messages:
            message_dicts.append(message.message)
        return [ChatMessage.model_validate(m) for m in message_dicts]

    @expose_sync_method("add_message")
    async def add_message_async(
        self, key: str, message: ChatMessage, idx: Optional[int] = None
    ) -> None:
        """Add a message for a key."""
        try:
            await MessageModel.objects.acreate_or_update(
                data=orjson.loads(message.model_dump_json()),
                thread_id=self.thread_id,
                tenant_id=self.tenant_id,
                run_id=self.run_id,
            )
        except Exception as e:
            logger.error(f"Error adding message to store: {e}")

    async def delete_messages_async(self, key: str, **kwargs) -> None:
        """Delete messages for a key."""
        message = await MessageModel.objects.filter(
            thread_id=self.thread_id, run_id=self.run_id
        ).afirst()
        if message:
            await message.adelete()
        return None

    async def delete_message_async(self, key: str, idx: int) -> Optional[ChatMessage]:
        """Delete specific message for a key."""
        if key not in self.store:
            return None
        if idx >= len(self.store[key]):
            return None
        return self.store[key].pop(idx)

    async def delete_last_message_async(self, key: str) -> Optional[ChatMessage]:
        """Delete last message for a key."""
        messages = await MessageModel.objects.filter(
            thread_id=self.thread_id, run_id=self.run_id
        ).aget()
        if not messages:
            return None
        message = messages[-1]
        await MessageModel.objects.adelete(message)
        return message

    async def get_keys_async(self) -> List[str]:
        """Get all keys."""
        return [self.thread_id]


def get_chat_name(name):
    return name[0:255]


class DbThreadStore(BaseThreadStore):
    """
    Thread storage that saves to the database.
    """

    @expose_sync_method("get_or_add_thread")
    async def get_or_add_thread_async(
        self,
        thread_id: str,
        tenant_id: str,
        tags: list[str] | None = None,
        name: str | None = None,
        user_id: str | None = None,
    ) -> "DbThreadStore":
        thread = await ChatThread.objects.aget_or_add_thread(
            thread_id, tenant_id=tenant_id, tags=tags, name=name, user_id=user_id
        )
        return thread

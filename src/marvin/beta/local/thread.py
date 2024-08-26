import uuid
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from marvin.beta.local.handlers import DefaultAssistantEventHandler
from marvin.extensions.memory.base import BaseMemory
from marvin.extensions.memory.temp_memory import Memory
from marvin.extensions.storage import BaseChatStore, SimpleChatStore
from marvin.extensions.storage.base import BaseThreadStore
from marvin.extensions.tools.tool import Tool
from marvin.extensions.types import ChatMessage
from marvin.extensions.utilities.message_parsing import (
    format_message_for_completion_endpoint,
)
from marvin.extensions.utilities.openai_streaming import PrintHandler
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method

from .assistant import LocalAssistant


class LocalThread(BaseModel, ExposeSyncMethodsMixin):
    id: str | uuid.UUID = Field(default_factory=lambda: str(uuid4()))
    storage: Optional[BaseChatStore] = SimpleChatStore()
    thread_storage: Optional[BaseThreadStore] | None = None
    memory: Optional[BaseMemory] = Memory(storage=SimpleChatStore())
    tenant_id: str
    messages: List[ChatMessage] = []
    _current_run_id: str | None = None

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    async def create_async(
        cls,
        id: str | None = Field(default=None, description="Thread ID for thread"),
        tenant_id: str | UUID = Field(default=None, description="Tenant ID for thread"),
        messages: List[ChatMessage] | None = None,
        storage: BaseChatStore | None = None,
        memory: BaseMemory | None = None,
        thread_storage: Optional[BaseThreadStore] = None,
        tags: List[str] | None = None,
    ) -> "LocalThread":
        """
        Creates a new thread.
        """
        thread_id = str(id) or str(uuid4())
        tenant_id = str(tenant_id) or "primary"
        memory = memory or Memory(storage=storage, index=thread_id, thread_id=thread_id)
        thread = cls(
            id=thread_id,
            tenant_id=tenant_id,
            storage=storage,
            memory=memory,
            thread_storage=thread_storage,
        )

        await thread.memory.load_async()
        for message in messages or []:
            await thread.add_message_async(message)

        # db storage
        if thread.thread_storage:
            await thread.thread_storage.get_or_add_thread_async(
                thread_id, tenant_id=tenant_id, tags=tags
            )
        return thread

    @classmethod
    def create(
        cls,
        id: str | None = Field(default=None, description="Thread ID for thread"),
        tenant_id: str | UUID = Field(default=None, description="Tenant ID for thread"),
        messages: List[ChatMessage] | None = None,
        storage: BaseChatStore | None = None,
        memory: BaseMemory | None = None,
        thread_storage: Optional[BaseThreadStore] = None,
        tags: List[str] | None = None,
    ):
        thread_id = str(id) or str(uuid4())
        tenant_id = str(tenant_id) or "primary"
        memory = memory or Memory(storage=storage, index=thread_id, thread_id=thread_id)
        thread = cls(
            id=thread_id,
            tenant_id=tenant_id,
            storage=storage,
            memory=memory,
            thread_storage=thread_storage,
        )

        thread.memory.load()
        for message in messages or []:
            thread.add_message(message)

        # db storage
        if thread.thread_storage:
            thread.thread_storage.get_or_add_thread(
                thread_id, tenant_id=tenant_id, tags=tags
            )
        return thread

    @expose_sync_method("add_message")
    async def add_message_async(self, message: ChatMessage) -> ChatMessage:
        await self.memory.put_async(message, index=self.id)
        return message

    @expose_sync_method("get_message")
    async def get_message_async(self, message_id: str) -> Optional[ChatMessage]:
        print("adding message")
        return self.memory.get(message_id, index=self.id)

    @expose_sync_method("list_messages")
    async def list_messages_async(
        self, index=None, limit: int = 100, order: str = "asc"
    ) -> List[ChatMessage]:
        if index is None:
            index = self.id
        return self.memory.get_messages(index=index)

    @expose_sync_method("get_history")
    async def get_history_async(self, limit: int = 100) -> List[ChatMessage]:
        return self.memory.get_messages(index=self.id)

    @expose_sync_method("get_messages_for_run")
    async def get_messages_for_run_async(self) -> List[Dict[str, str]]:
        history = await self.get_history_async()

        formatted_messages = format_message_for_completion_endpoint(messages=history)
        return formatted_messages

    @expose_sync_method("add_files")
    async def add_files_async(self, files: List[Any]) -> List[Any]:
        return []

    @expose_sync_method("run")
    async def run_async(
        self,
        assistant: LocalAssistant,
        message: ChatMessage | None = None,
        event_handler: PrintHandler = DefaultAssistantEventHandler,
        event_handler_kwargs: dict = None,
        tool_choice: str = "auto",
        tools: List[Tool] = None,
        context: dict | None = None,
        **kwargs,
    ):
        """
        Creates a new run for the thread.
        """
        from .run import LocalRun  # noqa

        event_handler_kwargs = event_handler_kwargs or {}
        memory = event_handler_kwargs.pop("memory", None) or self.memory
        context = event_handler_kwargs.pop("context", None) or context

        handler = event_handler or DefaultAssistantEventHandler(
            **event_handler_kwargs, context=context, memory=memory
        )
        run = LocalRun(
            assistant=assistant,
            thread=self,
            handler=handler,
            tool_choice=tool_choice or "auto",
            tools=tools or assistant.tools,
            **kwargs,
        )
        await run.execute_async(message=message)
        return run

import time
from typing import List
from uuid import UUID

from marvin.extensions.memory.base import BaseMemory
from marvin.extensions.storage.message_store import (
    BaseMessageStore,
    InMemoryMessageStore,
)
from marvin.extensions.types import ChatMessage
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method


class RuntimeMemory(BaseMemory, ExposeSyncMethodsMixin):
    """
    RuntimeMemory class to store messages at runtime.

    Attributes:
        index (str): The default index for storing messages.
        thread_id (str): The default thread ID for message organization.
        storage (BaseMessageStore | None): The storage backend for persisting messages.
        context (dict | None): Additional context information.
        loaded (bool): Flag indicating if messages have been loaded from storage.
        memory (dict[str, List[ChatMessage]]): In-memory storage of messages.
        previous_ids (List[str | UUID]): List of previously stored message IDs.
        requires_search (bool): Flag indicating if any message requires a search.
        hash_key (str | None): Unique identifier for this memory instance.

    Methods:
        load(): Load messages from storage.
        put(message: ChatMessage, index=None, persist=True): Add a message to memory.
        get(index): Retrieve messages for a specific index.
        get_all(): Retrieve all messages for the default index.
        list_messages(index=None, run_id=None): Retrieve messages as ChatMessage objects.
        get_messages(index=None): Retrieve messages for LLM processing.
        get_last_message(index=None, as_dicts=False): Get the last message in memory.

    Note:
        This class uses the ExposeSyncMethodsMixin to provide both synchronous and
        asynchronous versions of its methods.

    """

    index: str = "default"
    thread_id: str = "default"
    storage: BaseMessageStore | None = InMemoryMessageStore()
    context: dict | None = {}
    loaded: bool = False
    memory: dict[str, List[ChatMessage]] = {}
    previous_ids: List[str | UUID] = []
    requires_search: bool = False
    hash_key: str | None = None

    def __init__(self, storage=None, context=None, thread_id=None, index=None):
        super().__init__()
        self.memory = {"default": []}
        self.storage = storage or InMemoryMessageStore()
        self.thread_id = thread_id or "default"
        self.index = index or "default"
        self.load()
        self.hash_key = hash(
            f"{str(self.thread_id)}-{str(self.index)}-{str(time.time())}"
        )
        self.context = context or {}

    def _check_requires_search(self):
        """
        Check if the memory requires a search.
        Used by internal agents to check if the memory requires a search.
        """
        for message in self.memory[self.index]:
            if message.requires_search():
                self.requires_search = True
                break

    @expose_sync_method("load")
    async def load_async(self):
        """Load messages from storage."""
        if self.loaded:
            return self.memory

        messages = await self.storage.get_thread_messages_async(
            thread_id=self.thread_id
        )
        ids = [message.id for message in messages]

        self.previous_ids = ids
        self.memory[self.index] = messages
        self._check_requires_search()

        self.loaded = True
        return self.memory

    @expose_sync_method("put")
    async def put_async(self, message: ChatMessage, index=None, persist=True):
        """Put message in memory. By default, it persists the message in storage."""
        index = index or self.index
        if index not in self.memory:
            self.memory[index] = []
        # check if message exists
        if message.id in [m.id for m in self.memory[index]]:
            return
        self.memory[index].append(message)
        if self.storage:
            await self.storage.save_async(message, thread_id=self.thread_id)
        return self.memory

    @expose_sync_method("get")
    async def get_async(self, index):
        """Get messages from memory."""
        return self.memory.get(index, [])

    @expose_sync_method("get_all")
    async def get_all_async(self) -> List[ChatMessage]:
        """Get all messages from memory."""
        return await self.get_async(index=self.index)

    @expose_sync_method("list_messages")
    async def list_messages_async(self, index=None, run_id=None) -> List[ChatMessage]:
        """
        Retrieve messages as ChatMessage obj
        """
        index = index or self.index
        messages = await self.get_messages_async(thread_id=index) or []
        if run_id:
            messages = [message for message in messages if message.run_id == run_id]

        return messages

    @expose_sync_method("get_messages")
    async def get_messages_async(self, index=None) -> List[ChatMessage]:
        """
        Retrieve messages for llm
        """
        index = index or self.index
        messages = await self.get_async(index=index)
        return messages

    @expose_sync_method("get_last_message")
    async def get_last_message_async(self, index=None, as_dicts=False):
        messages = await self.get_messages_async(index=index)
        if len(messages) == 0:
            return None
        return messages[-1]

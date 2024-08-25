import time
from uuid import UUID

from marvin.extensions.memory.base import BaseMemory
from marvin.extensions.storage.base import BaseChatStore
from marvin.extensions.storage.simple_chatstore import SimpleChatStore
from marvin.extensions.types import ChatMessage
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method


class Memory(BaseMemory, ExposeSyncMethodsMixin):
    """
    Memory class to store messages.
    Every agent has some memory.
    Storage class can be used to persist.
    """

    index: str = "default"
    thread_id: str = "default"
    storage: BaseChatStore | None = SimpleChatStore()
    context: dict | None = {}
    loaded: bool = False
    memory: dict[str, list[ChatMessage]] = {}
    previous_ids: list[str | UUID] = []
    requires_search: bool = False
    hash_key: str | None = None

    def __init__(self, storage=None, context=None, thread_id=None, index=None):
        super().__init__()
        self.memory = {"default": []}
        self.storage = storage or SimpleChatStore()
        self.thread_id = thread_id or "default"
        self.index = thread_id or "default"
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
        print(self.storage, type(self.storage))
        messages = self.storage.get_messages(self.index)
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
            await self.storage.add_message_async(index, message)
        return self.memory

    @expose_sync_method("get")
    async def get_async(self, index):
        """Get messages from memory."""
        return self.memory.get(index, [])

    @expose_sync_method("get_all")
    async def get_all_async(self) -> list[ChatMessage]:
        """Get all messages from memory."""
        return await self.get_async(index=self.index)

    @expose_sync_method("list_messages")
    async def list_messages_async(self, index=None, run_id=None) -> list[ChatMessage]:
        """
        Retrieve messages as ChatMessage obj
        """
        index = index or self.index
        messages = await self.get_async(index=index) or []
        if run_id:
            messages = [message for message in messages if message.run_id == run_id]

        return messages

    @expose_sync_method("get_messages")
    async def get_messages_async(self, index=None) -> list[ChatMessage]:
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

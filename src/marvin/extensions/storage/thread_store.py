from typing import List, Optional

from marvin.extensions.storage.base import BaseStorage
from marvin.extensions.storage.redis_base import RedisBase
from marvin.extensions.types import ChatThread
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method


class BaseThreadStore(BaseStorage[ChatThread], ExposeSyncMethodsMixin):
    @expose_sync_method("save_thread")
    async def save_thread_async(self, thread: ChatThread) -> None:
        raise NotImplementedError("save_thread not implemented")

    @expose_sync_method("get_thread")
    async def get_thread_async(
        self, thread_id: str, tenant_id: str | None = None
    ) -> Optional[ChatThread]:
        raise NotImplementedError("get_thread not implemented")

    @expose_sync_method("get_or_create_thread")
    async def get_or_create_thread_async(
        self, thread_id: str, tenant_id: str | None = None
    ) -> ChatThread:
        raise NotImplementedError("get_or_create_thread not implemented")

    @expose_sync_method("list_threads")
    async def list_threads_async(
        self, filter_params: Optional[dict] = None, tenant_id: str | None = None
    ) -> List[ChatThread]:
        raise NotImplementedError("list_threads not implemented")


class InMemoryThreadStore(BaseThreadStore, ExposeSyncMethodsMixin):
    def __init__(self):
        self.threads = {}

    @expose_sync_method("save_thread")
    async def save_thread_async(self, thread: ChatThread) -> None:
        self.threads[thread.id] = thread

    @expose_sync_method("get_thread")
    async def get_thread_async(
        self, thread_id: str, tenant_id: str | None = None
    ) -> Optional[ChatThread]:
        return self.threads.get(thread_id)

    @expose_sync_method("get_or_create_thread")
    async def get_or_create_thread_async(
        self, thread_id: str, tenant_id: str | None = None
    ) -> ChatThread:
        thread = self.threads.get(thread_id)
        if not thread:
            thread = ChatThread(id=thread_id, tenant_id=tenant_id)
            await self.save_thread_async(thread)
        return thread

    @expose_sync_method("list_threads")
    async def list_threads_async(
        self, filter_params: Optional[dict] = None, tenant_id: str | None = None
    ) -> List[ChatThread]:
        if not filter_params:
            return [
                thread
                for thread in self.threads.values()
                if thread.tenant_id == tenant_id
            ]
        return [
            thread
            for thread in self.threads.values()
            if all(getattr(thread, k, None) == v for k, v in filter_params.items())
        ]


class RedisThreadStore(BaseThreadStore, RedisBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect()

    @expose_sync_method("save_thread")
    async def save_thread_async(self, thread: ChatThread) -> None:
        self.redis_client.set(f"thread:{thread.id}", thread.model_dump_json())

    @expose_sync_method("get_thread")
    async def get_thread_async(self, thread_id: str) -> Optional[ChatThread]:
        thread_data = self.redis_client.get(f"thread:{thread_id}")
        return ChatThread.model_validate_json(thread_data) if thread_data else None

    @expose_sync_method("get_or_create_thread")
    async def get_or_create_thread_async(
        self, thread_id: str, tenant_id: str | None = None
    ) -> ChatThread:
        thread = await self.get_thread_async(thread_id)
        if not thread:
            thread = ChatThread(id=thread_id, tenant_id=tenant_id)
            await self.save_thread_async(thread)
        return thread

    @expose_sync_method("list_threads")
    async def list_threads_async(
        self, filter_params: Optional[dict] = None
    ) -> List[ChatThread]:
        all_threads = [
            ChatThread.model_validate_json(thread_data)
            for thread_data in self.redis_client.mget(
                self.redis_client.keys("thread:*")
            )
        ]
        if not filter_params:
            return all_threads
        return [
            thread
            for thread in all_threads
            if all(getattr(thread, k, None) == v for k, v in filter_params.items())
        ]

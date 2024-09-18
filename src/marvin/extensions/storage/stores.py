import uuid
from typing import Any, BinaryIO, Generic, List, Optional, Tuple, TypeVar

from marvin.extensions.utilities.unique_id import generate_uuid_from_string
from marvin.extensions.storage.base import (
    BaseAgentStorage,
    BaseChatStore,
    BaseDataSourceStorage,
    BaseFileStorage,
    BaseRunStorage,
    BaseStorage,
    BaseThreadStore,
)
from marvin.extensions.types.agent import AgentConfig
from marvin.extensions.types.message import ChatMessage
from marvin.extensions.types.run import PersistedRun
from marvin.extensions.types.thread import ChatThread
from marvin.extensions.utilities.serialization import to_serializable
from marvin.extensions.types.data_source import DataSource
from marvin.extensions.storage.file_storage.local_file_storage import LocalFileStorage
from marvin.utilities.asyncio import expose_sync_method

from .layers import JsonFileStore, MemStore

T = TypeVar("T")


class MemoryStore(BaseStorage, Generic[T]):
    """
    Interface for storing data in memory.
    API between RuntimeMemory and MemoryStorageLayer
    Include the core methods required for storing data by default a JSON
    """

    store: MemStore | JsonFileStore = MemStore()

    @expose_sync_method("list")
    async def list_async(self) -> List[T]:
        return self.store.list()

    def _generic_from_serializable(self, data: Any) -> T:
        if self.model is None:
            raise ValueError("Model not set")
        return self.model.model_validate(data)

    @expose_sync_method("create")
    async def create_async(self, value: T, key: Optional[str] = None) -> T:
        key = key or getattr(value, "id", None) or str(uuid.uuid4())
        if hasattr(value, "id"):
            value.id = key
        if not isinstance(value, dict):
            value = value.model_dump()
        self.store.create(key, value)
        return value

    @expose_sync_method("get")
    async def get_async(self, key: str) -> Optional[T]:
        data = self.store.get(key)
        if data is None:
            return None
        return self._generic_from_serializable(data)

    @expose_sync_method("update")
    async def update_async(self, value: T, key: Optional[str] = None) -> T:
        key = key or getattr(value, "id", None)
        if key is None:
            raise ValueError("Either key or value.id must be provided")
        self.store.set(key, to_serializable(value))
        return value

    @expose_sync_method("filter")
    async def filter_async(self, **filters) -> List[T]:
        """
        Filter items based on given criteria.
        """
        return self.store.list(**filters)


class ChatStore(MemoryStore[List[ChatMessage]], BaseChatStore):

    store: MemStore = MemStore()

    @expose_sync_method("delete_messages")
    async def delete_messages_async(self, key: str) -> Optional[List[ChatMessage]]:
        return self.store.delete(key)

    @expose_sync_method("delete_message")
    async def delete_message_async(self, key: str, idx: int) -> Optional[ChatMessage]:
        if key in self.store and 0 <= idx < len(self.store[key]):
            return self.store[key].pop(idx)
        return None

    @expose_sync_method("delete_last_message")
    async def delete_last_message_async(self, key: str) -> Optional[ChatMessage]:
        if key in self.store and self.store[key]:
            return self.store[key].pop()
        return None

    @expose_sync_method("get_keys")
    async def get_keys_async(self) -> List[str]:
        return list(self.store.keys())

    @expose_sync_method("get_messages")
    async def filter_async(self, **filters) -> List[ChatMessage]:
        return self.store.filter(**filters)


class ThreadStore(MemoryStore[ChatThread], BaseThreadStore):

    store = MemStore()

    @expose_sync_method("get_or_add_thread")
    async def get_or_add_thread_async(
        self,
        thread_id: str,
        tenant_id: str,
        tags: List[str] | None = None,
        name: str | None = None,
        user_id: str | None = None,
    ) -> ChatThread:
        if thread_id not in self.store:
            thread = ChatThread(
                id=thread_id,
                tenant_id=tenant_id,
                tags=tags,
                name=name,
                user_id=user_id,
            )
            await self.create_async(thread, key=thread_id)
        return await self.get_async(thread_id)


class RunStore(MemoryStore[PersistedRun], BaseRunStorage):
    @expose_sync_method("get_or_create")
    async def get_or_create_async(self, id: str) -> tuple[PersistedRun, bool]:
        run = self.store.get(id)
        if run is None:
            run = PersistedRun(id=id)
            await self.create_async(run, key=id)
            return run, True
        return run, False

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
        run, created = await self.get_or_create_async(run_id)
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
        return await self.update_async(run)


class AgentStore(MemoryStore[AgentConfig], BaseAgentStorage):
    pass


class DataSourceStore(MemoryStore[DataSource], BaseDataSourceStorage):
    store = MemStore()
    file_storage: BaseFileStorage = LocalFileStorage()

    def clear_file_storage(self):
        self.file_storage.clear()

    @expose_sync_method("list_files")
    async def list_files_async(self, thread_id: str| None = None) -> List[DataSource]:
        if thread_id is None:
            files = self.store.list()
        else:
            files = self.store.filter(thread_id=thread_id)
            print(files, 'the files')
        return [DataSource.model_validate(f) for f in files]
    
    @expose_sync_method("delete_file")
    async def delete_file_async(self, file_id: str) -> bool:
        data_source = await self.get_async(file_id)
        if data_source is None:
            raise FileNotFoundError(f"File with id {file_id} not found")
        
        file_storage = self._file_storage()
        await file_storage.delete_file_async(file_id)
        self.store.delete(file_id)
    
    @expose_sync_method("save_file")
    async def save_file_async(self, file: BinaryIO, metadata: dict, file_id: str | None = None) -> DataSource:
        file_id = file_id or uuid.uuid4().hex
        file_storage = self._file_storage()
        
        # Save file to file storage
        file_info = await file_storage.save_file_async(file, str(file_id), metadata)
        
        # Create and save DataSource object
        data_source = DataSource(
            id=str(file_id),
            type="file",
            metadata=metadata,
            file_path=file_info.get("file_path"),
            file_name=file_info.get("file_name"),
            file_type=file_info.get("file_type"),
            file_size=file_info.get("size"),
            file_info=file_info,
            status="loaded"
        )
        await self.create_async(data_source, key=file_id)
        
        return data_source

    @expose_sync_method("get_file")
    async def get_file_async(self, file_id: str) -> Tuple[DataSource, BinaryIO]:
        data_source = await self.get_async(file_id)
        if data_source is None:
            raise FileNotFoundError(f"File with id {file_id} not found")
        
        file_storage = self._file_storage()
        file_content = await file_storage.get_file_async(file_id)
        
        return data_source, file_content

    
    def _file_storage(self) -> BaseFileStorage:
        if self.file_storage is None:
            from marvin.extensions.settings import extension_settings
            self.file_storage = extension_settings.storage.data_source_storage_class()
        return self.file_storage
    

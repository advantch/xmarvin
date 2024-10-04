from typing import List, Optional

from marvin.extensions.storage.base import BaseStorage
from marvin.extensions.storage.redis_base import RedisBase
from marvin.extensions.types import VectorStore
from marvin.utilities.asyncio import expose_sync_method


class BaseVectorStore(BaseStorage[VectorStore]):
    @expose_sync_method("save_vector")
    async def save_vector_async(self, vector: VectorStore) -> None:
        raise NotImplementedError("save_vector_async not implemented")

    @expose_sync_method("get_vector")
    async def get_vector_async(self, vector_id: str) -> Optional[VectorStore]:
        raise NotImplementedError("get_vector_async not implemented")

    @expose_sync_method("list_vectors")
    async def list_vectors_async(
        self, filter_params: Optional[dict] = None
    ) -> List[VectorStore]:
        raise NotImplementedError("list_vectors_async not implemented")


class InMemoryVectorStore(BaseVectorStore):
    def __init__(self):
        self.vector_stores = {}

    @expose_sync_method("save_vector")
    async def save_vector_async(self, vector_store: VectorStore) -> None:
        self.vector_stores[vector_store.id] = vector_store

    @expose_sync_method("get_vector")
    async def get_vector_async(self, vector_store_id: str) -> Optional[VectorStore]:
        return self.vector_stores.get(vector_store_id)

    @expose_sync_method("list_vectors")
    async def list_vectors_async(
        self, filter_params: Optional[dict] = None
    ) -> List[VectorStore]:
        if not filter_params:
            return list(self.vector_stores.values())
        return [
            vs
            for vs in self.vector_stores.values()
            if all(getattr(vs, k, None) == v for k, v in filter_params.items())
        ]


class RedisVectorStore(BaseVectorStore, RedisBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect()

    @expose_sync_method("save_vector")
    async def save_vector_async(self, vector_store: VectorStore) -> None:
        self.redis_client.set(
            f"vector_store:{vector_store.id}", vector_store.model_dump_json()
        )

    @expose_sync_method("get_vector")
    async def get_vector_async(self, vector_store_id: str) -> Optional[VectorStore]:
        vector_store_data = self.redis_client.get(f"vector_store:{vector_store_id}")
        return (
            VectorStore.model_validate_json(vector_store_data)
            if vector_store_data
            else None
        )

    @expose_sync_method("list_vectors")
    async def list_vectors_async(
        self, filter_params: Optional[dict] = None
    ) -> List[VectorStore]:
        all_vector_stores = [
            VectorStore.model_validate_json(vs_data)
            for vs_data in self.redis_client.mget(
                self.redis_client.keys("vector_store:*")
            )
        ]
        if not filter_params:
            return all_vector_stores
        return [
            vs
            for vs in all_vector_stores
            if all(getattr(vs, k, None) == v for k, v in filter_params.items())
        ]

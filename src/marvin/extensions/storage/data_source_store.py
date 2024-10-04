from typing import List, Optional

from marvin.extensions.storage.base import BaseStorage
from marvin.extensions.storage.redis_base import RedisBase
from marvin.extensions.types import DataSource
from marvin.extensions.utilities.file_utilities import ContentFile, File
from marvin.utilities.asyncio import ExposeSyncMethodsMixin, expose_sync_method


class BaseDataSourceStore(BaseStorage[DataSource], ExposeSyncMethodsMixin):
    @expose_sync_method("save_data_source")
    async def save_data_source_async(self, data_source: DataSource) -> DataSource:
        raise NotImplementedError("save_data_source_async not implemented")

    @expose_sync_method("get_data_source")
    async def get_data_source_async(self, data_source_id: str) -> Optional[DataSource]:
        raise NotImplementedError("get_data_source_async not implemented")

    @expose_sync_method("list_data_sources")
    async def list_data_sources_async(
        self, filter_params: Optional[dict] = None
    ) -> List[DataSource]:
        raise NotImplementedError("list_data_sources_async not implemented")

    @expose_sync_method("get_file_content_by_file_id")
    async def get_file_content_by_file_id_async(self, file_id: str) -> Optional[str]:
        raise NotImplementedError("get_file_content_by_file_id_async not implemented")

    @expose_sync_method("upload_file")
    async def upload_file_async(
        self, file_id: str, file_upload: File | ContentFile
    ) -> None:
        raise NotImplementedError("upload_file_async not implemented")

    @expose_sync_method("delete_file")
    async def delete_file_async(self, file_id: str) -> None:
        raise NotImplementedError("delete_file_async not implemented")


class InMemoryDataSourceStore(BaseDataSourceStore):
    def __init__(self):
        self.data_sources = {}

    @expose_sync_method("save_data_source")
    async def save_data_source_async(self, data_source: DataSource) -> DataSource:
        self.data_sources[data_source.id] = data_source
        return data_source

    @expose_sync_method("get_data_source")
    async def get_data_source_async(self, data_source_id: str) -> Optional[DataSource]:
        return self.data_sources.get(data_source_id)

    @expose_sync_method("list_data_sources")
    async def list_data_sources_async(
        self, filter_params: Optional[dict] = None
    ) -> List[DataSource]:
        if not filter_params:
            return list(self.data_sources.values())
        return [
            ds
            for ds in self.data_sources.values()
            if all(getattr(ds, k, None) == v for k, v in filter_params.items())
        ]

    @expose_sync_method("get_file_content_by_file_id")
    async def get_file_content_by_file_id_async(self, file_id: str) -> Optional[str]:
        """
        Get the file content by file_id.
        Uses local file storage as default for now.
        In Django, this will should be handled by the underlying model.
        """
        data_sources = await self.list_data_sources_async(
            filter_params={"file_id": file_id}
        )
        if not data_sources:
            return None
        ds = data_sources[0]
        if ds.file_store_metadata:
            file_path = ds.file_store_metadata.file_path
            if not file_path:
                return None
            with open(file_path, "r") as f:
                return f.read()
        return None


class RedisDataSourceStore(BaseDataSourceStore, RedisBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect()

    @expose_sync_method("save_data_source")
    async def save_data_source_async(self, data_source: DataSource) -> DataSource:
        self.redis_client.set(
            f"data_source:{data_source.id}", data_source.model_dump_json()
        )

    @expose_sync_method("get_data_source")
    async def get_data_source_async(self, data_source_id: str) -> Optional[DataSource]:
        data_source_data = self.redis_client.get(f"data_source:{data_source_id}")
        return (
            DataSource.model_validate_json(data_source_data)
            if data_source_data
            else None
        )

    @expose_sync_method("list_data_sources")
    async def list_data_sources_async(
        self, filter_params: Optional[dict] = None
    ) -> List[DataSource]:
        all_data_sources = [
            DataSource.model_validate_json(ds_data)
            for ds_data in self.redis_client.mget(
                self.redis_client.keys("data_source:*")
            )
        ]
        if not filter_params:
            return all_data_sources
        return [
            ds
            for ds in all_data_sources
            if all(getattr(ds, k, None) == v for k, v in filter_params.items())
        ]

    @expose_sync_method("get_file_content_by_file_id")
    async def get_file_content_by_file_id_async(self, file_id: str) -> Optional[str]:
        data_sources = await self.list_data_sources_async(
            filter_params={"file_id": file_id}
        )
        if not data_sources:
            return None
        ds = data_sources[0]
        if ds.upload:
            return ds.upload.content
        return None

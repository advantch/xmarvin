import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from marvin.extensions.storage.stores import DataSourceStore
from marvin.extensions.storage.file_storage.local_file_storage import LocalFileStorage
from marvin.extensions.storage.file_storage.s3_storage import S3Storage
from marvin.extensions.types import DataSource
from marvin.extensions.storage.base import BaseFileStorage
from marvin.extensions.settings import extension_settings

data_source_store = DataSourceStore()

@pytest.mark.parametrize("file_storage_cls", [LocalFileStorage, S3Storage])
@pytest.mark.asyncio
async def test_file_storage_operations(file_storage_cls):
    extension_settings.storage.file_storage_class = file_storage_cls
    file = io.BytesIO(b"test content")
    file = io.BytesIO(b"test content")
    metadata = {"content_type": "text/plain"}
    data_source_store.clear_file_storage()
    data_source = await data_source_store.save_file_async(file, metadata)

    assert isinstance(data_source, DataSource)
    assert data_source.type == "file"
    assert data_source.metadata == metadata
    
    assert data_source.file_path is not None
    assert data_source.file_id is not None
    # test get_file
    ds, file_content = await data_source_store.get_file_async(str(data_source.id))
    assert file_content.getvalue() == b"test content", ds

    # test update_file_metadata
    new_metadata = {"name": "test.txt"}
    await data_source_store.update_file_metadata_async(str(data_source.id), new_metadata)
    data_source = await data_source_store.get_async(str(data_source.id))
    assert data_source.status == "loaded"

    # list_files
    data_sources = await data_source_store.list_files_async()
    assert len(data_sources) == 1, [d for d in data_sources]
    assert data_sources[0].id == data_source.id
    assert data_sources[0].status == "loaded", data_sources[0]
    # test delete_file
    await data_source_store.delete_file_async(data_source.id)


    search_data_source = await data_source_store.get_async(str(data_source.id))
    assert search_data_source is None, search_data_source


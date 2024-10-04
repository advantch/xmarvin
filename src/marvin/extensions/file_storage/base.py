# base BlobStorage

from abc import ABC
from typing import Generic, List, Optional, TypeVar

from marvin.extensions.types.data_source import FileStoreMetadata

T = TypeVar("T")


class BaseBlobStorage(ABC, Generic[T]):
    async def save_file_async(self, key: str, content: T) -> FileStoreMetadata:
        raise NotImplementedError("save_file_async not implemented")

    async def get_file_async(self, key: str) -> Optional[T]:
        raise NotImplementedError("get_file_async not implemented")

    async def list_files_async(self, filter_params: Optional[dict] = None) -> List[T]:
        raise NotImplementedError("list_files_async not implemented")

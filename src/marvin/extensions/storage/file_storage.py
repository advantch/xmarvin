

from io import BytesIO
from typing import Union, Optional, BinaryIO
from uuid import UUID


from marvin.extensions.storage.base import BaseFileStorage


class SimpleFileStorage(BaseFileStorage):
    def __init__(self):
        self.files = {}
        self.metadata = {}

    async def save_file(self, file: BinaryIO, file_id: Union[str, UUID], metadata: Optional[dict] = None) -> dict:
        content = file.read()
        self.files[str(file_id)] = content
        file_metadata = metadata or {}
        file_metadata.update({
            "file_id": str(file_id),
            "size": len(content),
        })
        self.metadata[str(file_id)] = file_metadata
        return file_metadata

    async def get_file(self, file_id: Union[str, UUID]) -> BinaryIO:
        content = self.files.get(str(file_id))
        if content is None:
            raise FileNotFoundError(f"File with id {file_id} not found")
        return BytesIO(content)

    async def delete_file(self, file_id: Union[str, UUID]) -> None:
        file_id_str = str(file_id)
        if file_id_str in self.files:
            del self.files[file_id_str]
            del self.metadata[file_id_str]
        else:
            raise FileNotFoundError(f"File with id {file_id} not found")

    async def get_file_metadata(self, file_id: Union[str, UUID]) -> dict:
        metadata = self.metadata.get(str(file_id))
        if metadata is None:
            raise FileNotFoundError(f"File with id {file_id} not found")
        return metadata
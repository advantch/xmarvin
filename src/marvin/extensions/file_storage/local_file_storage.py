import mimetypes
import os
from io import BytesIO
from pathlib import Path
from typing import Callable, Union
from uuid import UUID

import aiohttp

from marvin.extensions.file_storage.base import BaseBlobStorage
from marvin.extensions.types.data_source import FileStoreMetadata
from marvin.extensions.utilities.file_utilities import ContentFile, File, UploadedFile
from marvin.utilities.asyncio import expose_sync_method


class LocalFileStorage(BaseBlobStorage):
    """
    Local file system storage.
    """

    root = Path(os.path.dirname(__file__))
    base_path: str = os.path.join(root, "marvin/files")
    is_file_system: bool = True
    prefix: str | None = ""
    construct_prefix: str | Callable = "local"

    def __init__(
        self, base_path: str | Callable = None, construct_prefix: str | Callable = None
    ):
        if base_path:
            self.base_path = base_path
        if construct_prefix:
            self.prefix = (
                construct_prefix
                if isinstance(construct_prefix, str)
                else construct_prefix()
            )

    def get_file_path(self, file_id: str | UUID) -> str:
        # todo allow passing of data source to extract metadata for files.
        return os.path.join(self.base_path, self.prefix, str(file_id))

    def _get_file_name(
        self,
        file: File | ContentFile | UploadedFile,
        file_id: Union[str, UUID, None] = None,
    ) -> str:
        return (
            getattr(file, "name", None)
            or getattr(file, "file_name", None)
            or str(file_id)
        )

    def _get_file_type(
        self,
        file: File | ContentFile | UploadedFile,
        file_id: Union[str, UUID, None] = None,
    ) -> str:
        content_type = (
            getattr(file, "content_type", None)
            or getattr(file, "file_type", None)
            or str(file_id)
        )
        try:
            return ContentFile.guess_content_type(file.read())
        except Exception:
            return content_type

    @expose_sync_method("save_file")
    async def save_file_async(
        self,
        file: File | ContentFile | UploadedFile,
        file_id: Union[str, UUID, None] = None,
        file_name: str = None,
    ) -> FileStoreMetadata:
        file_metadata = FileStoreMetadata(
            file_id=str(file_id),
            file_size=getattr(file, "size", None),
            file_name=file_name or self._get_file_name(file, file_id),
            file_type=getattr(file, "content_type", None),
        )

        # Create the full directory path
        # make sure the base path exists
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)
        file_path = os.path.join(self.base_path, str(file_id))
        file_metadata.file_path = file_path
        # Save file to local storage
        with open(file_path, "wb") as f:
            f.write(file.read())
        return file_metadata

    async def _write_file(
        self, content: bytes, file_id: Union[str, UUID], file_name: str
    ) -> FileStoreMetadata:
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path, exist_ok=True)
        file_path = os.path.join(self.base_path, str(file_id))

        with open(file_path, "wb") as f:
            f.write(content)

        mime_type, _ = mimetypes.guess_type(file_name)
        file_type = mime_type or "application/octet-stream"

        return FileStoreMetadata(
            file_id=str(file_id),
            file_size=len(content),
            file_name=file_name,
            file_type=file_type,
            file_path=file_path,
        )

    @expose_sync_method("get_file")
    async def get_file_async(self, file_metadata: FileStoreMetadata) -> BytesIO:
        file_path = file_metadata.file_path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File with id {file_metadata.file_id} not found")
        mime_type, _ = mimetypes.guess_type(file_path)

        if mime_type and mime_type.startswith("text"):
            # For text files, return a StringIO object
            with open(file_path, "r", encoding="utf-8") as f:
                return ContentFile(f.read(), name=file_metadata.file_name)
        else:
            # For binary files, return a BytesIO object
            with open(file_path, "rb") as f:
                return ContentFile(f.read(), name=file_metadata.file_name)

    @expose_sync_method("delete_file")
    async def delete_file_async(self, file_metadata: FileStoreMetadata) -> None:
        file_path = file_metadata.file_path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File with id {file_metadata.file_id} not found")
        os.remove(file_path)

    @expose_sync_method("download_file")
    async def download_file_async(self, url: str, file_id: Union[str, UUID]) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    return await self.save_file_async(BytesIO(content), file_id)
                else:
                    raise Exception(f"Failed to download file from {url}")

    @expose_sync_method("request_presigned_url")
    async def request_presigned_url_async(
        self, file_id: str, private: bool = True
    ) -> dict:
        # This is a mock implementation
        return {
            "id": file_id,
            "upload_url": f"https://example.com/upload/{file_id}",
        }

    def clear(self):
        # find all files in the base path and delete them
        # only use for testing
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                os.remove(os.path.join(root, file))
            for dir in dirs:
                os.rmdir(os.path.join(root, dir))

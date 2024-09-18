from io import BytesIO
import os
from typing import BinaryIO, List, Optional, Union
from uuid import UUID

import aiohttp

from marvin.extensions.storage.base import BaseFileStorage, expose_sync_method
from marvin.utilities.openai import get_openai_client


class LocalFileStorage(BaseFileStorage):

    base_path: str = "/tmp/marvin/files"
    is_file_system: bool = True

    def __init__(self):
        self.files = {}
        self.metadata = {}

    @expose_sync_method("save_file")
    async def save_file_async(
        self, file: BinaryIO, file_id: Union[str, UUID], metadata: Optional[dict] = None
    ) -> dict:
        content = file.read()
        self.files[str(file_id)] = content
        file_metadata = metadata or {}
        file_metadata.update(
            {
                "file_id": str(file_id),
                "file_size": len(content),
                "file_name": file_id,
                "file_type": "file",
            }
        )
        
        # Create the full directory path
        file_path = os.path.join(self.base_path, str(file_id))
        file_metadata["file_path"] = file_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Save file to local storage
        with open(file_path, "wb") as f:
            f.write(content)

        self.metadata[str(file_id)] = file_metadata
        return file_metadata

    @expose_sync_method("get_file")
    async def get_file_async(self, file_id: Union[str, UUID]) -> BinaryIO:
        content = self.files.get(str(file_id))
        if content is None:
            raise FileNotFoundError(f"File with id {file_id} not found")
        return BytesIO(content)

    @expose_sync_method("delete_file")
    async def delete_file_async(self, file_id: Union[str, UUID]) -> None:
        file_id_str = str(file_id)
        if file_id_str in self.files:
            del self.files[file_id_str]
            del self.metadata[file_id_str]
        else:
            raise FileNotFoundError(f"File with id {file_id} not found")

    @expose_sync_method("get_file_metadata")
    async def get_file_metadata_async(self, file_id: Union[str, UUID]) -> dict:
        metadata = self.metadata.get(str(file_id))
        if metadata is None:
            raise FileNotFoundError(f"File with id {file_id} not found")
        return metadata

    @expose_sync_method("sync_with_openai_thread")
    async def sync_with_openai_thread_async(self, thread_id: str) -> List[dict]:
        client = get_openai_client()
        messages = await client.beta.threads.messages.list(thread_id)

        file_ids = []
        for message in messages.data:
            file_ids.extend(message.file_ids)

        synced_files = []
        for file_id in file_ids:
            file = await client.files.retrieve(file_id)
            content_response = await client.files.content(file_id)
            content = await content_response.aread()
            metadata = await self.save_file_async(
                BytesIO(content), file_id, {"purpose": file.purpose}
            )
            synced_files.append(metadata)

        return synced_files

    @expose_sync_method("sync_with_openai_assistant")
    async def sync_with_openai_assistant_async(self, assistant_id: str) -> List[dict]:
        client = get_openai_client()
        assistant = await client.beta.assistants.retrieve(assistant_id)

        synced_files = []
        for file_id in assistant.file_ids:
            file = await client.files.retrieve(file_id)
            content_response = await client.files.content(file_id)
            content = await content_response.aread()
            metadata = await self.save_file_async(
                BytesIO(content), file_id, {"purpose": file.purpose}
            )
            synced_files.append(metadata)

        return synced_files

    @expose_sync_method("upload_to_openai")
    async def upload_to_openai_async(
        self, file_id: Union[str, UUID], purpose: str
    ) -> dict:
        client = get_openai_client()
        file_content = await self.get_file_async(file_id)
        file_metadata = await self.get_file_metadata_async(file_id)

        response = await client.files.create(file=file_content, purpose=purpose)

        # Update local metadata with OpenAI file ID
        file_metadata["openai_file_id"] = response.id
        await self.save_file_async(file_content, file_id, file_metadata)

        return response.model_dump()

    @expose_sync_method("download_file")
    async def download_file_async(self, url: str, file_id: Union[str, UUID]) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    return await self.save_file_async(
                        BytesIO(content), file_id, {"url": url}
                    )
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

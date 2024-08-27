from io import BytesIO
from typing import BinaryIO, Optional, Union, List
from uuid import UUID
import aiohttp

from abc import ABC, abstractmethod
from marvin.extensions.storage.base import ExposeSyncMethodsMixin
from marvin.utilities.openai import get_openai_client



class BaseFileStorage(ABC, ExposeSyncMethodsMixin):
    @abstractmethod
    async def save_file(
        self, file: BinaryIO, file_id: Union[str, UUID], metadata: Optional[dict] = None
    ) -> dict:
        """Save a file to storage and return its metadata."""
        pass

    @abstractmethod
    async def get_file(self, file_id: Union[str, UUID]) -> BinaryIO:
        """Retrieve a file from storage."""
        pass

    @abstractmethod
    async def delete_file(self, file_id: Union[str, UUID]) -> None:
        """Delete a file from storage."""
        pass

    @abstractmethod
    async def get_file_metadata(self, file_id: Union[str, UUID]) -> dict:
        """Retrieve metadata for a file."""
        pass

    @abstractmethod
    async def sync_with_openai_assistant(self, assistant_id: str) -> List[dict]:
        """Sync files with a remote OpenAI assistant."""
        ...

    @abstractmethod
    async def upload_to_openai(self, file_id: Union[str, UUID], purpose: str) -> dict:
        """Upload a file to OpenAI."""
        ...



class SimpleFileStorage(BaseFileStorage):
    def __init__(self):
        self.files = {}
        self.metadata = {}

    async def save_file(
        self, file: BinaryIO, file_id: Union[str, UUID], metadata: Optional[dict] = None
    ) -> dict:
        content = file.read()
        self.files[str(file_id)] = content
        file_metadata = metadata or {}
        file_metadata.update(
            {
                "file_id": str(file_id),
                "size": len(content),
            }
        )
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

    async def sync_with_openai_thread(self, thread_id: str) -> List[dict]:
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
            metadata = await self.save_file(BytesIO(content), file_id, {"purpose": file.purpose})
            synced_files.append(metadata)

        return synced_files

    async def sync_with_openai_assistant(self, assistant_id: str) -> List[dict]:
        client = get_openai_client()
        assistant = await client.beta.assistants.retrieve(assistant_id)
        
        synced_files = []
        for file_id in assistant.file_ids:
            file = await client.files.retrieve(file_id)
            content_response = await client.files.content(file_id)
            content = await content_response.aread()
            metadata = await self.save_file(BytesIO(content), file_id, {"purpose": file.purpose})
            synced_files.append(metadata)
        
        return synced_files

    async def upload_to_openai(self, file_id: Union[str, UUID], purpose: str) -> dict:
        client = get_openai_client()
        file_content = await self.get_file(file_id)
        file_metadata = await self.get_file_metadata(file_id)

        response = await client.files.create(
            file=file_content,
            purpose=purpose
        )

        # Update local metadata with OpenAI file ID
        file_metadata["openai_file_id"] = response.id
        await self.save_file(file_content, file_id, file_metadata)

        return response.model_dump()

    async def download_file(self, url: str, file_id: Union[str, UUID]) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content = await response.read()
                    return await self.save_file(BytesIO(content), file_id, {"url": url})
                else:
                    raise Exception(f"Failed to download file from {url}")

    async def request_presigned_url(self, file_id: str, private: bool = True) -> dict:
        # This is a mock implementation
        return {
            "id": file_id,
            "upload_url": f"https://example.com/upload/{file_id}",
        }
from datetime import datetime
from typing import Literal
from uuid import UUID
import uuid

from marvin.extensions.types.base import BaseModelConfig
from pydantic import BaseModel, Field

class IndexData(BaseModel):
    mime_type: str | None = None
    base64_string: str | None = None
    prompt: str | None = None

    class Config(BaseModelConfig):
        pass


class DataSource(BaseModel):
    id: str | UUID | None = None
    name: str | None = None
    file_name: str | None = None
    file_id: str | UUID | None = Field(
        description="File ID from request. If not provided, a new UUID will be generated.",
        default_factory=uuid.uuid4,
    )
    file_type: str | None = None
    file_size: int | None = None
    upload_url: str | None = None
    upload_type: str | None = Field(
        description="source of the document, upload, url image generation etc.",
        default=None,
    )
    description: str | None = None
    chunks_length: int | None = None
    chunks_strategy: Literal["default", "high_density", "low_density"] | None = Field(
        description="Strategy for chunking the document",
        default="default",
    )
    temporary: bool | None = None
    created: datetime | str | None = None
    modified: datetime | str | None = None
    index: IndexData | None = None
    file_upload_type: Literal["file", "image", "url", ""] | None = None
    url: str | None = None
    status: Literal["loaded", "indexing", "indexed", "failed", ""] | None = "loaded"
    reference_file_id: str | UUID | None = Field(
        description="Reference file ID. Use this to generate presigned upload URLs.",
        default=None,
    )
    class Config(BaseModelConfig):
        pass

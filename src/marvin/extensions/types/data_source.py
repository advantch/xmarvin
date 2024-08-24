from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from marvin.extensions.types.base import BaseSchemaConfig, CustomUrl
from pydantic import BaseModel, Field


class GithubOptionsSchema(BaseModel):
    issues: bool | None = False
    branch: str | None = "main"
    token: str | None = None


class DocumentFromURLSchema(BaseModel):
    name: str | None = None
    url: CustomUrl | None = None
    urls: list[dict[str, CustomUrl]] | None = None
    description: str | None = None
    url_option: str | None = "single"
    max_pages: int | None = 20
    max_depth: int | None = 3
    save_html: bool | None = False
    save_screenshots: bool | None = True
    tags: list[str] | None = None
    source: str = "url"
    index_name: str = "index_default"
    number_of_times_indexed: int = 0
    reindex: bool = False
    github_options: GithubOptionsSchema | None = GithubOptionsSchema()

    class Config(BaseSchemaConfig):
        pass

    def get_urls(self):
        if self.urls:
            return self.urls
        return [self.url]


class IndexData(BaseModel):
    mime_type: str | None = None
    base64_string: str | None = None
    prompt: str | None = None

    class Config(BaseSchemaConfig):
        pass

class DeleteDataSourcesSchema(BaseModel):
    ids: list[str]

class DataSourceSchema(BaseModel):
    id: str | UUID | None = None
    name: str | None = None
    file_name: str | None = None
    file_id: str | UUID | None = None
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
    data_source_urls: Optional[DocumentFromURLSchema] | None = None
    reference_file_id: str | UUID | None = Field(
        description="File ID from request if relevant, not persistent. Only returned in upload endpoints",
        default=None,
    )

    class Config(BaseSchemaConfig):
        pass

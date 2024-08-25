import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .base import BaseModelConfig


class DocumentMetadata(BaseModel):
    source: str | None = None
    relationships: dict = Field(default_factory=dict)
    tenant_id: str | None = None
    document_id: str | None = None
    title: str | None = None

    class Config(BaseModelConfig):
        extra = "allow"


class Document(BaseModel):
    id: str | uuid.UUID | None = Field(default_factory=lambda: str(uuid.uuid4()))
    page_content: str
    """String text."""
    metadata: dict | DocumentMetadata = Field(default_factory=dict)
    """Arbitrary metadata about the page content (e.g., source, relationships to other
        documents, etc.).
    """
    created: datetime | None = None
    highlighted: str | None = None
    score: float | None = 0.0
    type: Literal["Document"] = "Document"
    empty: bool | None = False
    embeddings: list[float] | None = None
    search_type: Literal["kw", "vector"] = "vector"

    class Config(BaseModelConfig):
        pass

    @staticmethod
    def llm_text_result(instance):
        return f"""
         #Document ID: {instance.id}
         #Page Content: {instance.page_content}
        """

    @staticmethod
    def llm_text_from_list(results):
        return "\n".join([Document.llm_text_result(i) for i in results])

    @classmethod
    def get_vectorizable_docs(cls, documents: list["Document"] | str):
        """
        Vectorizable the chunks of the documents.
        """
        from langchain_text_splitters import (
            RecursiveCharacterTextSplitter,
        )

        if isinstance(documents, str):
            documents = [Document(page_content=documents)]

        texts = [d.page_content for d in documents]
        metadata = [d.metadata for d in documents]
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=400)
        return splitter.create_documents(texts, metadata)

    @classmethod
    def get_embeddings(cls, documents):
        """
        Embed the chunks of the documents.
        """
        from marvin.extensions.embeddings.openai import OpenAIEmbeddings

        embedder = OpenAIEmbeddings()
        embeddings = embedder.embed_documents(documents)
        for idx, document in enumerate(documents):
            document.embeddings = embeddings[idx]

        return documents

    def to_cohere_format(self):
        title = getattr(self.metadata, "title", self.page_content[:100])
        return {
            "title": title,
            "snippet": self.page_content,
        }

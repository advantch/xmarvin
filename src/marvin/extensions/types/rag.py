from typing import List

from pydantic import BaseModel, Field


class Citation(BaseModel):
    start: int = Field(
        description="The starting character index of the citation in the main text",
        default=0,
    )
    end: int = Field(
        description="The ending character index of the citation in the main text",
        default=0,
    )
    text: str = Field(description="The text content of the citation", default="")
    document_ids: List[str] = Field(
        description="The IDs of the documents the citation refers to",
        default_factory=list,
    )


class RagDocument(BaseModel):
    id: str | None = Field(
        description="The unique identifier of the document", default=None
    )
    snippet: str | None = Field(
        description="A snippet or excerpt from the document", default=None
    )
    title: str | None = Field(description="The title of the document", default=None)
    rag_id: str | None = Field(description="The RAG ID of the document", default=None)


class TextWithCitations(BaseModel):
    text: str = Field(description="The main text content", default="")
    citations: List[Citation] = Field(
        description="A list of citations within the text", default_factory=list
    )
    documents: List[RagDocument] = Field(
        description="A list of referenced documents", default_factory=list
    )


class SearchQueryText(BaseModel):
    text: str = Field(..., description="The search query text")


class SearchQuery(BaseModel):
    search_queries: List[SearchQueryText] = Field(
        description="The search queries", default_factory=list
    )
    is_search_queries_only: bool = Field(
        description="Whether the search queries are only used for searching",
        default=False,
    )

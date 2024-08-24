import asyncio
import hashlib
from abc import ABC, abstractmethod

import numpy as np
from pydantic import BaseModel


class Embeddings(ABC):
    """Interface for embedding models."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed search docs."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed query text."""

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Asynchronous Embed search docs."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.embed_documents, texts
        )

    async def aembed_query(self, text: str) -> list[float]:
        """Asynchronous Embed query text."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.embed_query, text
        )


class FakeEmbeddings(Embeddings, BaseModel):
    """Fake embedding model."""

    size: int
    """The size of the embedding vector."""

    def _get_embedding(self) -> list[float]:
        return list(np.random.normal(size=self.size))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._get_embedding() for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._get_embedding()


class DeterministicFakeEmbedding(Embeddings, BaseModel):
    """
    Fake embedding model that always returns
    the same embedding vector for the same text.
    """

    size: int
    """The size of the embedding vector."""

    def _get_embedding(self, seed: int) -> list[float]:
        # set the seed for the random generator
        np.random.seed(seed)
        return list(np.random.normal(size=self.size))

    def _get_seed(self, text: str) -> int:
        """
        Get a seed for the random generator, using the hash of the text.
        """
        return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % 10**8

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._get_embedding(seed=self._get_seed(_)) for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._get_embedding(seed=self._get_seed(text))

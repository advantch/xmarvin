import asyncio
import hashlib
import random
from abc import ABC, abstractmethod
from typing import List

import numpy as np
from pydantic import BaseModel


class Embeddings(ABC):
    """Interface for embedding models."""

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous Embed search docs."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.embed_documents, texts
        )

    async def aembed_query(self, text: str) -> List[float]:
        """Asynchronous Embed query text."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.embed_query, text
        )


class FakeEmbeddings(Embeddings, BaseModel):
    """Fake embedding model."""

    size: int
    """The size of the embedding vector."""

    def _get_embedding(self) -> List[float]:
        seed = random.randint(0, 10**8)
        return list(np.random.default_rng(seed=seed).normal(size=self.size))

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._get_embedding() for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._get_embedding()


class DeterministicFakeEmbedding(Embeddings, BaseModel):
    """
    Fake embedding model that always returns
    the same embedding vector for the same text.
    """

    size: int = 10
    """The size of the embedding vector."""

    def _get_embedding(self) -> List[float]:
        # set the seed for the random generator
        seed = random.randint(0, 10**8)
        return list(np.random.default_rng(seed=seed).normal(size=self.size))

    def _get_seed(self, text: str) -> int:
        """
        Get a seed for the random generator, using the hash of the text.
        """
        return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % 10**8

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._get_embedding() for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._get_embedding()

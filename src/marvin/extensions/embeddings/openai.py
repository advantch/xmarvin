import asyncio
import concurrent
from concurrent.futures import ThreadPoolExecutor
from typing import List

from marvin.extensions.embeddings.base import Embeddings
from marvin.extensions.utilities.logging import logger
from marvin.extensions.settings import extension_settings
from marvin.settings import settings
from openai import OpenAI


def get_client(api_key=None):
    api_key = api_key or settings.openai.api_key
    return OpenAI(api_key=api_key)


openai_embeddings_client = get_client()


def get_embeddings(
    text,
    model="text-embedding-3-small",
    dimensions=None,
    api_key=None,
    use_default_client=True,
) -> List[float]:
    """
    Get embeddings from OpenAI.
    @param text: The text to embed.
    @param model: The model to use.
    @param dimensions: The dimensions of the embeddings.
    @param api_key: The API key to use.
    @param use_default_client: Whether to use the default client.
    @return: List[float] The embeddings.
    """
    if dimensions is None:
        dimensions = extension_settings.default_vector_dimensions
    if not use_default_client:
        client = get_client(api_key)
    else:
        client = openai_embeddings_client
    response = client.embeddings.create(input=text, model=model, dimensions=dimensions)
    return response.data[0].embedding


class OpenAIEmbeddings(Embeddings):
    def __init__(self, num_threads=50):
        self.num_threads = num_threads

    def embed_documents_legacy(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""
        return [get_embeddings(text) for text in texts]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs using a thread pool."""

        logger.info(
            f"Embedding {len(texts)} documents using {self.num_threads} threads"
        )
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            # Submit all tasks to the thread pool
            future_to_text = {
                executor.submit(get_embeddings, text): text for text in texts
            }

            results = []
            for future in concurrent.futures.as_completed(future_to_text):
                result = future.result()
                results.append(result)
            return results

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return get_embeddings(text)

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

import asyncio
import concurrent
from concurrent.futures import ThreadPoolExecutor

from marvin.extensions.embeddings.base import Embeddings
from marvin.extensions.monitoring import logger
from marvin.extensions.settings import extensions_settings
from marvin.settings import settings
from openai import OpenAI


def get_embeddings(text, model="text-embedding-3-small", dimensions=None):
    if dimensions is None:
        dimensions = extensions_settings.default_vector_dimensions
    client = OpenAI(api_key=settings.openai.api_key)

    response = client.embeddings.create(input=text, model=model, dimensions=dimensions)
    return response.data[0].embedding


class OpenAIEmbeddings(Embeddings):
    def __init__(self, num_threads=50):
        self.num_threads = num_threads

    def embed_documents_legacy(self, texts: list[str]) -> list[list[float]]:
        """Embed search docs."""
        return [get_embeddings(text) for text in texts]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed search docs using a thread pool."""

        logger.info(
            f"Embedding {len(texts)} documents using {self.num_threads} threads"
        )
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            # Submit all tasks to the thread pool
            future_to_text = {
                executor.submit(get_embeddings, text): text for text in texts
            }

            # Collect the results as they are completed
            results = []
            for future in concurrent.futures.as_completed(future_to_text):
                result = future.result()
                results.append(result)
            return results

    def embed_query(self, text: str) -> list[float]:
        """Embed query text."""
        return get_embeddings(text)

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

import asyncio
import concurrent
from concurrent.futures import ThreadPoolExecutor

from .base import Embeddings

clip_model = None
text_model = None

def get_embeddings(documents: list[str]):
    embedding = _get_text_model()
    text_generator = embedding.embed(documents)
    return list(text_generator)


def _get_clip_model():
    from fastembed import ImageEmbedding  # noqa
    clip_model = ImageEmbedding("Qdrant/resnet50-onnx")
    return clip_model


def _get_text_model():
    from fastembed import TextEmbedding  # noqa

    text_model = TextEmbedding()
    return text_model


def get_image_embedding(image: list[str]):
    model = clip_model or _get_clip_model()
    embeddings_generator = model.embed(image)
    return list(embeddings_generator)


class FastEmbedEmbeddings(Embeddings):
    def __init__(self, num_threads=50):
        self.num_threads = num_threads

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed search docs using a thread pool."""
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

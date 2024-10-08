import uuid
from typing import Dict

from pydantic import Field

import marvin
from marvin.extensions.memory.agent_memory.memory import MemoryProvider

try:
    import chromadb
except ImportError:
    chromadb = None


class ChromaMemory(MemoryProvider):
    model_config = dict(arbitrary_types_allowed=True)
    client: chromadb.ClientAPI = Field(
        default_factory=lambda: chromadb.PersistentClient(
            path=str(
                marvin.extensions.settings.extension_settings.home_path
                / "memory"
                / "chroma"
            )
        )
    )
    collection_name: str = Field(
        "memory-{key}",
        description="""
            Optional; the name of the collection to use. This should be a 
            string optionally formatted with the variable `key`, which 
            will be provided by the memory module. The default is `"memory-{{key}}"`.
            """,
    )

    def get_collection(self, memory_key: str) -> chromadb.Collection:
        return self.client.get_or_create_collection(
            self.collection_name.format(key=memory_key)
        )

    def add(self, memory_key: str, content: str) -> str:
        collection = self.get_collection(memory_key)
        memory_id = str(uuid.uuid4())
        collection.add(
            documents=[content], metadatas=[{"id": memory_id}], ids=[memory_id]
        )
        return memory_id

    def delete(self, memory_key: str, memory_id: str) -> None:
        collection = self.get_collection(memory_key)
        collection.delete(ids=[memory_id])

    def search(self, memory_key: str, query: str, n: int = 20) -> Dict[str, str]:
        results = self.get_collection(memory_key).query(
            query_texts=[query], n_results=n
        )
        return dict(zip(results["ids"][0], results["documents"][0]))


def ChromaEphemeralMemory(**kwargs) -> ChromaMemory:
    return ChromaMemory(client=chromadb.EphemeralClient(**kwargs))


def ChromaPersistentMemory(path: str = None, **kwargs) -> ChromaMemory:
    return ChromaMemory(
        client=chromadb.PersistentClient(
            path=path
            or str(
                marvin.extensions.settings.extension_settings.home_path
                / "memory"
                / "chroma"
            ),
            **kwargs,
        )
    )

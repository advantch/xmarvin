from qdrant_client import QdrantClient


def get_client():
    qclient = QdrantClient(
        url="https://6ec6116b-4002-4a09-99a0-5ad7ca28aefe.us-east4-0.gcp.cloud.qdrant.io:6333",
        api_key="nqY5JSmuHNEsAQZ6KuSwJRbPOndT7l1JngVolF_M55blMhVS7nF2iA",
    )
    return qclient


def create_collection():
    client = get_client()
    client.create_collection(
        collection_name="test_collection",
        vectors_config=client.get_fastembed_vector_params(),
        sparse_vectors_config=client.get_fastembed_sparse_vector_params(),
    )


class HybridSearcher:
    DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    SPARSE_MODEL = "prithivida/Splade_PP_en_v1"

    def __init__(self, collection_name):
        self.collection_name = collection_name
        # initialize Qdrant client
        self.qdrant_client = get_client()
        self.qdrant_client.set_model(self.DENSE_MODEL)
        # comment this line to use dense vectors only
        self.qdrant_client.set_sparse_model(self.SPARSE_MODEL)

    def search(self, text: str):
        search_result = self.qdrant_client.query(
            collection_name=self.collection_name,
            query_text=text,
            query_filter=None,  # If you don't want any filters for now
            limit=5,  # 5 the closest results
        )
        # `search_result` contains found vector ids with similarity scores
        # along with the stored payload

        # Select and return metadata
        metadata = [hit.metadata for hit in search_result]
        return metadata

import os
import getpass
from uuid import uuid4
from .sparse_encoder import compute_sparse_vector
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient, models
from qdrant_client.http.models import (
    Distance,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
    QueryRequest,
)

DENSE_VECTOR_NAME = "text-dense"
SPARSE_VECTOR_NAME = "text-sparse"

_QDRANT_CACHE = {}

def get_qdrant_client(
    url: str = "https://f028c8c9-ff23-4d61-a751-7dd10e1c066a.us-east-1-1.aws.cloud.qdrant.io", 
    timeout: int = 120
) -> QdrantClient:
    if not os.getenv("QDRANT_API_KEY"):
        os.environ["QDRANT_API_KEY"] = getpass.getpass("Enter your Qdrant API key: ")
    if url not in _QDRANT_CACHE:
        _QDRANT_CACHE[url] = QdrantClient(
        url=url,
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=timeout,
    )
    return _QDRANT_CACHE[url]

def embed_unique_chunks(
    chunks: list[Document],
    collection_name: str,
    similarity_threshold: float = 0.95,
    model_id = "naver/splade-cocondenser-ensembledistil"
) -> tuple[QdrantClient, OpenAIEmbeddings]:
    if not chunks:
        raise ValueError("No documents provided to embed.")
    client = get_qdrant_client()
    print("Qdrant client opened!")
    vector_size = 1536
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                    on_disk=True,
                )
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: SparseVectorParams(
                    index=SparseIndexParams(on_disk=True)
                )
            },
        )
    points = []
    chunk_quantity = len(chunks)
    print(f"Embedding {chunk_quantity} dense vectors: ")
    texts = [chunk.page_content for chunk in chunks]
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    dense_vectors = embeddings.embed_documents(texts)
    unique_dense_vectors: list[list[float] | None] = [None] * chunk_quantity
    # Dedupe search using dense vector only.
    # This avoids needing LangChain's QdrantVectorStore for ingestion.
    existing = client.query_batch_points(
            collection_name=collection_name,
            requests=[QueryRequest(
                query=dense_vector,
                using=DENSE_VECTOR_NAME,
                limit=1,
                with_payload=False,
            ) for dense_vector in dense_vectors]
        )
    for i, response in enumerate(existing):
        if response.points:
            if response.points[0].score < similarity_threshold:
                unique_dense_vectors[i] = dense_vectors[i]
    
    print(f"Creating {len(chunks)} points:")
    for chunk, dense_vector in zip(chunks, unique_dense_vectors):
        if dense_vector is not None:
            sparse_vector = compute_sparse_vector(chunk.page_content, model_id)
            points.append(models.PointStruct(
                id=uuid4(),
                vector={
                    DENSE_VECTOR_NAME: dense_vector,
                    SPARSE_VECTOR_NAME: sparse_vector,
                },
                payload={
                    "page_content": chunk.page_content,
                    "metadata": chunk.metadata,
                    "chunk_id": chunk.id,
                },
            ))
    print(f"Upserting {len(points)} points:")
    if points:
        client.upsert(
            collection_name=collection_name,
            points=points,
            wait=False,
        )
    return (client, embeddings)
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
)

DENSE_VECTOR_NAME = "text-dense"
SPARSE_VECTOR_NAME = "text-sparse"

def embed_unique_chunks(
    chunks: list[Document],
    collection_name: str = "github_docs",
    similarity_threshold: float = 0.95,
    model_id = "naver/splade-cocondenser-ensembledistil"
) -> tuple[QdrantClient, OpenAIEmbeddings]:
    if not chunks:
        raise ValueError("No documents provided to embed.")
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")
    if not os.getenv("QDRANT_API_KEY"):
        os.environ["QDRANT_API_KEY"] = getpass.getpass("Enter your Qdrant API key: ")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    client = QdrantClient(
        url="https://f028c8c9-ff23-4d61-a751-7dd10e1c066a.us-east-1-1.aws.cloud.qdrant.io",
        api_key=os.getenv("QDRANT_API_KEY"),
        timeout=120,
    )
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
    for chunk in chunks:
        # TODO use deterministic chunk IDs:
        chunk_id = getattr(chunk, "id", None) or str(uuid4())
        dense_vector = embeddings.embed_query(chunk.page_content)
        sparse_vector = compute_sparse_vector(chunk.page_content, model_id)
        # Dedupe search using dense vector only.
        # This avoids needing LangChain's QdrantVectorStore for ingestion.
        # TODO: Check if it's more effecient to use the sparse vector for this
        existing = client.query_points(
            collection_name=collection_name,
            query=dense_vector,
            using=DENSE_VECTOR_NAME,
            limit=1,
            with_payload=True,
        )
        if existing.points:
            best = existing.points[0]
            similarity = best.score
            if similarity >= similarity_threshold:
                continue
        points.append(models.PointStruct(
            id=chunk_id,
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
    client.upsert(
        collection_name=collection_name,
        points=points,
        wait=True,
    )
    return (client, embeddings)
from qdrant_client.models import Prefetch, RrfQuery, Rrf
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
from qdrant_client.http.models import QueryResponse
from document_ingestion.sparse_encoder import compute_sparse_vector

def hybrid_retriever_query(
    client: QdrantClient,
    dense_embedding: OpenAIEmbeddings,
    query: str, 
    collection_name: str = "github_docs", 
    top_k: int = 20,
    prefetch_k: int = 20,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
    rrf_k: int = 60,
    model_id = "naver/splade-cocondenser-ensembledistil"
) -> QueryResponse:
    query_sparse_vector = compute_sparse_vector(query, model_id)
    query_dense_vector = dense_embedding.embed_query(query)

    return client.query_points(
        collection_name=collection_name,
        prefetch=[
            Prefetch(
                query=query_dense_vector,
                using="text-dense",
                limit=prefetch_k,
            ),
            Prefetch(
                query=query_sparse_vector,
                using="text-sparse",
                limit=prefetch_k,
            ),
        ],
        query=RrfQuery(
            rrf=Rrf(k=rrf_k, weights=[dense_weight, sparse_weight])
        ),
        limit=top_k,
        with_payload=True,
    )

    
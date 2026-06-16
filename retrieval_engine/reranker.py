from langchain_core.documents import Document
from qdrant_client.http.models import QueryResponse
from sentence_transformers import CrossEncoder
from sentence_transformers.base.modality_types import PairInput
import torch


def rerank_results(
    query: str,
    retrieved_results: QueryResponse,
    top_k: int = 5,
) -> list[Document]:
    if not torch.cuda.is_available():
        print("Warning: No GPU found. Please add GPU to your notebook")

    cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L6-v2")
    cross_inputs: list[PairInput] = []
    candidate_docs: list[Document] = []
    for point in retrieved_results.points:
        if not point.payload:
            continue
        page_content = point.payload.get("page_content")
        if not page_content:
            continue
        metadata = point.payload.get("metadata", {}).copy()
        # Preserve useful retrieval metadata for citations/debugging.
        metadata["point_id"] = str(point.id)
        metadata["retrieval_score"] = point.score
        # Qdrant payload currently stores page_content + metadata.
        # If you later store chunk_id in payload, this preserves it.
        if point.payload.get("chunk_id") is not None:
            metadata["chunk_id"] = point.payload["chunk_id"]
        doc = Document(
            page_content=page_content,
            metadata=metadata,
        )
        candidate_docs.append(doc)
        cross_inputs.append([query, page_content])
    if not candidate_docs:
        return []
    cross_scores = cross_encoder.predict(cross_inputs)
    for doc, score in zip(candidate_docs, cross_scores):
        doc.metadata["cross_score"] = float(score)
    ranked_docs = sorted(
        candidate_docs,
        key=lambda doc: doc.metadata["cross_score"],
        reverse=True,
    )
    return ranked_docs[:top_k]
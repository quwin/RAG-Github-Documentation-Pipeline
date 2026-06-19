from fastapi import HTTPException
from .dependencies import get_qdrant_client
from .schemas import DocumentSummary


def list_indexed_documents(
    collection_name: str,
    limit: int = 1000,
    include_chunk_ids: bool = False,
) -> dict:
    client = get_qdrant_client()

    if not client.collection_exists(collection_name):
        raise HTTPException(
            status_code=404,
            detail=f"Collection '{collection_name}' does not exist.",
        )

    documents: dict[str, dict] = {}
    next_offset = None
    total_chunks = 0

    while True:
        points, next_offset = client.scroll(
            collection_name=collection_name,
            limit=limit,
            offset=next_offset,
            with_payload=True,
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}
            metadata = payload.get("metadata") or {}

            source_path = metadata.get("source_path")
            if not source_path:
                source_path = "unknown"

            page_content = payload.get("page_content") or ""
            chunk_id = payload.get("chunk_id") or str(point.id)

            if source_path not in documents:
                documents[source_path] = {
                    "source_path": source_path,
                    "repo_url": metadata.get("repo_url"),
                    "repo_name": metadata.get("repo_name"),
                    "file_type": metadata.get("file_type"),
                    "char_count": metadata.get("char_count"),
                    "section_headings": metadata.get("section_headings") or [],
                    "chunk_count": 0,
                    "chunk_ids": [],
                    "text_preview": page_content[:300] if page_content else None,
                }

            documents[source_path]["chunk_count"] += 1
            total_chunks += 1

            if include_chunk_ids:
                documents[source_path]["chunk_ids"].append(chunk_id)

        if next_offset is None:
            break

    summaries = [
        DocumentSummary(**document)
        for document in sorted(
            documents.values(),
            key=lambda item: item["source_path"],
        )
    ]

    return {
        "collection_name": collection_name,
        "document_count": len(summaries),
        "total_chunks": total_chunks,
        "documents": summaries,
    }
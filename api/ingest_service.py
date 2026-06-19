from document_ingestion.reader import get_head_branch, load_documents_from_repo
from document_ingestion.chunker import header_chunk_documents
from document_ingestion.embedder import embed_unique_chunks
from .dependencies import get_embeddings

def ingest_repo(
    repo_url: str,
    recursive_chunking: bool = False,
    erase_prior_embeddings: bool = False,
    branch: str | None = None,
) -> dict:
    resolved_branch = branch or get_head_branch(repo_url)
    docs, collection_name = load_documents_from_repo(
        repo_url=repo_url,
        data_dir="data",
        branch=resolved_branch,
    )
    chunks = header_chunk_documents(docs, recursive=recursive_chunking)
    embed_unique_chunks(chunks=chunks,collection_name=collection_name, embeddings=get_embeddings(), erase_prior_embeddings=erase_prior_embeddings)

    return {
        "repo_url": repo_url,
        "branch": resolved_branch,
        "documents_loaded": len(docs),
        "chunks_created": len(chunks),
        "collection_name": collection_name,
        "status": "indexed",
    }
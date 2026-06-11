from __future__ import annotations
import getpass
import os
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document
from chunker import stable_chunk_id
from langchain_chroma import Chroma

def embed_unique_chunks(
    chunks: list[Document],
    collection_name: str = "github_docs",
    persist_dir: str = "./chroma_langchain_db",
    similarity_threshold: float = 0.95,
) -> list[Document]:
    if not chunks:
        raise ValueError("No documents provided to embed.")
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("CHROMA_OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter your OpenAI API key: ")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector_store = Chroma(
        collection_name=collection_name,
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    unique_chunks = []
    skipped = []
    for chunk in chunks:
        matches = vector_store.similarity_search_with_score(
            chunk.page_content,
            k=1,
        )
        if matches:
            matched_doc, distance = matches[0]

            similarity = 1 - distance

            if similarity >= similarity_threshold:
                skipped.append(
                    {
                        "reason": "near_duplicate",
                        "chunk_id": getattr(chunk, "id", None),
                        "matched_source": matched_doc.metadata.get("source_path"),
                        "similarity": similarity,
                    }
                )
                continue
        unique_chunks.append(chunk)
        vector_store.add_documents(
            documents=[chunk],
            ids=[chunk.id],
            metadatas=[chunk.metadata]
        )
    print(f"Skipped {skipped.count} chunks:\n{skipped}")
    return unique_chunks
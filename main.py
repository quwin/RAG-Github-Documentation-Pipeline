from document_ingestion import chunker, embedder, reader
from generation import llm
from retrieval_engine import hybrid_retriever, reranker

def main():
    example_repo = "https://github.com/fastapi/fastapi"
    head_branch = reader.get_head_branch(example_repo)
    print(f"Head branch: {head_branch}")
    docs = reader.load_documents_from_repo(example_repo ,data_dir="data", branch=head_branch)
    print(f"Loaded {len(docs)} documentation files")
    for doc in docs[:5]:
        print(doc.metadata.get("source_path"), doc.metadata["char_count"])
    chunks = chunker.header_chunk_documents(docs=docs, recursive=True)
    collection_name = "fast_api_docs"
    qdrant_client, open_ai_embedder = embedder.embed_unique_chunks(chunks=chunks, collection_name=collection_name)
    query = input("Enter query: ")
    hybrid_response = hybrid_retriever.hybrid_retriever_query(qdrant_client, open_ai_embedder, query, collection_name)
    reranked_texts = reranker.rerank_results(query=query, retrieved_results=hybrid_response)
    claude_response = llm.answer_with_claude_sonnet(query=query, chunks = reranked_texts)
    print(claude_response.content)

main()
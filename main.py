from document_ingestion import chunker, embedder, reader
from generation import llm
from retrieval_engine import hybrid_retriever, reranker
from evaluation import evaluate_citations
import json

def main():
    example_repo = "https://github.com/fastapi/fastapi"
    docs, collection_name = reader.load_documents_from_repo(example_repo ,data_dir="data")
    print(f"Loaded {len(docs)} documents")
    chunks = chunker.header_chunk_documents(docs=docs, recursive=True)[:67]
    qdrant_client, open_ai_embedder = embedder.embed_unique_chunks(chunks=chunks, collection_name=collection_name)
    query = input("Enter query: ")
    hybrid_response = hybrid_retriever.hybrid_retriever_query(qdrant_client, open_ai_embedder, query, collection_name)
    reranked_texts = reranker.rerank_results(query=query, retrieved_results=hybrid_response)
    claude_response = llm.answer_with_claude_sonnet(query=query, chunks = reranked_texts)
    print(json.dumps(claude_response.content, indent=2, default=str))
    evaluated_response = evaluate_citations.evaluate_response(response=claude_response, original_query=query)
    print(evaluated_response)

main()
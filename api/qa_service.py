from langchain_core.messages.ai import AIMessage
from .schemas import SourceChunk
from .dependencies import get_qdrant_client, get_embeddings
from retrieval_engine.hybrid_retriever import hybrid_retriever_query
from retrieval_engine.reranker import rerank_results
from generation.llm import answer_with_claude_sonnet
from evaluation.evaluate_citations import evaluate_response

def _message_to_text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)
    return str(content)

def _source_from_doc(doc) -> SourceChunk:
    metadata = doc.metadata or {}
    return SourceChunk(
        chunk_id=metadata.get("chunk_id") or metadata.get("point_id"),
        source_path=metadata.get("source_path"),
        repo_url=metadata.get("repo_url"),
        section_heading=metadata.get("section_heading"),
        retrieval_score=metadata.get("retrieval_score"),
        cross_score=metadata.get("cross_score"),
        text_preview=doc.page_content[:500],
    )

def answer_question(
    question: str,
    collection_name: str,
    top_k: int = 20,
    rerank_top_k: int = 5,
    dense_weight: float = 1.0,
    sparse_weight: float = 1.0,
) -> dict:
    client = get_qdrant_client()
    embeddings = get_embeddings()

    retrieved = hybrid_retriever_query(
        client=client,
        dense_embedding=embeddings,
        query=question,
        collection_name=collection_name,
        top_k=top_k,
        dense_weight=dense_weight,
        sparse_weight=sparse_weight,
    )

    reranked_docs = rerank_results(
        query=question,
        retrieved_results=retrieved,
        top_k=rerank_top_k,
    )

    if not reranked_docs:
        return {
            "question": question,
            "answer": "The provided context does not contain enough information to answer that question.",
            "sources": [],
            "confidence": None,
        }

    answer_message = answer_with_claude_sonnet(
        query=question,
        chunks=reranked_docs,
    )

    evaluation = evaluate_response(
        response=answer_message,
        original_query=question,
    )
    return {
        "question": question,
        "answer": _message_to_text(answer_message),
        "sources": [_source_from_doc(doc) for doc in reranked_docs],
        "confidence": {
            "valid_citations": evaluation.valid_citations,
            "invalid_citations": evaluation.invalid_citations,
            "retrieval_confidence": evaluation.retrieval_confidence,
            "answer_completeness": evaluation.answer_completeness,
        },
    }
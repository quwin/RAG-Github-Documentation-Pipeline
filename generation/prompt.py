from langchain_core.documents import Document

def format_to_anthropic_documents(documents: list[Document]) -> list[dict]:
    return [{
        "type": "search_result",
        "content": [{"type": "text", "text": document.page_content}],
        "title": document.metadata.get("source_path", f"Document {i}"),
        "source": document.metadata.get("source_url", "Github repository documentation or code"),
        "citations": {"enabled": True},
    } for i, document in enumerate(documents)]

"""
Build messages for an LLM chat completion call.
The LLM is instructed to answer only from the retrieved context,
and admit when the context is insufficient.
"""
def system_rag_prompt() -> str:
    return """You are a careful documentation assistant for a Retrieval-Augmented Generation system.
    
        You must answer the user's question using only the provided context blocks.

        Rules:
        1. Use only facts that are explicitly supported by the search results.
        2. Cite every factual claim with one or more references.
        3. Do not cite a search result unless that result directly supports the claim.
        4. If the context does not contain enough information to answer, say so clearly.
        5. Do not use outside knowledge.
        6. Do not guess, infer unsupported details, or fill gaps from general knowledge.
        7. If the answer is partially supported, answer the supported part and explain what is missing.
        8. Output direct quotes when reasonable, but include enough detail to be useful.

        When context is insufficient, respond exactly:
        "The provided context does not contain enough information to answer that question."

        You may also add:
        "The context does mention: ..."
    """

def build_cited_message(query: str, chunks: list[Document]) -> list[dict]:
    content = [{"type": "text", "text": system_rag_prompt()}]
    content.extend(format_to_anthropic_documents(chunks))
    content.append({"type": "text", "text": query})
    return [{
        "role": "user",
        "content": content,
    }]
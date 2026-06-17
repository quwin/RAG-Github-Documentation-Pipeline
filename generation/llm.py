from langchain_core.documents import Document
from langchain_core.messages.ai import AIMessage
from .prompt import build_cited_message
from api.dependencies import get_llm_model

def answer_with_claude_sonnet(
    query: str,
    chunks: list[Document],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1000,
    temperature: float = 0.2,
) -> AIMessage:
    client = get_llm_model(model, max_tokens, temperature)
    response = client.invoke(build_cited_message(query=query, chunks=chunks))
    return response
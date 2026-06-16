from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from langchain_core.messages.ai import AIMessage
from .prompt import build_cited_message
import os
import getpass

_LLM_CACHE = {}

def get_llm_model(model: str, max_tokens, temperature) -> ChatAnthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API key: ")
    if model not in _LLM_CACHE:
        _LLM_CACHE[model] = ChatAnthropic(
            model_name=model, 
            timeout=120, 
            stop=None,
            max_tokens_to_sample=max_tokens,
            temperature=temperature,
            
        )
    return _LLM_CACHE[model]

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
from langchain_anthropic import ChatAnthropic
from langchain_core.messages.ai import AIMessage
from pydantic import BaseModel, Field
from .evaluation_prompt import build_eval_message
import os
import getpass

_LLM_CACHE = {}

"""The overall + in-text citations of a response."""
class ResponseVerification(BaseModel):
    valid_citations: list[int] = Field(description="The indexes of valid citations")
    invalid_citations: list[int] = Field(description="The indexes of invalid citations")
    retrieval_confidence: float = Field(description="The overall relevance of the retrieved search results to the original question")
    answer_completeness: float = Field(description="The score of the response's coverage in answering the original question")

def get_llm_model(model: str, max_tokens: int, temperature:float):
    if not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = getpass.getpass("Enter your Anthropic API key: ")
    if model not in _LLM_CACHE:
        _LLM_CACHE[model] = ChatAnthropic(
            model_name=model, 
            timeout=120, 
            stop=None, 
            temperature=temperature, 
            max_tokens_to_sample=max_tokens,
        ).with_structured_output(ResponseVerification, method="json_schema")
    return _LLM_CACHE[model]

def evaluate_response(
    response: AIMessage,
    original_query: str,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 1000,
    temperature: float = 0.2,
):
    client = get_llm_model(model, max_tokens, temperature)
    response = client.invoke(build_eval_message(query=original_query, response_content=getattr(response, "content", [])))
    return response
from langchain_core.messages.ai import AIMessage
from pydantic import BaseModel, Field
from .evaluation_prompt import build_eval_message
from api.dependencies import get_llm_model
from langchain_core.runnables import Runnable
from typing import Any, cast

"""The overall + in-text citations of a response."""
class ResponseVerification(BaseModel):
    valid_citations: list[int] = Field(description="The indexes of valid citations")
    invalid_citations: list[int] = Field(description="The indexes of invalid citations")
    retrieval_confidence: float = Field(description="The overall relevance of the retrieved search results to the original question")
    answer_completeness: float = Field(description="The score of the response's coverage in answering the original question")

def evaluate_response(
    response: AIMessage,
    original_query: str,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 1000,
    temperature: float = 0.2,
) -> ResponseVerification:
    client = cast(
        Runnable[Any, ResponseVerification],
        get_llm_model(model, max_tokens, temperature).with_structured_output(ResponseVerification, method="json_schema")
    )
    evaluated_response = client.invoke(build_eval_message(query=original_query, response_content=getattr(response, "content", [])))
    return evaluated_response
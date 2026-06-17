import os
from functools import lru_cache
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from langchain_anthropic import ChatAnthropic
from transformers import AutoTokenizer, AutoModelForMaskedLM
from sentence_transformers import CrossEncoder

@lru_cache
def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ.get("QDRANT_API_KEY"),
        timeout=120,
    )

@lru_cache
def get_embeddings(model: str = "text-embedding-3-small") -> OpenAIEmbeddings:
    return OpenAIEmbeddings(model=model)

@lru_cache
def get_llm_model(model: str, max_tokens: int, temperature:float):
    return ChatAnthropic(
        model_name=model, 
        timeout=120, 
        stop=None, 
        temperature=temperature, 
        max_tokens_to_sample=max_tokens,
    )

@lru_cache
def get_splade_model(model_id: str):
    return (AutoTokenizer.from_pretrained(model_id), AutoModelForMaskedLM.from_pretrained(model_id))

@lru_cache
def get_cross_encoder(model_id: str = "cross-encoder/ms-marco-MiniLM-L6-v2"):
    return CrossEncoder(model_id)
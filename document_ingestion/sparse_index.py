from __future__ import annotations
import json
import pickle
import re
from pathlib import Path
from typing import Any
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

def index_documents(docs: list[Document]):
    bm25_index = BM25ChunkIndex.from_documents(docs)
    bm25_index.save("./bm25_index")

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_./:-]+")

def tokenize(text: str) -> list[str]:
    """
    Tokenizer tuned for technical docs.
    Keeps useful technical tokens such as:
    - function_name
    - config.key
    - /api/v1/users
    - error-code-123
    """
    return TOKEN_PATTERN.findall(text.lower())

class BM25ChunkIndex:
    def __init__(self, bm25: BM25Okapi, records: list[dict[str, Any]]):
        self.bm25 = bm25
        self.records = records

    @classmethod
    def from_documents(cls, chunks: list[Document]) -> "BM25ChunkIndex":
        if not chunks:
            raise ValueError("No chunks provided for BM25 indexing.")

        records = []
        tokenized_corpus = []

        for i, chunk in enumerate(chunks):
            chunk_id = getattr(chunk, "id", None)
            if not chunk_id:
                raise ValueError(f"Chunk at index {i} is missing an id.")

            text = chunk.page_content
            tokens = tokenize(text)

            records.append(
                {
                    "id": chunk_id,
                    "text": text,
                    "metadata": chunk.metadata,
                }
            )
            tokenized_corpus.append(tokens)

        bm25 = BM25Okapi(tokenized_corpus)
        return cls(bm25=bm25, records=records)

    def search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        query_tokens = tokenize(query)
        scores = self.bm25.get_scores(query_tokens)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:k]

        results = []
        for rank, idx in enumerate(ranked_indices, start=1):
            record = self.records[idx]
            results.append(
                {
                    "id": record["id"],
                    "text": record["text"],
                    "metadata": record["metadata"],
                    "score": float(scores[idx]),
                    "rank": rank,
                    "retriever": "bm25",
                }
            )

        return results

    def save(self, persist_dir: str = "./bm25_index") -> None:
        path = Path(persist_dir)
        path.mkdir(parents=True, exist_ok=True)

        with (path / "bm25.pkl").open("wb") as f:
            pickle.dump(self.bm25, f)

        with (path / "records.json").open("w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, persist_dir: str = "./bm25_index") -> "BM25ChunkIndex":
        path = Path(persist_dir)

        with (path / "bm25.pkl").open("rb") as f:
            bm25 = pickle.load(f)

        with (path / "records.json").open("r", encoding="utf-8") as f:
            records = json.load(f)

        return cls(bm25=bm25, records=records)
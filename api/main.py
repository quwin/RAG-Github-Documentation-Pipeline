from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool

from .schemas import AskRequest, AskResponse, IngestRequest
from .qa_service import answer_question
from .ingest_service import ingest_repo


app = FastAPI(
    title="GitHub Docs RAG API",
    version="1.0.0",
    description="Hybrid-search RAG service over GitHub repository documentation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@app.post("/v1/ingest")
async def ingest(request: IngestRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(
        ingest_repo,
        request.repo_url,
        request.branch,
        request.recursive_chunking,
    )
    return {
        "status": "queued",
        "repo_url": request.repo_url,
    }

@app.post("/v1/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    return await run_in_threadpool(
        answer_question,
        question=request.question,
        collection_name=request.collection_name,
        top_k=request.top_k,
        rerank_top_k=request.rerank_top_k,
        dense_weight=request.dense_weight,
        sparse_weight=request.sparse_weight,
    )

@app.get("/v1/documents")
def list_documents(collection_name: str):
    # Initial placeholder.
    # Implement this by scrolling Qdrant payloads and grouping by source_path.
    return {
        "collection_name": collection_name,
        "documents": [],
    }
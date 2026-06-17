# GitHub Documentation RAG Pipeline

A production-oriented Retrieval-Augmented Generation pipeline for ingesting public GitHub repository documentation, indexing it with hybrid dense and sparse retrieval, and answering user questions with grounded responses, citations, source metadata, and confidence signals.

The system is designed for technical documentation search, where exact terms such as function names, configuration keys, class names, CLI flags, file paths, and error messages matter as much as semantic similarity.

---

## Table of Contents

* [Overview](#overview)
* [Key Features](#key-features)
* [Architecture](#architecture)
* [Tech Stack](#tech-stack)
* [Repository Structure](#repository-structure)
* [How the Pipeline Works](#how-the-pipeline-works)
  * [1. GitHub Repository Ingestion](#1-github-repository-ingestion)
  * [2. Documentation Filtering](#2-documentation-filtering)
  * [3. Chunking](#3-chunking)
  * [4. Dense and Sparse Embedding](#4-dense-and-sparse-embedding)
  * [5. Hybrid Retrieval](#5-hybrid-retrieval)
  * [6. Reranking](#6-reranking)
  * [7. Grounded Generation](#7-grounded-generation)
  * [8. Citation Evaluation](#8-citation-evaluation)
* [API Reference](#api-reference)
  * [GET `/health`](#get-health)
  * [POST `/v1/ingest`](#post-v1ingest)
  * [POST `/v1/ask`](#post-v1ask)
  * [GET `/v1/documents`](#get-v1documents)
* [Request and Response Schemas](#request-and-response-schemas)
* [Local Development](#local-development)
* [Docker Usage](#docker-usage)
* [Environment Variables](#environment-variables)
* [Example Usage](#example-usage)
* [Deployment Notes](#deployment-notes)
* [Current Implementation Status](#current-implementation-status)
* [Roadmap](#roadmap)
* [Troubleshooting](#troubleshooting)

---

## Overview

This project implements a Retrieval-Augmented Generation system for public GitHub repository documentation.

Given a GitHub repository URL, the system:

1. Clones the repository.
2. Extracts documentation-like files.
3. Splits the documents into chunks.
4. Creates dense OpenAI embeddings.
5. Creates sparse SPLADE vectors.
6. Stores both vector types in Qdrant.
7. Retrieves relevant context with hybrid dense+sparse search.
8. Applies Reciprocal Rank Fusion.
9. Reranks candidate chunks with a cross-encoder.
10. Sends the top chunks to Claude.
11. Generates an answer grounded only in retrieved context.
12. Returns citations, source metadata, and evaluation scores.

The goal is to provide reliable question answering over GitHub documentation while reducing hallucinations and preserving traceability back to the original source files.

---

## Key Features

* **GitHub documentation ingestion**

  * Accepts public GitHub repository URLs.
  * Resolves the repository default branch automatically when no branch is supplied.
  * Clones repositories using shallow Git clones.
  * Filters documentation files while excluding build artifacts, images, binaries, and cache directories.

* **Documentation-aware chunking**

  * Supports Markdown-header-based splitting.
  * Supports optional recursive splitting after header splitting.
  * Creates stable chunk IDs from normalized chunk content.

* **Hybrid retrieval**

  * Uses OpenAI dense embeddings for semantic similarity.
  * Uses SPLADE sparse vectors for lexical and keyword-aware retrieval.
  * Stores both dense and sparse vectors in Qdrant.
  * Combines retrieval paths using Reciprocal Rank Fusion.

* **Reranking**

  * Uses a sentence-transformers cross-encoder reranker.
  * Scores candidate chunks against the original question.
  * Keeps only the most relevant chunks before generation.

* **Grounded answer generation**

  * Uses Claude through Anthropic.
  * Instructs the model to answer only from retrieved context.
  * Requires citations for factual claims.
  * Returns an explicit insufficient-context response when the context does not support an answer.

* **Citation and answer evaluation**

  * Evaluates valid and invalid citations.
  * Scores retrieval confidence.
  * Scores answer completeness.
  * Returns structured confidence metadata with each answer.

* **FastAPI service**

  * Provides ingestion and question-answering endpoints.
  * Includes a health check endpoint.
  * Uses request and response schemas with Pydantic.

* **Container-ready**

  * Includes Docker and Docker Compose configuration.
  * Designed for deployment to container platforms such as Cloud Run.

---

## Architecture

```text
                    ┌────────────────────────────┐
                    │      Public GitHub Repo     │
                    └──────────────┬─────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │ Repo Loader / Reader        │
                    │ - validate GitHub URL       │
                    │ - clone repo                │
                    │ - filter documentation      │
                    │ - extract metadata          │
                    └──────────────┬─────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │ Chunking Layer              │
                    │ - Markdown header chunks    │
                    │ - optional recursive split  │
                    │ - stable chunk IDs          │
                    └──────────────┬─────────────┘
                                   │
                                   ▼
              ┌────────────────────────────────────────┐
              │ Embedding and Sparse Encoding           │
              │ - OpenAI dense embeddings               │
              │ - SPLADE sparse vectors                 │
              │ - near-duplicate filtering              │
              └────────────────────┬───────────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │ Qdrant Vector Database      │
                    │ - dense vector: text-dense  │
                    │ - sparse vector: text-sparse│
                    │ - payload metadata          │
                    └──────────────┬─────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │ Hybrid Retriever            │
                    │ - dense prefetch            │
                    │ - sparse prefetch           │
                    │ - RRF fusion                │
                    └──────────────┬─────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │ Cross-Encoder Reranker      │
                    │ - rerank top candidates     │
                    │ - preserve scores           │
                    └──────────────┬─────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │ Claude Generation Layer     │
                    │ - grounded prompt           │
                    │ - citation-enabled context  │
                    └──────────────┬─────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │ Evaluation Layer            │
                    │ - citation verification     │
                    │ - retrieval confidence      │
                    │ - answer completeness       │
                    └──────────────┬─────────────┘
                                   │
                                   ▼
                    ┌────────────────────────────┐
                    │ FastAPI JSON Response       │
                    │ - answer                    │
                    │ - sources                   │
                    │ - confidence scores         │
                    └────────────────────────────┘
```

---

## Tech Stack

| Layer                 | Technology                           |
| --------------------- | ------------------------------------ |
| API                   | FastAPI                              |
| Server                | Uvicorn                              |
| Data validation       | Pydantic                             |
| Dense embeddings      | OpenAI `text-embedding-3-small`      |
| Sparse retrieval      | SPLADE via Hugging Face Transformers |
| Vector database       | Qdrant                               |
| Hybrid retrieval      | Qdrant prefetch + RRF                |
| Reranking             | Sentence Transformers cross-encoder  |
| Generation            | Anthropic Claude                     |
| Prompting / documents | LangChain Core                       |
| Chunking              | LangChain text splitters             |
| Containerization      | Docker                               |

---

## Repository Structure

```text
.
├── api/
│   ├── dependencies.py
│   ├── ingest_service.py
│   ├── main.py
│   ├── qa_service.py
│   └── schemas.py
│
├── document_ingestion/
│   ├── chunker.py
│   ├── embedder.py
│   ├── reader.py
│   └── sparse_encoder.py
│
├── evaluation/
│   ├── evaluate_citations.py
│   └── evaluation_prompt.py
│
├── generation/
│   ├── llm.py
│   └── prompt.py
│
├── retrieval_engine/
│   ├── hybrid_retriever.py
│   └── reranker.py
│
├── data/
│   └── repos/
│
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt
└── README.md
```

### Important Modules

#### `api/main.py`

Defines the FastAPI application and exposes the public API routes:

* `GET /health`
* `POST /v1/ingest`
* `POST /v1/ask`
* `GET /v1/documents`

The ingestion endpoint queues ingestion work as a FastAPI background task. The ask endpoint runs the synchronous RAG pipeline in a threadpool so that the async API handler does not block the event loop.

#### `api/schemas.py`

Defines the request and response contracts:

* `IngestRequest`
* `AskRequest`
* `SourceChunk`
* `ConfidenceScores`
* `AskResponse`

These schemas control the shape of request bodies and JSON responses.

#### `api/ingest_service.py`

Coordinates the ingestion flow:

1. Resolve the branch.
2. Load documentation files from the repository.
3. Chunk the documents.
4. Embed and upsert chunks into Qdrant.

#### `api/qa_service.py`

Coordinates the question-answering flow:

1. Retrieve hybrid search results.
2. Rerank candidate chunks.
3. Generate a grounded Claude answer.
4. Evaluate citations and answer quality.
5. Return answer, sources, and confidence metadata.

#### `document_ingestion/reader.py`

Handles GitHub repository loading:

* Validates GitHub URLs.
* Resolves the repository name.
* Resolves the default branch.
* Clones or refreshes the repository.
* Filters documentation files.
* Extracts file metadata.
* Returns LangChain `Document` objects.

#### `document_ingestion/chunker.py`

Handles document splitting:

* Markdown-header-based splitting.
* Optional recursive splitting.
* Stable chunk ID generation based on normalized chunk content.

#### `document_ingestion/embedder.py`

Handles Qdrant collection creation, dense embedding generation, sparse vector creation, deduplication checks, and point upserts.

#### `document_ingestion/sparse_encoder.py`

Converts text into SPLADE-style sparse vectors for Qdrant sparse vector search.

#### `retrieval_engine/hybrid_retriever.py`

Runs hybrid dense+sparse retrieval using:

* OpenAI dense query embeddings.
* SPLADE sparse query vectors.
* Qdrant prefetch queries.
* Reciprocal Rank Fusion.

#### `retrieval_engine/reranker.py`

Uses a cross-encoder model to rerank retrieved chunks by relevance to the user question.

#### `generation/prompt.py`

Builds Claude-compatible messages using citation-enabled search-result blocks and a strict grounded-answer system prompt.

#### `generation/llm.py`

Invokes Claude with the grounded RAG prompt.

#### `evaluation/evaluate_citations.py`

Uses a structured LLM output schema to score citation validity, retrieval confidence, and answer completeness.

---

## How the Pipeline Works

### 1. GitHub Repository Ingestion

The ingestion process starts with a public GitHub repository URL.

Example:

```json
{
  "repo_url": "https://github.com/quwin/RAG-Github-Documentation-Pipeline",
  "branch": null,
  "recursive_chunking": true
}
```

If no branch is provided, the system resolves the repository’s default branch using Git.

The repository is cloned into:

```text
data/repos/{owner}_{repo}
```

For example:

```text
data/repos/quwin_RAG-Github-Documentation-Pipeline
```

If the repository was already cloned, the local copy is refreshed using `git fetch`, `git reset --hard`, and `git clean`.

---

### 2. Documentation Filtering

The reader filters for documentation-like files.

Supported documentation extensions include:

```text
.md
.mdx
.rst
.txt
.adoc
.ipynb
```

Recognized documentation filenames include:

```text
README
README.md
CHANGELOG
CHANGELOG.md
CONTRIBUTING
CONTRIBUTING.md
LICENSE
LICENSE.md
```

The loader excludes common irrelevant directories and files, including:

```text
.git
node_modules
dist
build
.next
.venv
venv
__pycache__
.pytest_cache
.mypy_cache
```

It also excludes binary or media formats such as:

```text
.png
.jpg
.jpeg
.gif
.svg
.webp
.pdf
.zip
.tar
.gz
.mp4
.mov
.exe
.dll
.so
```

Each loaded document includes metadata such as:

```json
{
  "repo_url": "https://github.com/owner/repo",
  "repo_name": "owner_repo",
  "source_path": "docs/example.md",
  "file_type": ".md",
  "section_headings": ["Introduction", "Usage", "Configuration"],
  "char_count": 12345
}
```

---

### 3. Chunking

The current implementation uses Markdown-header-based chunking.

The splitter recognizes:

```text
# Header 1
## Header 2
### Header 3
```

When `recursive_chunking` is enabled, chunks created from Markdown sections are further split recursively using configurable chunk size and overlap.

Default recursive settings:

```text
chunk_size = 1024
chunk_overlap = 200
```

Each chunk receives a deterministic chunk ID generated from a SHA-256 hash of normalized chunk content. This helps avoid creating duplicate logical chunks when re-indexing identical text.

---

### 4. Dense and Sparse Embedding

For every chunk, the system creates two vector representations.

#### Dense vector

Dense embeddings are generated with:

```text
OpenAI text-embedding-3-small
```

The implementation expects a dense vector size of:

```text
1536
```

The dense vector is stored in Qdrant under the vector name:

```text
text-dense
```

#### Sparse vector

Sparse vectors are generated with SPLADE using the default model:

```text
naver/splade-cocondenser-ensembledistil
```

The sparse vector is stored in Qdrant under the vector name:

```text
text-sparse
```

#### Qdrant payload

Each stored point includes:

```json
{
  "page_content": "Chunk text...",
  "metadata": {
    "repo_url": "https://github.com/owner/repo",
    "repo_name": "owner_repo",
    "source_path": "docs/example.md",
    "file_type": ".md",
    "section_headings": ["Usage"],
    "char_count": 1000
  },
  "chunk_id": "stable-or-generated-chunk-id"
}
```

---

### 5. Hybrid Retrieval

When a user asks a question, the system performs both dense and sparse retrieval.

The dense path embeds the query using OpenAI embeddings.

The sparse path converts the query into a SPLADE sparse vector.

Both are sent to Qdrant as prefetch queries:

```text
dense query  → text-dense
sparse query → text-sparse
```

The results are merged with Reciprocal Rank Fusion.

Configurable parameters include:

```text
top_k
prefetch_k
dense_weight
sparse_weight
rrf_k
```

The default retrieval behavior is:

```text
top_k = 20
prefetch_k = 20
dense_weight = 1.0
sparse_weight = 1.0
rrf_k = 60
```

This hybrid approach improves retrieval for technical documentation because dense retrieval captures semantic meaning while sparse retrieval captures exact identifiers and keywords.

---

### 6. Reranking

After hybrid retrieval, the top candidates are passed through a cross-encoder reranker.

The current reranker model is:

```text
cross-encoder/ms-marco-MiniLM-L6-v2
```

For each candidate chunk, the reranker scores:

```text
(question, chunk_text)
```

The score is stored in the document metadata as:

```text
cross_score
```

The highest scoring chunks are retained for answer generation.

Default reranked result count:

```text
rerank_top_k = 5
```

---

### 7. Grounded Generation

The final chunks are passed to Claude as citation-enabled search-result blocks.

The generation prompt instructs the model to:

1. Answer only from provided context.
2. Cite every factual claim.
3. Avoid citing unsupported sources.
4. Admit when context is insufficient.
5. Avoid outside knowledge.
6. Avoid guessing.
7. Answer only the supported part when the context is partial.

When there is not enough retrieved context, the model is instructed to respond:

```text
The provided context does not contain enough information to answer that question.
```

The default generation model is:

```text
claude-sonnet-4-6
```

---

### 8. Citation Evaluation

After generation, the system evaluates the answer using a structured evaluator.

The evaluator returns:

```json
{
  "valid_citations": [0, 2],
  "invalid_citations": [1],
  "retrieval_confidence": 0.86,
  "answer_completeness": 0.78
}
```

The evaluation checks:

* Whether cited text directly supports the claim.
* How relevant the retrieved chunks were to the original question.
* How completely the answer addressed the original question.

The current default evaluation model is:

```text
claude-haiku-4-5-20251001
```

---

## API Reference

### GET `/health`

Health check endpoint.

#### Request

```bash
curl http://localhost:8080/health
```

#### Response

```json
{
  "status": "ok"
}
```

---

### POST `/v1/ingest`

Queues ingestion for a public GitHub repository.

#### Request Body

```json
{
  "repo_url": "https://github.com/quwin/RAG-Github-Documentation-Pipeline",
  "branch": null,
  "recursive_chunking": true
}
```

#### Example Request

```bash
curl -X POST "http://localhost:8080/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/quwin/RAG-Github-Documentation-Pipeline",
    "branch": null,
    "recursive_chunking": true
  }'
```

#### Example Response

```json
{
  "status": "queued",
  "repo_url": "https://github.com/quwin/RAG-Github-Documentation-Pipeline"
}
```

#### Notes

This endpoint currently uses a FastAPI background task. The HTTP response confirms that the task was queued, not that indexing has completed.

For long repositories or large documentation sets, ingestion may take several minutes or longer depending on:

* Repository size.
* Number of documentation files.
* Number of chunks.
* OpenAI embedding latency.
* SPLADE sparse-vector computation time.
* Qdrant upsert latency.
* CPU and memory available to the container.

---

### POST `/v1/ask`

Asks a question against an indexed collection.

#### Request Body

```json
{
  "question": "How do I run my own instance in a container?",
  "collection_name": "quwin_RAG-Github-Documentation-Pipeline",
  "top_k": 20,
  "rerank_top_k": 5,
  "dense_weight": 1.0,
  "sparse_weight": 1.0
}
```

#### Example Request

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How do I run my own instance in a container?",
    "collection_name": "quwin_RAG-Github-Documentation-Pipeline",
    "top_k": 20,
    "rerank_top_k": 5,
    "dense_weight": 1.0,
    "sparse_weight": 1.0
  }'
```

#### Example Response

```json
{
  "question": "How do I run my own instance in a contianer?",
  "answer": "The answer generated by Claude appears here with citations.",
  "sources": [
    {
      "chunk_id": "abc123",
      "source_path": "docs/tutorial/security.md",
      "repo_url": "https://github.com/quwin/RAG-Github-Documentation-Pipeline",
      "section_heading": null,
      "retrieval_score": 0.72,
      "cross_score": 4.91,
      "text_preview": "First 500 characters of the source chunk..."
    }
  ],
  "confidence": {
    "retrieval_confidence": 0.86,
    "answer_completeness": 0.78,
    "valid_citations": [0, 1],
    "invalid_citations": []
  }
}
```

---

### GET `/v1/documents`

Lists indexed documents for a collection.

#### Request

```bash
curl "http://localhost:8080/v1/documents?collection_name=quwin_RAG-Github-Documentation-Pipeline"
```

#### Current Response

```json
{
  "collection_name": "quwin_RAG-Github-Documentation-Pipeline",
  "documents": []
}
```

#### Implementation Status

This endpoint is currently a placeholder. It should eventually scroll Qdrant payloads, group chunks by `source_path`, and return document-level metadata.

---

## Request and Response Schemas

### `IngestRequest`

```json
{
  "repo_url": "string",
  "branch": "string | null",
  "recursive_chunking": "boolean"
}
```

Defaults:

```json
{
  "branch": null,
  "recursive_chunking": true
}
```

---

### `AskRequest`

```json
{
  "question": "string",
  "collection_name": "string",
  "top_k": "integer",
  "rerank_top_k": "integer",
  "dense_weight": "number",
  "sparse_weight": "number"
}
```

Defaults:

```json
{
  "collection_name": "github_docs",
  "top_k": 20,
  "rerank_top_k": 5,
  "dense_weight": 1.0,
  "sparse_weight": 1.0
}
```

---

### `AskResponse`

```json
{
  "question": "string",
  "answer": "string",
  "sources": [
    {
      "chunk_id": "string | null",
      "source_path": "string | null",
      "repo_url": "string | null",
      "section_heading": "string | null",
      "retrieval_score": "number | null",
      "cross_score": "number | null",
      "text_preview": "string"
    }
  ],
  "confidence": {
    "retrieval_confidence": "number",
    "answer_completeness": "number",
    "valid_citations": ["integer"],
    "invalid_citations": ["integer"]
  }
}
```

When no relevant chunks are found, the response is:

```json
{
  "question": "Your question",
  "answer": "The provided context does not contain enough information to answer that question.",
  "sources": [],
  "confidence": null
}
```

---

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set environment variables

Create a `.env` file:

```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
QDRANT_URL=your-qdrant-url
QDRANT_API_KEY=your-qdrant-api-key
```

If running Qdrant locally without an API key, `QDRANT_API_KEY` may be omitted depending on your Qdrant setup.

### 5. Start the API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

### 6. Verify the service

```bash
curl http://localhost:8080/health
```

Expected response:

```json
{
  "status": "ok"
}
```

---

## Docker Usage

### Build the image

```bash
docker build -t github-docs-rag .
```

### Run the container

```bash
docker run --rm -p 8080:8080 \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e QDRANT_URL="$QDRANT_URL" \
  -e QDRANT_API_KEY="$QDRANT_API_KEY" \
  github-docs-rag
```

### Run with Docker Compose

```bash
docker compose up --build
```

The Compose file passes the following environment variables into the API container:

```text
OPENAI_API_KEY
ANTHROPIC_API_KEY
QDRANT_URL
QDRANT_API_KEY
```

It also mounts local data into the container:

```text
./data:/app/data
```

---

## Environment Variables

| Variable            | Required | Description                                           |
| ------------------- | -------: | ----------------------------------------------------- |
| `OPENAI_API_KEY`    |      Yes | Used for dense embeddings with OpenAI.                |
| `ANTHROPIC_API_KEY` |      Yes | Used for Claude answer generation and evaluation.     |
| `QDRANT_URL`        |      Yes | URL for the Qdrant instance.                          |
| `QDRANT_API_KEY`    |      Yes | API key for Qdrant Cloud or secured Qdrant instances. |

---

## Example Usage

### 1. Ingest a repository

```bash
curl -X POST "http://localhost:8080/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/quwin/RAG-Github-Documentation-Pipeline",
    "recursive_chunking": true
  }'
```

Example response:

```json
{
  "status": "queued",
  "repo_url": "https://github.com/quwin/RAG-Github-Documentation-Pipeline"
}
```

The collection name will be derived from the GitHub owner and repo name:

```text
quwin_RAG-Github-Documentation-Pipeline
```

### 2. Ask a question

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What container does this use?",
    "collection_name": "quwin_RAG-Github-Documentation-Pipeline"
  }'
```

### 3. Tune retrieval weights

Prioritize semantic retrieval:

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How does FastAPI handle request validation?",
    "collection_name": "fastapi_fastapi",
    "dense_weight": 1.5,
    "sparse_weight": 0.5
  }'
```

Prioritize exact keyword matching:

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does response_model do?",
    "collection_name": "fastapi_fastapi",
    "dense_weight": 0.5,
    "sparse_weight": 1.5
  }'
```

---

## Deployment Notes

This service can be deployed to a Docker container runtime.

Important production considerations:

1. **Do not run very large ingestion jobs synchronously inside request handlers.**

   * The current `/v1/ingest` endpoint uses FastAPI background tasks.
   * For production-scale workloads, use Cloud Run Jobs, Cloud Tasks, Pub/Sub, or another job queue.

2. **Allocate enough CPU and memory.**

   * SPLADE sparse vector creation is CPU-intensive.
   * The reranker loads a transformer model.
   * Large repositories may require significant memory: at least 4GB of Memory is recomended.

3. **Use persistent external Qdrant.**

   * FThis project utilizes Qdrant Cloud as a separately managed Qdrant service.
   * Do not rely on local container storage for production indexing.

4. **Protect ingestion endpoints.**

   * Public ingestion can be abused because cloning, embedding, and sparse encoding are expensive.
   * Add authentication, authorization, request size limits, and domain restrictions.

5. **Restrict CORS in production.**

   * The current API allows all origins.
   * Replace wildcard CORS with your frontend domain.

6. **Set request timeouts deliberately.**

   * Long-running answer requests may time out if retrieval, reranking, generation, and evaluation are all performed inline.
   * Consider making evaluation optional for lower latency.

---

## Current Implementation Status

| Capability                             | Status                |
| -------------------------------------- | --------------------- |
| GitHub repo validation                 | Implemented           |
| Default branch resolution              | Implemented           |
| Repo cloning and refreshing            | Implemented           |
| Documentation file filtering           | Implemented           |
| Metadata extraction                    | Implemented           |
| Markdown-header chunking               | Implemented           |
| Optional recursive chunking            | Implemented           |
| Stable chunk IDs                       | Implemented           |
| Dense OpenAI embeddings                | Implemented           |
| SPLADE sparse vectors                  | Implemented           |
| Qdrant collection creation             | Implemented           |
| Dense+sparse Qdrant storage            | Implemented           |
| Near-duplicate checking                | Implemented           |
| Hybrid RRF retrieval                   | Implemented           |
| Cross-encoder reranking                | Implemented           |
| Claude grounded generation             | Implemented           |
| Citation-enabled context blocks        | Implemented           |
| Citation evaluation                    | Implemented           |
| Confidence scores                      | Implemented           |
| `/health` endpoint                     | Implemented           |
| `/v1/ingest` endpoint                  | Implemented           |
| `/v1/ask` endpoint                     | Implemented           |
| `/v1/documents` endpoint               | Placeholder           |
| Dashboard UI                           | Not yet implemented   |
| QA eval suite                          | Not yet implemented   |
| Cloud Tasks / Cloud Run Jobs ingestion | Not yet implemented   |

---

## Roadmap

### Short-term improvements

* Add ingestion job IDs.
* Add job status tracking.
* Add structured logging.
* Add better exception handling around Git, Qdrant, OpenAI, and Anthropic calls.
* Add request-level timeout handling.
* Add collection deletion or reset endpoint for development.

### Medium-term improvements

* Move ingestion to Cloud Run Jobs or Cloud Tasks.
* Add a dashboard for querying indexed repositories.
* Add a retrieval-debug view showing dense, sparse, fused, and reranked scores.
* Add optional evaluation mode.
* Add streaming answer generation.
* Add authentication for deployed API access.
* Add rate limits.

### Long-term improvements

* Add QA evaluation suite.
* Compare chunking strategies.
* Add regression tests for retrieval quality.
* Support private GitHub repositories.
* Support GitHub App authentication.
* Add incremental indexing based on changed files.
* Add repository webhooks.
* Add multi-repository search.
* Add organization-level documentation search.
* Support Github code files for prejects lacking in-depth technical documentation

---

## Troubleshooting

### `{"detail":[{"type":"missing","loc":["body"],"msg":"Field required","input":null}]}`

This usually means the JSON body was not sent correctly.

Make sure the `curl` command uses backslashes correctly and does not include blank lines after a trailing backslash.

Correct:

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does this documentation say?",
    "collection_name": "owner_repo"
  }'
```

Incorrect:

```bash
curl -X POST "http://localhost:8080/v1/ask" \

  -H "Content-Type: application/json" \

  -d '{
    "question": "What does this documentation say?",
    "collection_name": "owner_repo"
  }'
```

Blank lines after backslashes can cause the shell to execute `-H` and `-d` as separate commands.

---

### `QDRANT_URL` missing

If the service fails with a missing environment variable error, confirm that `QDRANT_URL` is set.

```bash
echo $QDRANT_URL
```

For Docker Compose, confirm that your `.env` file exists and contains:

```bash
QDRANT_URL=your-qdrant-url
```

---

### OpenAI authentication error

Confirm:

```bash
echo $OPENAI_API_KEY
```

The ingestion pipeline requires OpenAI access to generate dense embeddings.

---

### Anthropic authentication error

Confirm:

```bash
echo $ANTHROPIC_API_KEY
```

The answering and evaluation layers require Anthropic access.

---

### Ingestion takes a long time

Large repositories can create many chunks. Each chunk requires:

1. Dense embedding.
2. Sparse SPLADE vector creation.
3. Qdrant point construction.
4. Qdrant upsert.

To reduce ingestion time:

* Use smaller repositories during testing.
* Disable recursive chunking for initial experiments.
* Increase CPU allocation.
* Move ingestion into an asynchronous job system.
* Batch sparse-vector generation where possible.
* Cache model loading.
* Avoid re-indexing the same repository repeatedly.

---

## Example End-to-End Flow

### Start the API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8080
```

### Ingest a repository

```bash
curl -X POST "http://localhost:8080/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/quwin/UnderTheGun",
    "recursive_chunking": true
  }'
```

### Ask a question

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does this documentation say?",
    "collection_name": "quwin_UnderTheGun"
  }'
```

### Ask with custom retrieval settings

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which configuration keys are supported?",
    "collection_name": "quwin_UnderTheGun",
    "top_k": 30,
    "rerank_top_k": 8,
    "dense_weight": 0.8,
    "sparse_weight": 1.2
  }'
```

---

## Design Rationale

### Why hybrid search?

Dense retrieval is strong for semantic similarity, but it can miss exact identifiers. Technical documentation often depends on exact strings such as:

* Function names
* Class names
* File names
* Environment variables
* Error messages
* CLI commands
* Configuration keys

Sparse retrieval is better at matching exact terms. Combining dense and sparse retrieval gives the system both semantic understanding and keyword precision.

---

### Why reranking?

Hybrid retrieval gives a broad candidate set. The reranker improves precision by directly scoring each candidate chunk against the user’s question.

This helps reduce irrelevant context before generation, which can improve:

* Answer quality
* Citation accuracy
* Context efficiency
* Grounding

---

### Why citation evaluation?

Many RAG systems return citations without verifying whether the citation actually supports the claim. This project adds a second-pass evaluation layer that checks citation support and answer completeness.

This makes the system more production-ready and easier to evaluate.


---

## Acknowledgements

This project uses:

* FastAPI for API serving.
* Qdrant for dense and sparse vector search.
* OpenAI for dense embeddings.
* Anthropic Claude for grounded answer generation.
* LangChain for document abstractions and text splitting.
* Sentence Transformers for cross-encoder reranking.
* Hugging Face Transformers for SPLADE sparse encoding.

# GitHub Documentation RAG Pipeline

A production-oriented Retrieval-Augmented Generation pipeline for ingesting public GitHub repository documentation, indexing it with hybrid dense and sparse retrieval, and answering questions with grounded citations, source metadata, and confidence scores.

This project is designed for both architectural and technical documentation search, where exact terms such as function names, configuration keys, class names, CLI flags, file paths, and error messages matter as much as semantic similarity.

---

## Highlights

* Ingests public GitHub repository documentation.
* Filters documentation-like files and extracts source metadata.
* Chunks documents using Markdown headers with optional recursive splitting.
* Stores OpenAI dense embeddings and SPLADE sparse vectors in Qdrant.
* Retrieves context using hybrid dense+sparse search with weighted RRF.
* Reranks retrieved chunks with a cross-encoder.
* Generates grounded answers with Claude.
* Evaluates citation validity, retrieval confidence, and answer completeness.
* Exposes a FastAPI API for ingestion, question answering, and document inspection.
* Runs locally or in a containerized deployment.

---

## Architecture

```text
Public GitHub Repo
        ↓
Document Loader
        ↓
Documentation Filtering
        ↓
Markdown / Recursive Chunking
        ↓
Dense Embeddings + Sparse Encoding
        ↓
Qdrant Vector Store
        ↓
Hybrid Dense + Sparse Retrieval
        ↓
Reciprocal Rank Fusion
        ↓
Cross-Encoder Reranking
        ↓
Claude Grounded Generation
        ↓
Citation Evaluation
        ↓
FastAPI JSON Response
```

Full system design: [docs/architecture.md](docs/architecture.md)

---

## Tech Stack

| Layer              | Technology                          |
| ------------------ | ----------------------------------- |
| API                | FastAPI                             |
| Server             | Uvicorn                             |
| Request validation | Pydantic                            |
| Dense embeddings   | OpenAI `text-embedding-3-small`     |
| Sparse retrieval   | SPLADE                              |
| Vector database    | Qdrant                              |
| Hybrid retrieval   | Dense + sparse search with RRF      |
| Reranking          | Sentence Transformers cross-encoder |
| Generation         | Anthropic Claude                    |
| Chunking           | LangChain text splitters            |
| Containerization   | Docker                              |

---

## API Overview

| Method | Endpoint        | Purpose                                        |
| ------ | --------------- | ---------------------------------------------- |
| `GET`  | `/health`       | Check whether the API is running               |
| `POST` | `/v1/ingest`    | Queue ingestion for a public GitHub repository |
| `POST` | `/v1/ask`       | Ask a question against an indexed collection   |
| `GET`  | `/v1/documents` | List indexed documents for a collection        |

Full API documentation: [docs/api-reference.md](docs/api-reference.md)

---

## Quick Start

### 1. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Set environment variables

Create a `.env` file:

```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
QDRANT_URL=your-qdrant-url
QDRANT_API_KEY=your-qdrant-api-key
```

### 3. Start the API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

### 4. Verify the service

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

Build the image:

```bash
docker build -t github-docs-rag .
```

Run the container:

```bash
docker run --rm -p 8080:8080 \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e QDRANT_URL="$QDRANT_URL" \
  -e QDRANT_API_KEY="$QDRANT_API_KEY" \
  github-docs-rag
```

Or run with Docker Compose:

```bash
docker compose up --build
```

Deployment details: [docs/deployment.md](docs/deployment.md)

---

## Example Usage

### Ingest a repository

```bash
curl -X POST "http://localhost:8080/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/quwin/UnderTheGun",
    "recursive_chunking": true
  }'
```

Example response:

```json
{
  "status": "queued",
  "repo_url": "https://github.com/quwin/UnderTheGun"
}
```

The collection name is derived from the GitHub owner and repository name:

```text
quwin_UnderTheGun
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

### List indexed documents

```bash
curl "http://localhost:8080/v1/documents?collection_name=quwin_UnderTheGun"
```

To include chunk IDs:

```bash
curl "http://localhost:8080/v1/documents?collection_name=quwin_UnderTheGun&include_chunk_ids=true"
```

---

## Request Examples

### `/v1/ingest`

```json
{
  "repo_url": "https://github.com/quwin/UnderTheGun",
  "branch": null,
  "erase_prior_embeddings": false,
  "recursive_chunking": true
}
```

### `/v1/ask`

```json
{
  "question": "Which configuration keys are supported?",
  "collection_name": "quwin_UnderTheGun",
  "top_k": 20,
  "rerank_top_k": 5,
  "dense_weight": 1.0,
  "sparse_weight": 1.0
}
```

### `/v1/documents`

```bash
GET /v1/documents?collection_name=quwin_UnderTheGun
```

---

## Documentation

| Document                                                       | Description                                                                           |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| [Architecture](docs/architecture.md)                           | End-to-end system design and component responsibilities                               |
| [API Reference](docs/api-reference.md)                         | Endpoint details, request bodies, response bodies, and curl examples                  |
| [Deployment](docs/deployment.md)                               | Docker, Docker Compose, Cloud Run, environment variables, and production notes        |

---

## Current Status

Implemented:

* GitHub repo validation
* Default branch resolution
* Repository cloning and refreshing
* Documentation file filtering
* Metadata extraction
* Markdown-header chunking
* Optional recursive chunking
* Stable chunk IDs
* Dense OpenAI embeddings
* SPLADE sparse vectors
* Qdrant dense+sparse vector storage
* Hybrid RRF retrieval
* Cross-encoder reranking
* Claude grounded generation
* Citation-enabled responses
* Citation evaluation
* Confidence scores
* `/health` endpoint
* `/v1/ingest` endpoint
* `/v1/ask` endpoint
* `/v1/documents` endpoint

Not yet implemented:

* Dashboard UI
* Full Q&A evaluation suite
* Automatic ingestion workflow
* Authentication and rate limiting
* Streaming answer generation
* Multi-repository search

---

## Design Rationale

Dense retrieval is strong for semantic similarity, but technical documentation often depends on exact strings such as function names, file paths, environment variables, CLI commands, configuration keys, and error messages.

This project combines dense retrieval with sparse retrieval so the system can capture both semantic meaning and exact keyword matches. A cross-encoder reranker then improves precision before generation, and a citation evaluation layer checks whether generated claims are actually supported by cited context.

More detail: [docs/architecture.md](docs/architecture.md)

---

## Roadmap

Near-term improvements:

* Add ingestion job IDs.
* Add job status tracking.
* Move long-running ingestion to Cloud Tasks or Cloud Run Jobs.
* Add structured logging.
* Add better error handling around Git, Qdrant, OpenAI, and Anthropic calls.
* Add optional evaluation mode for lower-latency responses.
* Add a dashboard for querying indexed repositories.

---

## Acknowledgements

This project uses FastAPI, Qdrant, OpenAI, Anthropic Claude, LangChain, Sentence Transformers, Hugging Face Transformers, and Docker.

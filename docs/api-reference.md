# API Reference

This document describes the public HTTP API for the GitHub Documentation RAG Pipeline.

The API is implemented with FastAPI and exposes endpoints for:

* checking service health
* ingesting public GitHub repositories
* asking questions over indexed documentation
* listing indexed source documents in a Qdrant collection

Default local base URL:

```text
http://localhost:8080
```

---

## Endpoints

| Method | Endpoint        | Description                                    |
| ------ | --------------- | ---------------------------------------------- |
| `GET`  | `/health`       | Check whether the API is running               |
| `POST` | `/v1/ingest`    | Queue ingestion for a public GitHub repository |
| `POST` | `/v1/ask`       | Ask a question against an indexed collection   |
| `GET`  | `/v1/documents` | List indexed documents for a collection        |

---

## Authentication

The current API implementation does not enforce authentication.

For production deployments, add authentication before exposing the API publicly, especially for `/v1/ingest`, because ingestion can trigger expensive Git cloning, embedding, sparse encoding, and vector upsert work.

Recommended production controls:

* API key authentication
* request size limits
* repository allowlists or domain restrictions
* rate limiting
* user-level quotas
* protected CORS configuration

---

## Content Type

All `POST` requests should use:

```http
Content-Type: application/json
```

Example:

```bash
-H "Content-Type: application/json"
```

---

# `GET /health`

Health check endpoint.

Use this endpoint to verify that the FastAPI service is running.

---

## Request

```bash
curl "http://localhost:8080/health"
```

---

## Response

```json
{
  "status": "ok"
}
```

---

## Response Fields

| Field    | Type   | Description                                             |
| -------- | ------ | ------------------------------------------------------- |
| `status` | string | Service status. Returns `"ok"` when the API is running. |

---

# `POST /v1/ingest`

Queues ingestion for a public GitHub repository.

This endpoint accepts a GitHub repository URL, resolves the branch if needed, loads documentation-like files, chunks them, embeds them, creates sparse vectors, and upserts the resulting points into Qdrant.

The endpoint returns immediately after queuing the ingestion task. A successful HTTP response means the ingestion task was queued, not necessarily completed.

---

## Request Body

```json
{
  "repo_url": "https://github.com/quwin/UnderTheGun",
  "branch": null,
  "erase_prior_embeddings": false,
  "recursive_chunking": true
}
```

---

## Request Fields

| Field                    |           Type | Required | Default | Description                                                                |
| ------------------------ | -------------: | -------: | ------: | -------------------------------------------------------------------------- |
| `repo_url`               |         string |      Yes |     N/A | Public GitHub repository URL to ingest                                     |
| `branch`                 | string or null |       No |  `null` | Branch to ingest. If omitted, the default branch is resolved automatically |
| `erase_prior_embeddings` |        boolean |       No | `false` | Whether to delete the existing Qdrant collection before re-indexing        |
| `recursive_chunking`     |        boolean |       No |  `true` | Whether to apply recursive splitting after Markdown-header splitting       |

---

## Example Request

```bash
curl -X POST "http://localhost:8080/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/quwin/UnderTheGun",
    "recursive_chunking": true
  }'
```

---

## Example Response

```json
{
  "status": "queued",
  "repo_url": "https://github.com/quwin/UnderTheGun"
}
```

---

## Response Fields

| Field      | Type   | Description                                                                 |
| ---------- | ------ | --------------------------------------------------------------------------- |
| `status`   | string | Queue status. Returns `"queued"` when the ingestion task has been scheduled |
| `repo_url` | string | Repository URL submitted for ingestion                                      |

---

## Collection Naming

The Qdrant collection name is derived from the GitHub owner and repository name.

For example:

```text
https://github.com/quwin/UnderTheGun
```

becomes:

```text
quwin_UnderTheGun
```

Use this collection name when calling `/v1/ask` or `/v1/documents`.

---

## Notes

Ingestion can take a long time for large repositories because each chunk may require:

1. dense embedding generation
2. SPLADE sparse vector creation
3. Qdrant point construction
4. Qdrant upsert

For production workloads, consider moving ingestion to Cloud Tasks, Pub/Sub, Cloud Run Jobs, or another external job system instead of relying only on FastAPI background tasks.

---

## Possible Errors

### Invalid or unsupported GitHub URL

```json
{
  "detail": "Only github.com repositories are allowed."
}
```

### Missing request body

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

This usually means the JSON body was not passed correctly in the request.

---

# `POST /v1/ask`

Asks a question against an indexed documentation collection.

This endpoint performs the full RAG pipeline:

1. embeds the user question
2. computes a sparse query vector
3. retrieves dense and sparse candidates from Qdrant
4. combines results with Reciprocal Rank Fusion
5. reranks candidates with a cross-encoder
6. sends the top chunks to Claude
7. generates a grounded answer with citations
8. evaluates citation quality and answer completeness

---

## Request Body

```json
{
  "question": "What does this documentation say?",
  "collection_name": "quwin_UnderTheGun",
  "top_k": 20,
  "rerank_top_k": 5,
  "dense_weight": 1.0,
  "sparse_weight": 1.0
}
```

---

## Request Fields

| Field             |    Type | Required |         Default | Description                                                     |
| ----------------- | ------: | -------: | --------------: | --------------------------------------------------------------- |
| `question`        |  string |      Yes |             N/A | User question to answer from indexed documentation              |
| `collection_name` |  string |       No | `"github_docs"` | Qdrant collection to search                                     |
| `top_k`           | integer |       No |            `20` | Number of fused retrieval candidates to return before reranking |
| `rerank_top_k`    | integer |       No |             `5` | Number of reranked chunks to keep for generation                |
| `dense_weight`    |  number |       No |           `1.0` | Weight applied to dense retrieval during RRF fusion             |
| `sparse_weight`   |  number |       No |           `1.0` | Weight applied to sparse retrieval during RRF fusion            |

---

## Example Request

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does this documentation say?",
    "collection_name": "quwin_UnderTheGun"
  }'
```

---

## Example Request with Custom Retrieval Settings

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

## Example Response

```json
{
  "question": "What does this documentation say?",
  "answer": "The generated answer appears here with citations.",
  "sources": [
    {
      "chunk_id": "2f1c8f7e...",
      "source_path": "README.md",
      "repo_url": "https://github.com/quwin/UnderTheGun",
      "section_heading": null,
      "retrieval_score": 0.7421,
      "cross_score": 5.1834,
      "text_preview": "The first 500 characters of the retrieved source chunk..."
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

## Response Fields

| Field        | Type           | Description                            |
| ------------ | -------------- | -------------------------------------- |
| `question`   | string         | Original user question                 |
| `answer`     | string         | Generated answer from Claude           |
| `sources`    | array          | Reranked source chunks used as context |
| `confidence` | object or null | Citation and answer quality metadata   |

---

## `sources[]` Fields

| Field             | Type           | Description                                               |
| ----------------- | -------------- | --------------------------------------------------------- |
| `chunk_id`        | string or null | Stable chunk identifier, when available                   |
| `source_path`     | string or null | Source file path inside the repository                    |
| `repo_url`        | string or null | Original GitHub repository URL                            |
| `section_heading` | string or null | Section heading associated with the chunk, when available |
| `retrieval_score` | number or null | Score from Qdrant hybrid retrieval                        |
| `cross_score`     | number or null | Score from the cross-encoder reranker                     |
| `text_preview`    | string         | Preview of the retrieved chunk text                       |

---

## `confidence` Fields

| Field                  | Type              | Description                                                                |
| ---------------------- | ----------------- | -------------------------------------------------------------------------- |
| `retrieval_confidence` | number            | Evaluator score for how relevant the retrieved chunks were to the question |
| `answer_completeness`  | number            | Evaluator score for how completely the answer addressed the question       |
| `valid_citations`      | array of integers | Citation indexes judged to be supported                                    |
| `invalid_citations`    | array of integers | Citation indexes judged to be unsupported or only partially supported      |

---

## Insufficient Context Response

If no relevant reranked chunks are found, the endpoint returns:

```json
{
  "question": "Your question",
  "answer": "The provided context does not contain enough information to answer that question.",
  "sources": [],
  "confidence": null
}
```

The generation prompt also instructs the model to return an insufficient-context answer when the retrieved context does not support the question.

---

## Retrieval Tuning

You can tune retrieval behavior through the request body.

### Favor semantic similarity

Use a higher dense weight when the question is conceptual or phrased differently from the documentation.

```json
{
  "question": "How does the app decide what information to retrieve?",
  "collection_name": "quwin_UnderTheGun",
  "dense_weight": 1.5,
  "sparse_weight": 0.5
}
```

### Favor exact keyword matching

Use a higher sparse weight when searching for exact identifiers, error messages, config keys, class names, file paths, or CLI flags.

```json
{
  "question": "What does OPENAI_API_KEY do?",
  "collection_name": "quwin_UnderTheGun",
  "dense_weight": 0.5,
  "sparse_weight": 1.5
}
```

### Increase candidate pool

Use a larger `top_k` and `rerank_top_k` for broader questions where the answer may span several documents.

```json
{
  "question": "How does ingestion work from start to finish?",
  "collection_name": "quwin_UnderTheGun",
  "top_k": 40,
  "rerank_top_k": 10
}
```

---

## Possible Errors

### Missing request body

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

This often happens when a multiline `curl` command contains blank lines after trailing backslashes.

Correct:

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does this documentation say?",
    "collection_name": "quwin_UnderTheGun"
  }'
```

Incorrect:

```bash
curl -X POST "http://localhost:8080/v1/ask" \

  -H "Content-Type: application/json" \

  -d '{
    "question": "What does this documentation say?",
    "collection_name": "quwin_UnderTheGun"
  }'
```

---

# `GET /v1/documents`

Lists indexed source documents for a Qdrant collection.

This endpoint scrolls stored Qdrant points, reads chunk payload metadata, groups chunks by `source_path`, and returns document-level summaries.

Use this endpoint to verify whether ingestion produced indexed documents.

---

## Query Parameters

| Parameter           |    Type | Required | Default | Description                                    |
| ------------------- | ------: | -------: | ------: | ---------------------------------------------- |
| `collection_name`   |  string |      Yes |     N/A | Qdrant collection to inspect                   |
| `include_chunk_ids` | boolean |       No | `false` | Whether to include chunk IDs for each document |

---

## Example Request

```bash
curl "http://localhost:8080/v1/documents?collection_name=quwin_UnderTheGun"
```

---

## Example Request Including Chunk IDs

```bash
curl "http://localhost:8080/v1/documents?collection_name=quwin_UnderTheGun&include_chunk_ids=true"
```

---

## Example Response

```json
{
  "collection_name": "quwin_UnderTheGun",
  "document_count": 2,
  "total_chunks": 14,
  "documents": [
    {
      "source_path": "README.md",
      "repo_url": "https://github.com/quwin/UnderTheGun",
      "repo_name": "quwin_UnderTheGun",
      "file_type": ".md",
      "char_count": 8234,
      "section_headings": [
        "Overview",
        "Installation",
        "Usage"
      ],
      "chunk_count": 8,
      "chunk_ids": [],
      "text_preview": "First 300 characters of the source document or chunk..."
    },
    {
      "source_path": "docs/setup.md",
      "repo_url": "https://github.com/quwin/UnderTheGun",
      "repo_name": "quwin_UnderTheGun",
      "file_type": ".md",
      "char_count": 4120,
      "section_headings": [
        "Setup",
        "Environment Variables"
      ],
      "chunk_count": 6,
      "chunk_ids": [],
      "text_preview": "First 300 characters of the source document or chunk..."
    }
  ]
}
```

---

## Example Response with `include_chunk_ids=true`

```json
{
  "collection_name": "quwin_UnderTheGun",
  "document_count": 1,
  "total_chunks": 3,
  "documents": [
    {
      "source_path": "README.md",
      "repo_url": "https://github.com/quwin/UnderTheGun",
      "repo_name": "quwin_UnderTheGun",
      "file_type": ".md",
      "char_count": 8234,
      "section_headings": [
        "Overview",
        "Installation",
        "Usage"
      ],
      "chunk_count": 3,
      "chunk_ids": [
        "b8f2e1...",
        "c01d94...",
        "e718aa..."
      ],
      "text_preview": "First 300 characters of the source document or chunk..."
    }
  ]
}
```

---

## Response Fields

| Field             | Type    | Description                                       |
| ----------------- | ------- | ------------------------------------------------- |
| `collection_name` | string  | Qdrant collection that was inspected              |
| `document_count`  | integer | Number of unique source documents found           |
| `total_chunks`    | integer | Total number of chunks found across all documents |
| `documents`       | array   | Document-level summaries grouped by source path   |

---

## `documents[]` Fields

| Field              | Type             | Description                                                   |
| ------------------ | ---------------- | ------------------------------------------------------------- |
| `source_path`      | string           | File path inside the source repository                        |
| `repo_url`         | string or null   | Original GitHub repository URL                                |
| `repo_name`        | string or null   | Derived repository collection name                            |
| `file_type`        | string or null   | Source file extension                                         |
| `char_count`       | integer or null  | Character count from the original source document metadata    |
| `section_headings` | array of strings | Markdown headings extracted from the source document          |
| `chunk_count`      | integer          | Number of indexed chunks for this source document             |
| `chunk_ids`        | array of strings | Chunk IDs. Empty unless `include_chunk_ids=true`              |
| `text_preview`     | string or null   | Preview text from the first available chunk for that document |

---

## Collection Not Found

If the collection does not exist, the endpoint returns a `404`.

Example:

```json
{
  "detail": "Collection 'missing_collection' does not exist."
}
```

---

# Schemas

This section documents the primary request and response schemas used by the API.

---

## `IngestRequest`

```json
{
  "repo_url": "string",
  "branch": "string | null",
  "erase_prior_embeddings": "boolean",
  "recursive_chunking": "boolean"
}
```

Defaults:

```json
{
  "branch": null,
  "erase_prior_embeddings": false,
  "recursive_chunking": true
}
```

---

## `AskRequest`

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

## `AskResponse`

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

---

## `DocumentsResponse`

```json
{
  "collection_name": "string",
  "document_count": "integer",
  "total_chunks": "integer",
  "documents": [
    {
      "source_path": "string",
      "repo_url": "string | null",
      "repo_name": "string | null",
      "file_type": "string | null",
      "char_count": "integer | null",
      "section_headings": ["string"],
      "chunk_count": "integer",
      "chunk_ids": ["string"],
      "text_preview": "string | null"
    }
  ]
}
```

---

# Common Workflows

## Verify API Health

```bash
curl "http://localhost:8080/health"
```

---

## Ingest a Repository

```bash
curl -X POST "http://localhost:8080/v1/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/quwin/UnderTheGun",
    "recursive_chunking": true
  }'
```

---

## Check Whether Documents Were Indexed

```bash
curl "http://localhost:8080/v1/documents?collection_name=quwin_UnderTheGun"
```

---

## Ask a Question

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does this documentation say?",
    "collection_name": "quwin_UnderTheGun"
  }'
```

---

## Ask with Keyword-Heavy Retrieval

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does QDRANT_URL configure?",
    "collection_name": "quwin_UnderTheGun",
    "dense_weight": 0.5,
    "sparse_weight": 1.5
  }'
```

---

# Production Notes

## Long-Running Ingestion

The ingestion endpoint currently queues a FastAPI background task. This is acceptable for local development and small demos, but long-running ingestion jobs are better handled by a dedicated job system.

Recommended options:

* Cloud Run Jobs
* Cloud Tasks
* Pub/Sub
* Celery
* RQ
* another external worker queue

---

## Timeouts

Answer requests may be slow because they can involve:

1. OpenAI query embedding
2. SPLADE sparse query encoding
3. Qdrant retrieval
4. cross-encoder reranking
5. Claude generation
6. Claude-based citation evaluation

To reduce latency:

* lower `top_k`
* lower `rerank_top_k`
* make evaluation optional
* cache model loading
* allocate more CPU and memory
* split ingestion and question-answering into separate services

---

## Security

Before public deployment, protect the API with:

* authentication
* rate limits
* request validation
* repository allowlists
* stricter CORS settings
* logging and abuse monitoring

The ingestion endpoint is especially sensitive because it performs expensive external and compute-heavy operations.

---

# Troubleshooting

## `Field required` Error

Error:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

Cause:

The JSON request body was not sent correctly.

Common reason:

A multiline `curl` command had blank lines after trailing backslashes.

Correct:

```bash
curl -X POST "http://localhost:8080/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does this documentation say?",
    "collection_name": "quwin_UnderTheGun"
  }'
```

Incorrect:

```bash
curl -X POST "http://localhost:8080/v1/ask" \

  -H "Content-Type: application/json" \

  -d '{
    "question": "What does this documentation say?",
    "collection_name": "quwin_UnderTheGun"
  }'
```

---

## Collection Does Not Exist

Error:

```json
{
  "detail": "Collection 'quwin_UnderTheGun' does not exist."
}
```

Possible causes:

* ingestion has not completed yet
* the collection name is wrong
* ingestion failed before creating the collection
* `erase_prior_embeddings=true` deleted the collection before a failed re-ingestion

Fixes:

1. Confirm the collection name derived from the GitHub URL.
2. Check API logs for ingestion errors.
3. Re-run ingestion.
4. Call `/v1/documents` again after ingestion has completed.

---

## Empty Document List

Possible causes:

* ingestion is still running
* no documentation-like files were found
* Qdrant upsert has not completed yet
* the wrong collection name was used
* the repository only contains unsupported file types

Fixes:

1. Check logs for `documents_loaded` and `chunks_created`.
2. Confirm the repository contains supported documentation files.
3. Confirm the collection name.
4. Retry with `erase_prior_embeddings=true` if you want to rebuild the collection.

---

## Slow Ingestion

Large repositories can create many chunks. Each chunk requires dense embedding, sparse vector computation, and Qdrant upsert work.

Ways to reduce ingestion time:

* test with smaller repositories
* disable recursive chunking for initial tests
* allocate more CPU
* batch sparse-vector generation
* move ingestion into Cloud Run Jobs or another worker system
* avoid repeatedly re-indexing the same repository

---

## Slow Question Answering

Answer requests may be slow because retrieval, reranking, generation, and evaluation run in one request path.

Ways to reduce answer latency:

* lower `top_k`
* lower `rerank_top_k`
* make citation evaluation optional
* use a smaller reranker
* skip reranking for simple queries
* cache frequent queries
* allocate more CPU and memory

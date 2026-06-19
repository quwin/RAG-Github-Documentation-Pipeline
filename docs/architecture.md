# Architecture

This document describes the architecture of the GitHub Documentation RAG Pipeline.

The system is designed to ingest documentation from public GitHub repositories, index that documentation with both dense and sparse retrieval signals, retrieve relevant chunks for a user question, and generate grounded answers with citations and confidence metadata.

## Summary

The architecture is built around a layered RAG pipeline:

```text
ingest -> chunk -> embed -> retrieve -> rerank -> generate -> evaluate
```

The key design choice is hybrid retrieval. Dense embeddings provide semantic matching, while SPLADE sparse vectors preserve exact technical terms. RRF combines both retrieval paths, a cross-encoder reranker improves precision, Claude generates grounded answers, and the evaluator adds quality signals for citations and completeness.

This design makes the system more reliable for technical documentation than a dense-only RAG pipeline.


---

## System Goals

The main goals of this project are:

1. **Grounded question answering**

   Answers should be generated only from retrieved repository documentation, not from the model's general knowledge.

2. **Traceable citations**

   Responses should include source-backed citations so users can understand which documentation chunks support each answer.

3. **Hybrid retrieval**

   The retriever should support both semantic similarity and exact keyword matching.

4. **Technical documentation awareness**

   The system should perform well on documentation queries involving function names, class names, configuration keys, environment variables, file paths, CLI flags, and error messages.

5. **Production-oriented API design**

   The project should expose a clean FastAPI interface for ingestion, question answering, and document inspection.

6. **Evaluation hooks**

   The system should include confidence and citation-evaluation signals so answer quality can be inspected instead of assumed.

---

## High-Level Architecture

```text
Public GitHub Repository
        |
        v
GitHub Repository Loader
        |
        v
Documentation Filter
        |
        v
Document Metadata Extraction
        |
        v
Markdown / Recursive Chunking
        |
        v
Dense Embedding + Sparse Encoding
        |
        v
Qdrant Vector Database
        |
        v
Hybrid Dense + Sparse Retrieval
        |
        v
Reciprocal Rank Fusion
        |
        v
Cross-Encoder Reranking
        |
        v
Claude Grounded Generation
        |
        v
Citation and Answer Evaluation
        |
        v
FastAPI JSON Response
```

---

## Runtime Components

| Component        | Responsibility                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------ |
| FastAPI app      | Exposes HTTP routes for health checks, ingestion, question answering, and document listing |
| Reader           | Clones GitHub repositories and loads documentation-like files                              |
| Chunker          | Splits source documents into retrievable chunks                                            |
| Embedder         | Creates dense and sparse vector representations and stores them in Qdrant                  |
| Sparse encoder   | Converts text into SPLADE-style sparse vectors                                             |
| Qdrant           | Stores dense vectors, sparse vectors, and chunk metadata                                   |
| Hybrid retriever | Retrieves candidates using dense and sparse search                                         |
| RRF fusion layer | Combines dense and sparse retrieval candidates into one ranked list                        |
| Reranker         | Uses a cross-encoder to improve precision before generation                                |
| Generation layer | Sends retrieved chunks to Claude with a grounded-answer prompt                             |
| Evaluation layer | Scores citation validity, retrieval confidence, and answer completeness                    |

---

## API Layer

The API layer is implemented with FastAPI.

It exposes four main routes:

| Method | Route           | Purpose                                          |
| ------ | --------------- | ------------------------------------------------ |
| `GET`  | `/health`       | Confirms the API is running                      |
| `POST` | `/v1/ingest`    | Queues repository ingestion                      |
| `POST` | `/v1/ask`       | Answers a question against an indexed collection |
| `GET`  | `/v1/documents` | Lists indexed documents for a collection         |

The API layer is intentionally thin. It validates requests, delegates work to service functions, and returns structured responses.

---

## Request Flow: Repository Ingestion

Repository ingestion starts when a client calls:

```text
POST /v1/ingest
```

Example request:

```json
{
  "repo_url": "https://github.com/quwin/UnderTheGun",
  "branch": null,
  "erase_prior_embeddings": false,
  "recursive_chunking": true
}
```

The ingestion flow is:

```text
/v1/ingest
    |
    v
ingest_repo()
    |
    v
resolve default branch
    |
    v
load_documents_from_repo()
    |
    v
header_chunk_documents()
    |
    v
embed_unique_chunks()
    |
    v
Qdrant collection
```

---

## Ingestion Service

The ingestion service coordinates the ingestion pipeline.

It performs four main steps:

1. Resolve the repository branch.
2. Load documentation files from the repository.
3. Split loaded documents into chunks.
4. Embed and upsert chunks into Qdrant.

The service returns a structured ingestion result containing:

```json
{
  "repo_url": "https://github.com/owner/repo",
  "branch": "main",
  "documents_loaded": 10,
  "chunks_created": 64,
  "collection_name": "owner_repo",
  "status": "indexed"
}
```

The `/v1/ingest` endpoint currently queues ingestion with a FastAPI background task and returns immediately with:

```json
{
  "status": "queued",
  "repo_url": "https://github.com/owner/repo"
}
```

This means the HTTP response confirms that ingestion was queued, not that indexing has completed.

---

## Repository Loading

The repository loader is responsible for safely loading public GitHub documentation.

It performs the following steps:

1. Validate that the URL is an HTTPS GitHub repository URL.
2. Resolve the repository name from the GitHub owner and repo.
3. Clone the repository into the local `data/repos/` directory.
4. If the repository already exists locally, refresh it with Git.
5. Walk the repository tree.
6. Keep documentation-like files.
7. Exclude irrelevant directories, build outputs, media files, binaries, and archives.
8. Extract metadata for each loaded document.

The collection name is derived from the GitHub repository path.

For example:

```text
https://github.com/quwin/UnderTheGun
```

becomes:

```text
quwin_UnderTheGun
```

---

## Documentation Filtering

The loader keeps documentation-like files.

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

The loader excludes common non-documentation directories such as:

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

It also excludes binary, image, video, archive, and executable formats such as:

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

This keeps the index focused on source documentation rather than generated artifacts or irrelevant repository files.

---

## Document Metadata

Each loaded document is represented as a LangChain `Document`.

The document metadata includes:

```json
{
  "repo_url": "https://github.com/owner/repo",
  "repo_name": "owner_repo",
  "source_path": "docs/example.md",
  "file_type": ".md",
  "section_headings": ["Overview", "Usage", "Configuration"],
  "char_count": 12345
}
```

This metadata is preserved through chunking, embedding, retrieval, and final source attribution.

---

## Chunking Layer

The chunking layer splits repository documentation into retrieval-sized units.

The current implementation uses Markdown-header-based splitting.

It recognizes:

```text
# Header 1
## Header 2
### Header 3
```

When recursive chunking is enabled, the system applies recursive character splitting after Markdown-header splitting.

Default recursive settings:

```text
chunk_size = 1024
chunk_overlap = 200
```

This produces chunks that are small enough for retrieval but still preserve useful section-level structure.

---

## Stable Chunk IDs

Each chunk receives a deterministic chunk ID based on normalized chunk content.

The chunk ID is generated by:

1. lowercasing the chunk text
2. normalizing whitespace
3. hashing the normalized text with SHA-256

This makes repeated indexing more stable because identical chunks produce the same logical ID.

The design also helps identify duplicate content across documentation files.

---

## Embedding and Sparse Encoding Layer

For each chunk, the system creates two vector representations:

1. a dense vector
2. a sparse vector

These representations support different retrieval strengths.

---

## Dense Embeddings

Dense embeddings are generated with OpenAI embeddings.

The expected dense vector size is 1536 dimensions.

Dense retrieval is useful for semantic matching. It can retrieve relevant chunks even when the user's wording differs from the documentation.

Example:

```text
User query:
"How do I configure the database connection?"

Documentation wording:
"Set the DATABASE_URL environment variable before starting the service."
```

A dense retriever can often connect these semantically related statements.

---

## Sparse Encoding

Sparse vectors are generated with SPLADE.

Sparse retrieval is useful for exact identifier matching.

It is especially important for technical documentation containing:

* environment variables
* function names
* class names
* file paths
* CLI commands
* config keys
* package names
* error messages

Example:

```text
OPENAI_API_KEY
QDRANT_URL
response_model
docker-compose.yaml
```

Dense embeddings may blur these exact identifiers, while sparse retrieval can preserve them as strong lexical signals.

---

## Qdrant Storage Design

The system stores both dense and sparse vectors in the same Qdrant collection.

Each point contains:

```json
{
  "id": "uuid",
  "vector": {
    "text-dense": [0.01, 0.02, 0.03],
    "text-sparse": {
      "indices": [123, 456, 789],
      "values": [0.8, 0.4, 0.2]
    }
  },
  "payload": {
    "page_content": "Chunk text...",
    "metadata": {
      "repo_url": "https://github.com/owner/repo",
      "repo_name": "owner_repo",
      "source_path": "docs/example.md",
      "file_type": ".md",
      "section_headings": ["Usage"],
      "char_count": 1000
    },
    "chunk_id": "stable-chunk-id"
  }
}
```

This design allows a single collection to support both semantic vector search and sparse lexical search.

---

## Deduplication Strategy

Before inserting chunks, the embedder can check whether similar chunks already exist.

The similarity threshold, by default is 95% (0.95):

If an existing chunk is above the threshold, the new chunk can be skipped.

This avoids wasting retrieval slots on duplicate content and reduces redundant context during answer generation.

---

## Request Flow: Question Answering

Question answering starts when a client calls:

```text
POST /v1/ask
```

Example request:

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

The question-answering flow is:

```text
/v1/ask
    |
    v
answer_question()
    |
    v
hybrid_retriever_query()
    |
    v
rerank_results()
    |
    v
answer_with_claude_sonnet()
    |
    v
evaluate_response()
    |
    v
AskResponse
```

---

## Hybrid Retrieval

The hybrid retriever runs two retrieval paths:

1. dense retrieval
2. sparse retrieval

The dense path embeds the query using OpenAI embeddings and searches the `text-dense` vector.

The sparse path converts the query into a SPLADE sparse vector and searches the `text-sparse` vector.

Both searches are sent to Qdrant as prefetch queries.

The results are then combined with Reciprocal Rank Fusion.

---

## Reciprocal Rank Fusion

Reciprocal Rank Fusion, or RRF, combines multiple ranked lists into one fused ranking.

In this project, the fused inputs are:

1. dense retrieval results
2. sparse retrieval results

Configurable parameters include:

```text
top_k
prefetch_k
dense_weight
sparse_weight
rrf_k
```

Default values:

```text
top_k = 20
prefetch_k = 20
dense_weight = 1.0
sparse_weight = 1.0
rrf_k = 60
```

The dense and sparse weights allow the caller to tune retrieval behavior.

For semantic questions, dense retrieval can be weighted more heavily:

```json
{
  "dense_weight": 1.5,
  "sparse_weight": 0.5
}
```

For exact-keyword questions, sparse retrieval can be weighted more heavily:

```json
{
  "dense_weight": 0.5,
  "sparse_weight": 1.5
}
```

---

## Reranking Layer

Hybrid retrieval returns a broad candidate set.

The reranker improves precision by scoring each candidate chunk against the original user question.

The reranker uses a cross-encoder model.

Default model:

```text
cross-encoder/ms-marco-MiniLM-L6-v2
```

For each candidate, the reranker scores this pair:

```text
(question, chunk_text)
```

The score is stored in document metadata as:

```text
cross_score
```

The final top reranked chunks are passed to the generation layer.

Default number of reranked chunks:

```text
rerank_top_k = 5
```

---

## Generation Layer

The generation layer sends the reranked chunks to Claude.

The prompt is designed to enforce grounded answers.

The model is instructed to:

1. answer only from provided context
2. cite every factual claim
3. avoid citing unsupported sources
4. avoid outside knowledge
5. avoid guessing
6. answer only the supported part when context is partial
7. explicitly state when the context does not contain enough information

When the context is insufficient, the model is instructed to respond:

```text
The provided context does not contain enough information to answer that question.
```

---

## Citation-Enabled Context

Retrieved chunks are formatted as citation-enabled search-result blocks.

Each chunk includes:

```json
{
  "type": "search_result",
  "content": [
    {
      "type": "text",
      "text": "Retrieved chunk text..."
    }
  ],
  "title": "README.md",
  "source": "Github repository documentation or code",
  "citations": {
    "enabled": true
  }
}
```

This lets the model produce source-grounded answers with citation support.

---

## Evaluation Layer

After answer generation, the response is sent to an evaluation layer.

The evaluator produces structured output with:

```json
{
  "valid_citations": [0, 2],
  "invalid_citations": [1],
  "retrieval_confidence": 0.86,
  "answer_completeness": 0.78
}
```

The evaluator checks:

1. whether citations directly support the claims they are attached to
2. whether the retrieved search results were relevant to the original question
3. whether the answer completely addressed the question

This gives the API a quality signal beyond simply returning generated text.

---

## Response Assembly

The final `/v1/ask` response includes:

```json
{
  "question": "User question",
  "answer": "Generated answer with citations",
  "sources": [
    {
      "chunk_id": "chunk-id",
      "source_path": "README.md",
      "repo_url": "https://github.com/owner/repo",
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

The `sources` array exposes the retrieved and reranked chunks used as generation context.

The `confidence` object exposes evaluator output.

---

## Document Listing Flow

The `/v1/documents` endpoint helps verify ingestion.

It accepts:

```text
collection_name
include_chunk_ids
```

The service then:

1. checks whether the Qdrant collection exists
2. scrolls Qdrant points
3. reads payload metadata
4. groups chunks by `source_path`
5. counts chunks per source document
6. returns document-level summaries

Example response:

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
      "section_headings": ["Overview", "Usage"],
      "chunk_count": 8,
      "chunk_ids": [],
      "text_preview": "First 300 characters..."
    }
  ]
}
```

This endpoint is useful for confirming that a repository has been indexed before asking questions against it.

---

## Service Boundaries

The project is organized around clear service boundaries.

```text
api/
    HTTP routing, request validation, response models, orchestration

document_ingestion/
    repository loading, filtering, chunking, embedding, sparse encoding

retrieval_engine/
    dense retrieval, sparse retrieval, RRF fusion, reranking

generation/
    grounded prompt construction and Claude invocation

evaluation/
    citation and answer quality evaluation
```

This separation makes it easier to modify one layer without rewriting the entire pipeline.

---

## Data Flow Summary

### Ingestion Path

```text
GitHub URL
  -> clone repository
  -> filter documentation files
  -> extract metadata
  -> split into chunks
  -> generate dense vectors
  -> generate sparse vectors
  -> create Qdrant points
  -> upsert into collection
```

### Query Path

```text
User question
  -> dense query embedding
  -> sparse query encoding
  -> Qdrant dense retrieval
  -> Qdrant sparse retrieval
  -> RRF fusion
  -> cross-encoder reranking
  -> Claude grounded generation
  -> citation evaluation
  -> JSON response
```

### Document Inspection Path

```text
Collection name
  -> Qdrant collection existence check
  -> scroll stored points
  -> group payloads by source_path
  -> count documents and chunks
  -> return document summaries
```

---

## Why Hybrid Search?

Dense retrieval and sparse retrieval solve different problems.

Dense retrieval is good at semantic similarity.

Example:

```text
Question:
"How do I start the app locally?"

Relevant documentation:
"Run uvicorn api.main:app --host 0.0.0.0 --port 8080"
```

Sparse retrieval is good at exact lexical matching.

Example:

```text
Question:
"What does QDRANT_URL configure?"

Relevant documentation:
"QDRANT_URL=your-qdrant-url"
```

A dense-only retriever may miss exact terms or rank them too low. A sparse-only retriever may miss paraphrased concepts.

Hybrid retrieval gives the system both semantic coverage and exact identifier matching.

---

## Why Reranking?

Hybrid retrieval is optimized for recall. It gathers a broad candidate set from dense and sparse search.

However, the generation model should receive the most relevant chunks possible.

The cross-encoder reranker improves precision by directly comparing the question with each candidate chunk.

This helps:

* reduce irrelevant context
* improve answer grounding
* improve citation quality
* reduce hallucination risk
* use the context window more efficiently

---

## Why Citation Evaluation?

Many RAG systems return citations without checking whether those citations actually support the generated claims.

This project adds a post-generation evaluation step to inspect citation support.

The evaluator is designed to identify:

* citations that directly support claims
* citations that do not support claims
* weak retrieval results
* incomplete answers

This turns citation quality into a visible output instead of a hidden assumption.

---

## Why Qdrant?

Qdrant is used because it supports:

* named dense vectors
* sparse vectors
* payload metadata
* vector search over collections
* hybrid retrieval patterns
* scrolling over stored points for inspection endpoints

This makes it a good fit for storing both dense and sparse document representations in one retrieval backend.

---

## Why FastAPI?

FastAPI is used because it provides:

* Pydantic request and response validation
* automatic OpenAPI documentation
* clean route definitions
* async endpoint support
* easy local development with Uvicorn
* straightforward container deployment

The API layer remains small while service modules perform the heavier pipeline work.

---

## Current Limitations

The current architecture is functional, but several parts can be improved for production use.

### Ingestion jobs

Ingestion currently runs as a FastAPI background task.

This is acceptable for local development and demos, but large repositories should use a dedicated job system such as:

* Cloud Run Jobs
* Cloud Tasks
* Pub/Sub
* Celery
* RQ

### Job status tracking

The API currently returns `"queued"` for ingestion, but does not expose a persistent job ID or job status endpoint.

A production version should add:

* ingestion job IDs
* job states
* error tracking
* retry behavior
* indexing timestamps

### Latency

The `/v1/ask` endpoint performs retrieval, reranking, generation, and evaluation in one request path.

This can be slow because it may involve:

* OpenAI query embedding
* SPLADE query encoding
* Qdrant retrieval
* cross-encoder inference
* Claude generation
* Claude-based evaluation

Potential improvements:

* make evaluation optional
* reduce `top_k`
* reduce `rerank_top_k`
* cache query embeddings
* cache frequent answers
* use a smaller reranker
* stream generation results

### Security

The current API does not enforce authentication.

Before exposing the service publicly, add:

* authentication
* rate limiting
* request validation
* repository allowlists
* stricter CORS settings
* abuse monitoring

### Multi-repository search

The current design assumes users query a specific Qdrant collection.

A future version could support:

* searching multiple repositories
* organization-level search
* repository filters
* source-type filters
* incremental re-indexing

---

## Future Architecture Improvements

Planned improvements include:

1. **Dedicated ingestion workers**

   Move indexing out of the API runtime and into a worker or job service.

2. **Persistent job tracking**

   Store job status, timestamps, errors, and collection metadata.

3. **Streaming generation**

   Stream answer tokens back to the client while citation evaluation runs separately.

4. **Optional evaluation mode**

   Allow users to skip citation evaluation for lower-latency responses.

5. **Dashboard**

   Add a frontend for asking questions, inspecting retrieved chunks, and comparing dense-only vs. hybrid retrieval.

6. **Retrieval debugging**

   Return or visualize dense scores, sparse scores, fused scores, and reranker scores.

7. **Evaluation suite**

   Add a golden Q&A dataset and regression tests for retrieval quality, faithfulness, and citation accuracy.

8. **Incremental indexing**

   Re-index only changed files instead of rebuilding entire repositories.

9. **Private repository support**

   Add GitHub authentication for private repositories.

10. **Multi-repository search**

Support cross-repository and organization-level documentation search.

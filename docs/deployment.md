# Deployment

This document describes how to run and deploy the GitHub Documentation RAG Pipeline.

The service is packaged as a FastAPI application and can run locally, inside Docker, with Docker Compose, or on a managed container runtime such as Google Cloud Run.

---

## Summary

The deployment model is container-first.

For local development, run the API directly with Uvicorn or Docker Compose.

For production-style deployment, run the FastAPI app on Cloud Run, store vectors in Qdrant Cloud, keep secrets in Secret Manager, restrict CORS, and move long-running ingestion into a dedicated job or worker system.

The minimum deployable stack is:

```text
FastAPI container
Qdrant instance
OpenAI API key
Anthropic API key
```

The recommended production stack is:

```text
FastAPI API service
Dedicated ingestion worker
Task queue or job runner
Qdrant Cloud
Secret Manager
Frontend dashboard
```

---

## Deployment Overview

The application exposes a FastAPI API for:

* health checks
* GitHub repository ingestion
* question answering over indexed documentation
* indexed document inspection

The service depends on external model and vector database providers:

* OpenAI for dense embeddings
* Anthropic Claude for answer generation and evaluation
* Qdrant for dense and sparse vector storage

At runtime, the API requires environment variables for these services.

---

## Runtime Requirements

The application requires:

* Python 3.11+
* Git
* Docker, if running containerized
* OpenAI API key
* Anthropic API key
* Qdrant URL
* Qdrant API key, if using Qdrant Cloud or a secured Qdrant instance

The application also loads local transformer models for:

* SPLADE sparse encoding
* cross-encoder reranking

Because of this, the container should have enough CPU and memory for model loading and inference.

Recommended minimum for deployed containers:

```text
CPU:    1 vCPU
Memory: 4 GiB
```

For larger repositories or faster ingestion, allocate more CPU and memory.

---

## Environment Variables

| Variable            | Required | Description                                               |
| ------------------- | -------: | --------------------------------------------------------- |
| `OPENAI_API_KEY`    |      Yes | Used to generate dense embeddings                         |
| `ANTHROPIC_API_KEY` |      Yes | Used for Claude answer generation and citation evaluation |
| `QDRANT_URL`        |      Yes | URL of the Qdrant instance                                |
| `QDRANT_API_KEY`    |  Usually | API key for Qdrant Cloud or a secured Qdrant instance     |

Example `.env` file:

```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
QDRANT_URL=https://your-qdrant-cluster-url
QDRANT_API_KEY=your-qdrant-api-key
```

Do not commit `.env` files or API keys to Git.

---

## Local Development

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

---

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 3. Set environment variables

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
QDRANT_URL=your-qdrant-url
QDRANT_API_KEY=your-qdrant-api-key
```

Or export them directly in your shell:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export QDRANT_URL="your-qdrant-url"
export QDRANT_API_KEY="your-qdrant-api-key"
```

---

### 4. Start the API locally

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

---

### 5. Verify the service

```bash
curl "http://localhost:8080/health"
```

Expected response:

```json
{
  "status": "ok"
}
```

---

## Docker Deployment

### Build the Docker image

From the project root:

```bash
docker build -t github-docs-rag .
```

---

### Run the container

```bash
docker run --rm -p 8080:8080 \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  -e QDRANT_URL="$QDRANT_URL" \
  -e QDRANT_API_KEY="$QDRANT_API_KEY" \
  github-docs-rag
```

---

### Verify the container

```bash
curl "http://localhost:8080/health"
```

Expected response:

```json
{
  "status": "ok"
}
```

---

## Docker Compose

Docker Compose is the easiest way to run the API with local environment variables.

### Start the service

```bash
docker compose up --build
```

The API will be available at:

```text
http://localhost:8080
```

---

### Stop the service

```bash
docker compose down
```

---

### Compose environment variables

The Compose file passes these variables into the API container:

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

This allows cloned repositories and local ingestion artifacts to persist outside the container lifecycle.

---

## Qdrant Deployment Options

The application expects Qdrant to be available through `QDRANT_URL`.

You can use either:

1. Qdrant Cloud
2. A self-hosted Qdrant instance
3. A local Qdrant container for development

---

## Option 1: Qdrant Cloud

For production or portfolio deployment, Qdrant Cloud is usually the simplest option.

Set:

```bash
QDRANT_URL=https://your-qdrant-cloud-cluster-url
QDRANT_API_KEY=your-qdrant-cloud-api-key
```

Advantages:

* persistent external vector storage
* no local disk dependency
* easier Cloud Run deployment
* less container complexity

Recommended for production demos.

---

## Option 2: Local Qdrant Container

For local development, you can run Qdrant separately:

```bash
docker run -p 6333:6333 -p 6334:6334 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage" \
  qdrant/qdrant
```

Then set:

```bash
QDRANT_URL=http://localhost:6333
```

If your Qdrant instance does not require authentication, `QDRANT_API_KEY` may be omitted depending on your configuration.

---

## Option 3: Add Qdrant to Docker Compose

For local-only development, you can extend `docker-compose.yaml` to include a Qdrant service.

Example:

```yaml
services:
  api:
    build: .
    ports:
      - "8080:8080"
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      QDRANT_URL: http://qdrant:6333
      QDRANT_API_KEY: ${QDRANT_API_KEY}
    volumes:
      - ./data:/app/data
    depends_on:
      - qdrant

  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_storage:/qdrant/storage
```

This is useful for local development, but for production deployment, prefer an external managed Qdrant instance.

---

## Google Cloud Run Deployment

Cloud Run is a good deployment target for the FastAPI API because it runs containerized HTTP services.

Recommended production split:

```text
Cloud Run Service:
  handles /health, /v1/ask, /v1/documents

Cloud Run Job or worker:
  handles long-running /v1/ingest work

Qdrant Cloud:
  stores dense and sparse vectors
```

The current implementation can run as a single Cloud Run service, but long ingestion jobs may exceed request limits or tie up API resources.

---

## Deploying the API to Cloud Run

### 1. Set project variables

```bash
PROJECT_ID="your-google-cloud-project-id"
REGION="us-west1"
SERVICE_NAME="github-docs-rag-api"
IMAGE_NAME="github-docs-rag"
```

---

### 2. Configure gcloud

```bash
gcloud config set project "$PROJECT_ID"
gcloud config set run/region "$REGION"
```

---

### 3. Build and submit the image

```bash
gcloud builds submit --tag "gcr.io/$PROJECT_ID/$IMAGE_NAME"
```

---

### 4. Deploy to Cloud Run

```bash
gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/$PROJECT_ID/$IMAGE_NAME" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 900 \
  --set-env-vars OPENAI_API_KEY="$OPENAI_API_KEY" \
  --set-env-vars ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
  --set-env-vars QDRANT_URL="$QDRANT_URL" \
  --set-env-vars QDRANT_API_KEY="$QDRANT_API_KEY"
```

For a public portfolio demo, `--allow-unauthenticated` is convenient but not secure. For production use, require authentication.

---

### 5. Test the deployed service

After deployment, Cloud Run prints a service URL.

Set it as a shell variable:

```bash
SERVICE_URL="https://your-cloud-run-service-url"
```

Test health:

```bash
curl "$SERVICE_URL/health"
```

Expected response:

```json
{
  "status": "ok"
}
```

---

## Calling the Deployed API

### Ingest a repository

```bash
curl -X POST "$SERVICE_URL/v1/ingest" \
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

---

### List indexed documents

```bash
curl "$SERVICE_URL/v1/documents?collection_name=quwin_UnderTheGun"
```

---

### Ask a question

```bash
curl -X POST "$SERVICE_URL/v1/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What does this documentation say?",
    "collection_name": "quwin_UnderTheGun"
  }'
```

---

## Recommended Cloud Run Settings

For the API service:

| Setting       |      Recommended Value | Reason                                                                     |
| ------------- | ---------------------: | -------------------------------------------------------------------------- |
| CPU           |          `2` or higher | SPLADE and reranker inference are CPU-heavy                                |
| Memory        |        `4Gi` or higher | Transformer models require significant memory                              |
| Timeout       | `300` to `900` seconds | RAG responses may involve retrieval, reranking, generation, and evaluation |
| Concurrency   |            `1` to `10` | Lower concurrency reduces memory pressure                                  |
| Min instances |             `0` or `1` | Use `1` to reduce cold starts                                              |
| Max instances |        Based on budget | Controls cost and scaling behavior                                         |

For ingestion-heavy workloads, prefer running ingestion outside the API request path.

---

## Handling Long-Running Ingestion

The current `/v1/ingest` endpoint uses a FastAPI background task.

That works for local development and small repositories, but it has limitations:

* no persistent job ID
* no durable retry behavior
* no status endpoint
* possible timeout issues
* work may be interrupted if the container shuts down
* API CPU and memory are shared with ingestion

For production, move ingestion to a dedicated job system.

Recommended options:

* Cloud Run Jobs
* Cloud Tasks
* Pub/Sub with a worker service
* Celery
* RQ

---

## Cloud Run Jobs Pattern

A Cloud Run Job is a good fit when ingestion is long-running and does not need to hold an HTTP request open.

Recommended architecture:

```text
Client
  -> API service
  -> create ingestion job request
  -> Cloud Run Job indexes repository
  -> Qdrant stores vectors
  -> /v1/documents confirms indexed output
```

In this pattern, ingestion should be moved into a command-line entry point such as:

```bash
python -m jobs.ingest_repo \
  --repo-url "https://github.com/quwin/UnderTheGun" \
  --branch main \
  --recursive-chunking true
```

A future job runner could call the same `ingest_repo()` service function used by the API.

---

## Cloud Tasks Pattern

Cloud Tasks is a good fit when you want HTTP-based queueing with retries.

Recommended architecture:

```text
Client
  -> API service
  -> enqueue Cloud Task
  -> worker endpoint receives task
  -> worker runs ingestion
  -> Qdrant stores vectors
```

In this pattern, split ingestion into a protected worker route such as:

```text
POST /internal/ingest
```

The public `/v1/ingest` route should enqueue a task and return a job ID.

The private worker route should perform the actual indexing.

---

## Secret Management

For local development, `.env` files are acceptable.

For deployed environments, prefer a managed secret store.

On Google Cloud, use Secret Manager for:

* `OPENAI_API_KEY`
* `ANTHROPIC_API_KEY`
* `QDRANT_API_KEY`

Recommended approach:

1. Create secrets in Secret Manager.
2. Grant the Cloud Run service account access.
3. Mount or inject secrets as environment variables.
4. Avoid storing secrets in deployment scripts or source control.

Example Cloud Run deployment with secrets:

```bash
gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/$PROJECT_ID/$IMAGE_NAME" \
  --region "$REGION" \
  --memory 4Gi \
  --cpu 2 \
  --timeout 900 \
  --set-env-vars QDRANT_URL="$QDRANT_URL" \
  --set-secrets OPENAI_API_KEY=OPENAI_API_KEY:latest \
  --set-secrets ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest \
  --set-secrets QDRANT_API_KEY=QDRANT_API_KEY:latest
```

---

## CORS

The current API allows all origins.

That is convenient for local development, but too permissive for production.

For production, restrict CORS to your frontend domain.

Example:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Health Checks

The service exposes:

```text
GET /health
```

Use it for:

* local verification
* deployment smoke tests
* uptime checks
* load balancer health checks

Example:

```bash
curl "$SERVICE_URL/health"
```

Expected response:

```json
{
  "status": "ok"
}
```

---

## Verifying Ingestion

After calling `/v1/ingest`, use `/v1/documents` to check whether Qdrant contains indexed source documents.

Example:

```bash
curl "$SERVICE_URL/v1/documents?collection_name=quwin_UnderTheGun"
```

A successful ingestion should return a response with:

```json
{
  "collection_name": "quwin_UnderTheGun",
  "document_count": 1,
  "total_chunks": 8,
  "documents": []
}
```

The exact document count, chunk count, and document list depend on the repository.

If the collection does not exist yet, ingestion may still be running or may have failed.

---

## Logging

For local development, standard output logs are usually enough.

For production, log the following events:

* request start and end
* repository URL submitted for ingestion
* resolved branch
* number of documents loaded
* number of chunks created
* number of points upserted
* Qdrant collection name
* retrieval timing
* reranking timing
* generation timing
* evaluation timing
* errors from Git, OpenAI, Anthropic, Qdrant, and model loading

Avoid logging:

* API keys
* full user secrets
* private repository tokens
* large retrieved chunks unless needed for debugging

---

## Performance Considerations

### Ingestion Performance

Ingestion is usually the slowest workflow.

Primary cost drivers:

* repository size
* number of documentation files
* recursive chunking
* OpenAI embedding latency
* SPLADE sparse-vector computation
* Qdrant upsert latency
* CPU allocation
* memory allocation

Ways to improve ingestion speed:

* use smaller repositories during testing
* disable recursive chunking during initial experiments
* increase CPU allocation
* batch sparse-vector computation
* cache model loading
* avoid repeated full re-indexing
* move ingestion into a dedicated worker or job
* use job status tracking

---

### Query Performance

Question answering involves multiple steps:

1. dense query embedding
2. sparse query encoding
3. Qdrant hybrid retrieval
4. cross-encoder reranking
5. Claude answer generation
6. Claude citation evaluation

Ways to reduce latency:

* lower `top_k`
* lower `rerank_top_k`
* skip citation evaluation for fast mode
* cache frequent queries
* cache query embeddings
* use a smaller reranker
* stream answer generation
* allocate more CPU and memory
* separate answer generation and evaluation

---

## Storage Considerations

The service stores cloned repositories under:

```text
data/repos/
```

When running with Docker Compose, local `./data` is mounted into the container at:

```text
/app/data
```

In production, do not rely on ephemeral container storage for long-term source data.

Recommended production storage pattern:

* Qdrant stores all indexed vectors and metadata.
* Container disk is treated as temporary.
* Repositories are cloned as needed during ingestion.
* Long-term ingestion metadata is stored in a database, if job tracking is added.

---

## Security Considerations

Before exposing the API publicly, add protections.

### Protect `/v1/ingest`

The ingestion endpoint is expensive because it can trigger:

* Git clone operations
* documentation parsing
* embedding calls
* sparse encoding
* Qdrant writes

Recommended protections:

* authentication
* rate limiting
* repository allowlist
* request validation
* job quotas
* maximum repository size
* maximum file count
* maximum chunk count

---

### Protect API Keys

Never expose these values to the client:

* OpenAI API key
* Anthropic API key
* Qdrant API key

Only the backend should access these secrets.

---

### Restrict CORS

Do not use wildcard CORS in production.

Use your deployed frontend origin instead.

---

### Validate Repository URLs

Only allow intended repository sources.

Recommended rules:

* require HTTPS
* require `github.com`
* reject local file paths
* reject SSH URLs
* reject arbitrary domains
* optionally use repository owner allowlists
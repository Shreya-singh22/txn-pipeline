cat > README.md << 'EOF'
# AI-Powered Transaction Processing Pipeline

An async backend pipeline that ingests messy financial transaction CSVs, cleans the data, detects anomalies, classifies transactions using an LLM (Gemini), and produces a narrative risk summary — all via a job-based polling API.

## Tech Stack

- **API**: FastAPI
- **Database**: PostgreSQL
- **Queue**: Celery + Redis
- **LLM**: Google Gemini (gemini-2.0-flash)
- **Containerization**: Docker + Docker Compose

## Architecture

```
Client → FastAPI (api) → Redis (queue) → Celery (worker) → PostgreSQL
                                              ↓
                                        Gemini LLM API
```

- `api`: handles HTTP requests, enqueues jobs
- `worker`: picks up jobs, runs the processing pipeline
- `redis`: message broker between api and worker
- `db`: stores jobs, transactions, and summaries

## Processing Pipeline

1. **Data Cleaning** — normalize dates to ISO 8601, strip `$` from amounts, uppercase status/currency, fill blank categories with `Uncategorised`, remove exact duplicate rows
2. **Anomaly Detection**:
   - Flags transactions > 3× the account's median amount
   - Flags USD transactions at domestic-only merchants (Swiggy, Ola, IRCTC, Zomato, etc.)
   - Flags transactions with "SUSPICIOUS" in notes
3. **LLM Classification** — batches all `Uncategorised` rows into a single Gemini call, assigns one of: Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other
4. **LLM Narrative Summary** — single call returns total spend by currency, top 3 merchants, anomaly count, 2–3 sentence narrative, and risk level (low/medium/high). Falls back to a computed statistical summary if the LLM call fails.
5. **Retry Logic** — LLM calls retry up to 3× with exponential backoff (via `tenacity`). On total failure, affected rows are marked `llm_failed=true` and processing continues — the job never fails due to LLM issues.

## Setup

### Prerequisites
- Docker Desktop installed and running
- A free Gemini API key from [aistudio.google.com](https://aistudio.google.com)

### Steps

```bash
git clone <your-repo-url>
cd alemeno

cp .env.example .env
# edit .env and paste your GEMINI_API_KEY

docker compose up --build
```

The API will be available at `http://localhost:8000`. Interactive docs (Swagger UI) at `http://localhost:8000/docs`.

## Environment Variables (`.env.example`)

| Variable | Description |
|---|---|
| `POSTGRES_USER` | Postgres username |
| `POSTGRES_PASSWORD` | Postgres password |
| `POSTGRES_DB` | Postgres database name |
| `DATABASE_URL` | Full SQLAlchemy connection string |
| `REDIS_URL` | Redis connection string |
| `GEMINI_API_KEY` | Your Gemini API key |
| `UPLOAD_DIR` | Directory inside container for uploaded files |

## API Endpoints

### 1. Upload a CSV
```bash
curl -X POST http://localhost:8000/jobs/upload \
  -F "file=@transactions.csv"
```
Response:
```json
{"job_id": "...", "message": "Job enqueued", "status": "pending"}
```

### 2. Check job status
```bash
curl http://localhost:8000/jobs/<job_id>/status
```
Returns status (`pending`/`processing`/`completed`/`failed`), row counts, and a summary once completed.

### 3. Get full results
```bash
curl http://localhost:8000/jobs/<job_id>/results
```
Returns all cleaned transactions, the list of flagged anomalies, category-wise spend breakdown, and the narrative summary.

### 4. List all jobs
```bash
curl http://localhost:8000/jobs
curl "http://localhost:8000/jobs?status=completed"
```

## Project Structure

```
alemeno/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── transactions.csv
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── routers/
│   │   └── jobs.py
│   └── worker/
│       ├── celery_app.py
│       ├── tasks.py
│       ├── cleaning.py
│       ├── anomaly.py
│       └── llm.py
```

## Scaling Considerations (at 100× load)

- **DB connection pool saturation** → use PgBouncer for connection pooling
- **Single Redis instance** → move to Redis Cluster for broker HA
- **LLM rate limits** → batch more aggressively, add response caching for repeated merchant/category patterns
- **Worker memory/throughput** → horizontal scaling of Celery workers via Kubernetes, separate queues for classification vs. narrative tasks
EOF
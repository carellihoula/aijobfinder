# AILFJ — AI-Powered Job Matching API

Analyzes a PDF resume and returns the most relevant job offers with a detailed matching report.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI (API)                       │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │   LangGraph Pipeline │
              └──────────┬──────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
   pdf_parser      cv_structurer   cortex_search
                                         │
                              ┌──────────┴──────────┐
                              │ hit                 │ miss
                              ▼                     ▼
                        llm_reranker       keyword_extractor
                              │                     │
                        report_generator      job_search
                                                    │
                                              cortex_feed ──► Cortex DB
                                                    │         (background)
                                          embeddings_filter
                                                    │
                                            llm_reranker
                                                    │
                                          report_generator
```

### Cortex — Centralized Job Vector Index

The **Cortex** is a PostgreSQL + pgvector database that centralizes all jobs collected from external providers (JSearch, Adzuna). It is continuously populated by Celery workers and queried by vector similarity on every CV analysis — with no external API call needed.

```
Cron (nightly)  → Celery worker → fetch providers → embed → store in Cortex
User request    → embed CV      → pgvector search → llm_reranker → report
```

---

## Tech Stack

| Component | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| AI Pipeline | LangGraph (StateGraph) |
| LLM | OpenAI GPT-4o-mini |
| Embeddings | OpenAI text-embedding-3-small |
| Main database | SQLite (dev) / PostgreSQL (prod) |
| Cortex (vector DB) | PostgreSQL + pgvector |
| Queue / Cron | Celery + Redis + Celery Beat |
| Worker monitoring | Flower |
| Job providers | JSearch (RapidAPI) + Adzuna |

---

## LangGraph Pipeline

```
pdf_parser          Extract raw text from PDF (pdfplumber)
    ↓
cv_structurer       Parse CV → CVSchema JSON (LLM structured output)
    ↓
cortex_search       Embed CV → pgvector similarity search (TOP 100)
    ↓
  [hit]─────────────────────────────────────────┐
  [miss]                                        │
    ↓                                           │
keyword_extractor   Generate search queries     │
    ↓               from CV (LLM)               │
job_search          Parallel calls to           │
    ↓               JSearch + Adzuna            │
cortex_feed         Queue found jobs →          │
    ↓               into Cortex (Celery bg)     │
embeddings_filter   Cosine similarity filter    │
    ↓               ←────────────────────────── ┘
llm_reranker        Score 0–10 per offer (LLM, 2 parallel batches)
    ↓
report_generator    Final Markdown report (LLM)
```

**Retry loop**: if `job_search` returns 0 results, `prepare_retry` progressively relaxes filters (drop location → drop contract_type) and regenerates different keywords (max 2 attempts).

---

## Installation

### Prerequisites

- Python 3.12+
- Redis
- PostgreSQL with `pgvector` extension (for the Cortex)

### Setup

```bash
git clone <repo>
cd AILFJ

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### Configuration

Copy `.env.example` to `.env` and fill in the required values:

```bash
cp .env.example .env
```

```env
# App
DEBUG=false
SECRET_KEY=your-secret-key

# Main database
DATABASE_URL=sqlite+aiosqlite:///./ailfj.db

# Cortex (PostgreSQL + pgvector)
CORTEX_DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/postgres

# Redis (Celery)
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Job providers
JSEARCH_API_KEY=...
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...
ADZUNA_COUNTRY=fr
```

---

## Running

### Development

```bash
# API
uvicorn app.main:app --reload

# Celery worker
celery -A app.worker.celery_app worker --loglevel=info

# Celery Beat (cron scheduler)
celery -A app.worker.celery_app beat --loglevel=info

# Flower (optional worker monitoring UI)
celery -A app.worker.celery_app flower --port=5555
```

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
celery -A app.worker.celery_app worker --concurrency=2 --loglevel=warning
celery -A app.worker.celery_app beat --loglevel=warning
```

---

## Deployment Strategy

Before going live, bootstrap the Cortex so it has enough jobs to serve users:

```bash
# 1. Start the infrastructure (API + Celery)
# 2. Trigger initial ingestion per domain
curl -X POST "https://api.yourdomain.com/cortex/ingest/full?domain=tech_software" \
  -H "Authorization: Bearer <token>"

curl -X POST "https://api.yourdomain.com/cortex/ingest/full?domain=tech_data" \
  -H "Authorization: Bearer <token>"

# ... repeat for all domains

# 3. Check fill level
curl "https://api.yourdomain.com/cortex/stats" \
  -H "Authorization: Bearer <token>"

# 4. Go live once active_jobs count is sufficient
```

The Cortex then refreshes automatically every night at 2 AM via Celery Beat.

---

## API Reference

### Auth

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create an account |
| `POST` | `/auth/login` | Obtain a JWT token |

### CV Analysis

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/analysis/upload` | Upload PDF and start analysis |
| `GET` | `/analysis/{id}` | Retrieve analysis results |

**Upload parameters**:

```
file              PDF resume (required)
keywords          Additional keywords (optional, comma-separated)
locations         Target cities (optional)
contract_type     cdi | cdd | stage | alternance | freelance | temps_partiel
remote            true | false
date_posted       today | 3days | week | month
experience_level  junior | mid | senior
```

### Cortex

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/cortex/ingest` | Custom ingestion (synchronous) |
| `POST` | `/cortex/ingest/full` | Seed keyword ingestion (Celery) |
| `GET` | `/cortex/stats` | Number of active jobs in the Cortex |
| `GET` | `/cortex/domains` | Available domains and keyword counts |
| `DELETE` | `/cortex/jobs/cleanup` | Deactivate stale jobs |

### Scheduled Celery Tasks

| Task | Schedule | Description |
|---|---|---|
| `full_ingestion` | Nightly at **2:00 AM** | Full ingestion across all domains |
| `cleanup_old_jobs` | Every **Sunday at 3:00 AM** | Deactivate jobs older than 30 days |

---

## Project Structure

```
app/
├── main.py                    # FastAPI app + lifespan
├── config.py                  # Settings (pydantic-settings)
│
├── auth/                      # JWT authentication
├── users/                     # User management
├── cv/                        # CV model
├── analysis/                  # Analyses and results
│
├── pipeline/
│   ├── graph.py               # LangGraph StateGraph
│   ├── state.py               # PipelineState (TypedDict)
│   └── nodes/
│       ├── pdf_parser.py
│       ├── cv_structurer.py
│       ├── cortex_search.py   # Cortex vector search
│       ├── keyword_extractor.py
│       ├── job_search.py      # JSearch + Adzuna
│       ├── cortex_feed.py     # Cortex self-enrichment (fire-and-forget)
│       ├── prepare_retry.py   # Retry loop + filter relaxation
│       ├── embeddings_filter.py
│       ├── llm_reranker.py
│       └── report_generator.py
│
├── cortex/
│   ├── db.py                  # PostgreSQL + pgvector connection
│   ├── models.py              # cortex_jobs table
│   ├── service.py             # CRUD + vector search
│   ├── ingestion.py           # Ingestion pipeline
│   ├── enricher.py            # Seniority detection (LLM batch)
│   ├── seeds.py               # 130+ keywords across 16 domains (ROME/ESCO)
│   ├── schemas.py
│   └── router.py
│
└── worker/
    ├── celery_app.py          # Celery config + Beat schedule
    └── tasks.py               # Tasks: full_ingestion, cortex_feed, cleanup
```

---

## Cortex Domains

`tech_software` · `tech_data` · `tech_infra` · `tech_product` · `tech_design` · `tech_security` · `finance_banking` · `marketing_sales` · `hr_legal` · `engineering_industry` · `supply_chain` · `healthcare` · `education_research` · `consulting_management` · `construction_real_estate` · `communication_media`

Seed keywords derived from **ROME** (France Travail) and **ESCO** (European Commission) taxonomies.

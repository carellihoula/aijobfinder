# AILFJ — Claude Code Project Context

## What this project is
AI-powered CV-to-job matching API. User uploads a PDF CV → LangGraph pipeline extracts, searches, ranks jobs → returns a report + matched offers. Monorepo layout: API code in `backend/`, frontend in `ailfj-frontend/` (React + Vite + Tailwind v4), orchestrated together via the root `docker-compose.yml`.

---

## Stack
- **API**: FastAPI + Uvicorn
- **Pipeline**: LangGraph StateGraph (10 nodes)
- **LLM**: OpenAI GPT-4o-mini (`settings.OPENAI_MODEL`)
- **Embeddings**: text-embedding-3-small (`settings.OPENAI_EMBEDDING_MODEL`)
- **Main DB**: PostgreSQL via asyncpg (`DATABASE_URL`) — SQLAlchemy async
- **Cortex DB**: PostgreSQL + pgvector (`CORTEX_DATABASE_URL`) — same Supabase instance, different engine
- **Storage**: AWS S3 (`S3_BUCKET` + `AWS_*`) with local disk fallback
- **Queue**: Celery + Redis (`REDIS_URL`), scheduled with Celery Beat
- **Job providers**: JSearch (RapidAPI) + Adzuna
- **PDF generation**: reportlab (pure Python, no system deps)

---

## LangGraph pipeline flow

```
pdf_parser → cv_structurer → cortex_search
                                  ├─ hit  → embeddings_filter → llm_reranker → report_generator
                                  └─ miss → keyword_extractor → job_search
                                                 ↑                    ├─ found → cortex_feed → embeddings_filter → llm_reranker → report_generator
                                                 └── prepare_retry ←──┘ empty (max 2 retries)
```

- `cortex_feed` is fire-and-forget (Celery), self-enriches the Cortex from fallback results
- `prepare_retry` relaxes filters progressively: attempt 1 drops locations, attempt 2 drops contract_type too
- `keyword_extractor` uses a different prompt on retry (broader, excludes failed keywords)

---

## The Cortex
Centralized pgvector job index. Pre-populated by Celery crons, served to all users — no per-user API call needed.

- **`backend/app/cortex/`**: db, models, service, ingestion, enricher, seeds, router
- **`backend/app/cortex/seeds.py`**: 130+ seed keywords across 16 domains (ROME/ESCO-inspired)
- **`backend/app/cortex/esco.py`**: ESCO REST API client — NOT wired yet, run manually with `python -m app.cortex.esco`
- **Cron**: nightly at 2h (`full_ingestion`), cleanup Sundays at 3h (`cleanup_old_jobs`)
- CV embedding query: roles + skills + level only — no user_keywords (Cortex is generalist)

---

## Cover letter feature
- `POST /analysis/{id}/apply?job_index=0` → metadata JSON + document URLs
- `GET  /analysis/{id}/cv` → CV PDF (S3 presigned redirect or local stream)
- `POST /analysis/{id}/cover-letter?job_index=0` → PDF bytes

**Agent**: LLM produces `CoverLetterContent` (fully structured JSON with sender, recipient, paragraphs with purpose labels, tone, highlighted_skills, key_selling_point). Backends only consume this object.

**PDF backend** (`backend/app/cover_letter/backends/reportlab_backend.py`) — pure Python, no system deps.

---

## Storage abstraction (`backend/app/storage.py`)
- `S3_BUCKET` set → AWS S3 (`put_object`, presigned URLs)
- `S3_BUCKET` empty → local `UPLOAD_DIR/` fallback
- CV key format: `cvs/{user_id}/{cv_id}.pdf`
- `GET /analysis/{id}/cv` returns `RedirectResponse 302` to presigned URL (S3) or `StreamingResponse` (local)
- **Never cache the presigned URL client-side** — always call the endpoint for a fresh URL

---

## Key conventions
- **No French in code** — comments, strings, log messages all in English. French is only in seed keywords (job search terms for French boards) and LLM-generated cover letter text.
- **No mock data in prod** — `_MOCK_JOBS` in `job_search.py` only active when `settings.DEBUG = True`
- **No "Supabase" in code** — use `CORTEX_DATABASE_URL` everywhere, provider-agnostic
- **Cortex is generalist** — no user_keywords in cortex_search, CV profile only (roles/skills/level)
- **Skills extraction at runtime** — `llm_reranker` extracts matching/missing skills per job. `enricher.py` only handles seniority at ingestion.

---

## Running locally

All commands below run from `backend/`.

```bash
cd backend

# API
uvicorn app.main:app --reload

# Celery worker
celery -A app.worker.celery_app worker --loglevel=info

# Celery Beat (crons)
celery -A app.worker.celery_app beat --loglevel=info

# Flower (monitoring)
celery -A app.worker.celery_app flower --port=5555

# Test ESCO client (standalone)
python -m app.cortex.esco
```

Or via Docker Compose from the repo root (`docker-compose.yml`): `docker compose up --build -d` starts `frontend`, `api`, `celery-worker`, `celery-beat`, `flower`, and `redis` together.

## Database
- `DATABASE_URL` must use `postgresql+asyncpg://` (not psycopg2, not plain postgresql://)
- Port `5432` for direct connection (Supabase pooler on 6543 is incompatible with asyncpg prepared statements)
- `CORTEX_DATABASE_URL` uses `postgresql+asyncpg://` on port `5432`
- Tables created automatically on startup via `init_db()` and `init_cortex()`

---

## Frontend (`ailfj-frontend/`)
React 19 + Vite + Tailwind v4 + React Query + React Router v7.

Key files:
- `src/api/` — `client.ts` (axios, JWT interceptor), `analysis.ts`, `apply.ts`
- `src/pages/` — `UploadPage.tsx`, `AnalysisPage.tsx`, `LoginPage.tsx`, `RegisterPage.tsx`
- `src/components/` — `MatchCard.tsx`, `ApplyModal.tsx`, `FilterBar.tsx`, `MarkdownReport.tsx`
- `src/lib/designTypes.ts` — `DesignJobMatch` (includes `originalIndex` for backend job_index param)

Vite proxy: `/api` → `http://localhost:8000` (dev only)

Apply flow: click "Postuler" on MatchCard → `ApplyModal` opens → fetches cover letter PDF (`POST /cover-letter`) → shows CV iframe + cover letter iframe side by side → user downloads and applies manually.

---

## Important decisions already made
- **Celery + Redis** for prod crons (not APScheduler, not cron tab)
- **pgvector cosine similarity** for job search — seniority NOT detected by vector (cosine can't distinguish junior/senior with same tech stack), hence LLM enrichment at ingestion
- **ESCO keywords in French** (`language=fr`) — providers target French job boards
- **`originalIndex`** stored on `DesignJobMatch` — frontend filtered list index ≠ backend `analysis.matches` index
- **`extra = "ignore"`** on Settings — unknown `.env` vars silently ignored (e.g. `PGVECTOR_URL` legacy key)
- **S3 presigned URL expires** → frontend must never store it, always call `GET /analysis/{id}/cv` for a fresh one

---

## Files NOT to touch without care
- `backend/app/pipeline/graph.py` — full graph wiring, conditional edges
- `backend/app/cortex/db.py` — graceful disable if `CORTEX_DATABASE_URL` not set
- `backend/app/storage.py` — single place to swap S3 ↔ local; keep interface stable (`save_cv`, `read_file`, `get_presigned_url`, `delete_file`)
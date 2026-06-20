# AILFJ — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser (React + Vite)                                             │
│  ../ailfj-frontend                                                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP  /api  (Vite proxy → :8000)
┌────────────────────────────▼────────────────────────────────────────┐
│  FastAPI  :8000                                                      │
│  ├── /auth          JWT login / register                            │
│  ├── /analysis      upload CV, get results                          │
│  ├── /analysis/:id/cv              CV PDF (S3 redirect or stream)   │
│  ├── /analysis/:id/cover-letter    generated PDF                    │
│  ├── /analysis/:id/apply           metadata + document URLs         │
│  └── /cortex        ingest, stats, cleanup                          │
└───────┬──────────────────────────────┬──────────────────────────────┘
        │ BackgroundTask               │ async
        ▼                              ▼
┌───────────────┐             ┌────────────────────┐
│ LangGraph     │             │ Cover Letter Agent  │
│ Pipeline      │             │ (LLM → JSON → PDF) │
└───────┬───────┘             └────────────────────┘
        │
   ┌────┴──────────────────────────────────┐
   │                                       │
   ▼                                       ▼
┌──────────────────┐             ┌─────────────────────┐
│  Cortex          │             │  Job Providers       │
│  PostgreSQL +    │             │  JSearch + Adzuna    │
│  pgvector        │             └─────────────────────┘
│  (Supabase)      │
└──────────────────┘
        ▲
        │ Celery tasks
┌───────┴──────────┐      ┌──────────┐
│  Celery Worker   │◄─────│  Redis   │
│  + Celery Beat   │      └──────────┘
└──────────────────┘

┌──────────────────┐
│  AWS S3          │  CV PDFs  (cvs/{user_id}/{cv_id}.pdf)
└──────────────────┘
```

---

## LangGraph Pipeline

### State (`app/pipeline/state.py`)

```
PipelineState (TypedDict)
├── pdf_path          str          storage key (S3 or local)
├── cv_text           str          raw extracted text
├── cv_json           CVSchema     structured CV (JSON)
├── user_keywords     list[str]    user-provided extra keywords
├── keywords          list[str]    LLM-generated search queries
├── user_locations    list[str]    target cities (overrides CV)
├── contract_type     str          cdi|cdd|stage|alternance|freelance|temps_partiel
├── remote            bool
├── date_posted       str          today|3days|week|month
├── experience_level  str          junior|mid|senior
├── failed_keywords   list[str]    queries that returned 0 jobs
├── search_attempts   int          API fallback attempt counter
├── jobs              list[dict]   raw jobs from providers
├── filtered_jobs     list[dict]   after cosine similarity filter
├── matches           list[dict]   scored + ranked by LLM
└── final_report      str          markdown report
```

### Graph

```
pdf_parser
    │
cv_structurer
    │
cortex_search ──────────────────────────── hit (filtered_jobs not empty)
    │ miss                                      │
keyword_extractor ◄── prepare_retry             │
    │                      ▲                    │
job_search                 │ (0 jobs,           │
    ├── found              │  attempts < 2)     │
    │   cortex_feed ──► embeddings_filter ◄─────┘
    │                       │
    └── empty ──────────────┤
        (attempts == 2)     │
            │               ▼
            └──────► llm_reranker
                            │
                     report_generator
                            │
                           END
```

### Nodes

| Node | File | Role |
|---|---|---|
| `pdf_parser` | `nodes/pdf_parser.py` | pdfplumber → raw text via `storage.read_file` |
| `cv_structurer` | `nodes/cv_structurer.py` | LLM structured output → CVSchema JSON |
| `cortex_search` | `nodes/cortex_search.py` | Embed CV → pgvector cosine search TOP 100 |
| `keyword_extractor` | `nodes/keyword_extractor.py` | LLM generates search queries; retry prompt on `failed_keywords` |
| `job_search` | `nodes/job_search.py` | Parallel JSearch + Adzuna calls; mock only in DEBUG |
| `cortex_feed` | `nodes/cortex_feed.py` | Fire-and-forget Celery task → stores fallback jobs in Cortex |
| `prepare_retry` | `nodes/prepare_retry.py` | Accumulates `failed_keywords`, relaxes filters |
| `embeddings_filter` | `nodes/embeddings_filter.py` | Cosine similarity filter (scikit-learn) |
| `llm_reranker` | `nodes/llm_reranker.py` | Score 0–10 per job, 2 parallel batches of 30 |
| `report_generator` | `nodes/report_generator.py` | Final markdown report |

### Retry Logic

```
attempt 0 → 1 : clear user_locations
attempt 1 → 2 : clear user_locations + contract_type
attempt 2     : no more retries → report_generator (empty results)

keyword_extractor on retry:
  - generates DIFFERENT keywords (temperature=0.4)
  - excludes all failed_keywords from previous attempts
```

---

## The Cortex

Centralized vector job index shared across all users. Populated by background workers, not per-user API calls.

### Schema (`app/cortex/models.py`)

```
cortex_jobs
├── id            UUID PK
├── external_id   str  UNIQUE   dedup key (provider:job_id)
├── title         str
├── company       str
├── location      str
├── description   str
├── url           str
├── contract_type str
├── remote        bool
├── seniority     str           junior|mid|senior|""  (LLM-enriched at ingestion)
├── skills        list[str]     nullable (reserved for future)
├── embedding     Vector(1536)  text-embedding-3-small
├── source        str           jsearch|adzuna
├── is_active     bool
├── created_at    datetime
└── last_seen_at  datetime
```

### Search Query

CV query text = `roles + skills + level + experience_level` (no user_keywords — Cortex is generalist).

```sql
SELECT *, embedding <=> CAST(:embedding AS vector) AS distance
FROM cortex_jobs
WHERE is_active = true
  AND (:contract_type = '' OR contract_type = :contract_type)
  AND (:remote = false OR remote = true)
  AND (:seniority = '' OR seniority = '' OR seniority = :seniority)
ORDER BY distance ASC
LIMIT 100
```

### Ingestion Pipeline

```
SEED_KEYWORDS (130+ terms, 16 domains)
    │
run_full_ingestion()
    │
    ├── fetch from JSearch + Adzuna  (parallel per keyword)
    ├── dedup by external_id
    ├── enrich seniority (LLM batch, 30 jobs/call)
    ├── embed descriptions (text-embedding-3-small)
    └── upsert to cortex_jobs

Fallback path (self-enrichment):
    job_search finds jobs → cortex_feed_node → feed_cortex_from_fallback (Celery)
        └── store_jobs_from_fallback() → skip fetch, dedup → enrich → embed → upsert
```

### Cron Schedule

```
cortex-full-ingestion-nightly   crontab(hour=2, minute=0)           every day
cortex-cleanup-weekly           crontab(hour=3, minute=0, dow=0)    every Sunday
```

### Seed Domains (16)

`tech_software` · `tech_data` · `tech_infra` · `tech_product` · `tech_design` · `tech_security` · `finance_banking` · `marketing_sales` · `hr_legal` · `engineering_industry` · `supply_chain` · `healthcare` · `education_research` · `consulting_management` · `construction_real_estate` · `communication_media`

Keywords derived from ROME (France Travail) and ESCO (EU) taxonomies, in French (targets French job boards).

### ESCO Client (`app/cortex/esco.py`)
Not wired. Fetches occupation titles from the official EU ESCO REST API by ISCO-08 group codes. Run manually: `python -m app.cortex.esco`

---

## Cover Letter Agent

```
POST /analysis/{id}/cover-letter?job_index=0

cv_data (from CV.data) ──┐
job (from matches[i])  ──┴──► LLM (structured output)
                                │
                        CoverLetterContent (Pydantic)
                        ├── sender       {full_name, email, phone, location}
                        ├── recipient    {company_name, contact, job_title}
                        ├── city_date    "Paris, 15 juin 2026"
                        ├── subject      "Candidature au poste de X chez Y"
                        ├── salutation   "Madame, Monsieur,"
                        ├── paragraphs   [{purpose, text} × 3-4]
                        ├── closing      str
                        ├── sign_off     "Cordialement,"
                        ├── highlighted_skills  list[str]
                        ├── tone         formal|dynamic|creative
                        └── key_selling_point   str
                                │
                        render_pdf(content)
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
            reportlab_backend       weasyprint_backend
            (pure Python)           (HTML/CSS → PDF)
```

Switch backend: `COVER_LETTER_BACKEND=reportlab|weasyprint` in `.env`

---

## Storage Layer (`app/storage.py`)

```
save_cv(data, user_id, cv_id, filename) → key
read_file(key)                          → bytes
get_presigned_url(key, expires_in=3600) → str | None
delete_file(key)

S3_BUCKET set     → AWS S3  (boto3 put_object / get_object / presigned URL)
S3_BUCKET empty   → local UPLOAD_DIR/ fallback

Key format: cvs/{user_id}/{cv_id}.pdf

GET /analysis/{id}/cv:
  S3    → RedirectResponse 302 to presigned URL (no bandwidth on API server)
  Local → StreamingResponse bytes

Presigned URL expires in 1h → frontend always calls GET /analysis/{id}/cv
for a fresh URL, never caches the S3 URL directly.
```

---

## Databases

### Main DB (`DATABASE_URL`)
PostgreSQL via `postgresql+asyncpg://` — port 5432 (direct, not pooler).

```
users       id, email, hashed_password, full_name, is_active
cvs         id, user_id, pdf_path, raw_text, data (JSON), version, source
analyses    id, user_id, cv_id, status, search_filters, keywords, matches, final_report, error
```

### Cortex DB (`CORTEX_DATABASE_URL`)
Same Supabase instance, separate SQLAlchemy engine. Gracefully disabled if `CORTEX_DATABASE_URL` is empty — pipeline falls through to API fallback.

---

## API Endpoints

### Auth
```
POST /auth/register
POST /auth/login
```

### Analysis
```
POST /analysis/upload          multipart PDF + filters → 202 (background pipeline)
GET  /analysis/{id}            poll status + results
GET  /analysis/{id}/cv         original CV PDF
POST /analysis/{id}/cover-letter?job_index=0    generated cover letter PDF
POST /analysis/{id}/apply?job_index=0           metadata + document URLs
```

### Cortex (admin)
```
POST   /cortex/ingest            custom ingestion (sync)
POST   /cortex/ingest/full       seed keyword ingestion (Celery async)
GET    /cortex/stats             active job count
GET    /cortex/domains           16 domains + keyword counts
DELETE /cortex/jobs/cleanup      deactivate stale jobs
```

---

## Celery Tasks (`app/worker/tasks.py`)

| Task | Trigger | Retries |
|---|---|---|
| `full_ingestion` | Nightly cron + `POST /cortex/ingest/full` | 3× after 5min |
| `feed_cortex_from_fallback` | `cortex_feed_node` after successful job_search | 2× after 1min |
| `cleanup_old_jobs` | Weekly cron | 2× after 1min |

---

## Frontend Architecture (`../ailfj-frontend`)

```
React 19 + Vite 8 + Tailwind v4 + React Query v5 + React Router v7

Pages
├── /login           LoginPage.tsx
├── /register        RegisterPage.tsx
├── /                UploadPage.tsx    (CV upload + filters)
└── /analysis/:id    AnalysisPage.tsx  (polling + results)

Key components
├── MatchCard.tsx      job card (expandable, skills, score)
├── ApplyModal.tsx     CV + cover letter PDFs side by side
├── FilterBar.tsx      client-side filter (contract, mode, score)
├── MarkdownReport.tsx final AI report renderer
└── StatusHeader.tsx   progress bar + live step display

API layer (src/api/)
├── client.ts          axios + JWT interceptor + 401 → /login redirect
├── analysis.ts        uploadCV, getAnalysis
└── apply.ts           applyToJob, fetchCoverLetterPdf (blob)

Design system (CSS vars → Tailwind tokens)
├── Light/dark via .dark class on <html>
├── Colors: ink, muted, subtle, accent (#7c3aed), canvas, line
└── Animations: fade-up, pop-in, shimmer, spin-slow

Apply flow
1. User clicks "Postuler" on MatchCard
2. ApplyModal opens (match.originalIndex used for job_index param)
3. CV iframe: GET /api/analysis/{id}/cv (follows S3 redirect)
4. Cover letter: POST /api/analysis/{id}/cover-letter → blob → iframe
5. User downloads both PDFs → applies on company website
```

---

## Environment Variables

```env
# App
DEBUG=false
SECRET_KEY=

# Main DB (asyncpg, port 5432)
DATABASE_URL=postgresql+asyncpg://...

# Cortex (asyncpg, port 5432)
CORTEX_DATABASE_URL=postgresql+asyncpg://...

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Job providers
JSEARCH_API_KEY=
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
ADZUNA_COUNTRY=fr

# AWS S3 (optional — falls back to local disk)
AWS_REGION=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET=

# PDF backend
COVER_LETTER_BACKEND=reportlab   # or weasyprint
```
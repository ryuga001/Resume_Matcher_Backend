# Sahara — Backend

Django 6 REST API powering AI-driven ATS resume analysis, a resume builder pipeline, and the Sahara Academy course platform with RAG-based AI tutoring.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 6 + Django REST Framework |
| Database | PostgreSQL 16 + pgvector |
| File storage | AWS S3 / MinIO (S3-compatible) |
| AI / LLM | Google Gemini (`google-genai`) |
| Embeddings | `sentence-transformers` — `all-MiniLM-L6-v2` (384-dim, local) |
| PDF parsing | PyMuPDF (`fitz`) |
| PDF generation | ReportLab |
| Auth | PyJWT — access token 15 min + refresh token 7 days, HTTP-only cookies |
| Async workers | RabbitMQ + `pika` (3 workers: subtopic, content, bulk_content) |
| Cache / broker | Redis |

---

## Project Layout

```
backend/
├── config/              Django settings, root URL conf, WSGI/ASGI
├── users/               Auth — register, login, logout, refresh, profile
├── resumes/             Resume upload, S3 storage, builder pipeline
│   ├── services/
│   │   ├── formatters/  Strategy pattern — PDF formatter (ReportLab)
│   │   ├── enhancers/   Decorator pattern — skills / keyword / summary enhancers
│   │   ├── resume_structurer_service.py   Gemini: raw text → structured JSON
│   │   ├── resume_builder_service.py      Orchestrator
│   │   ├── resume_parser_service.py       PyMuPDF text extraction
│   │   └── resume_service.py              Upload flow (parse → skills → S3 → embed)
│   └── repositories/
├── analysis/            ATS scoring via Gemini + pgvector RAG retrieval
│   └── service/
│       ├── analysis_service.py
│       ├── retrieval_service.py
│       └── prompt_builder.py
├── embeddings/          Chunking + MiniLM embedding + pgvector indexing
├── courses/             Sahara Academy — course CRUD, subtopic/content generation
├── workers/             RabbitMQ consumers (subtopic / content / bulk_content)
├── common/
│   ├── ai/llm_service.py   Gemini client wrapper
│   ├── s3.py               S3/MinIO client (presign, upload, delete, stream)
│   ├── embeddings.py       MiniLM inference helper
│   └── rabbitmq.py         RabbitMQ connection helper
└── manage.py
```

---

## API Reference

### Auth — `/api/auth/`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `register` | Create account, set HTTP-only cookies |
| `POST` | `login` | Authenticate, set HTTP-only cookies |
| `POST` | `logout` | Clear cookies |
| `POST` | `refresh` | Rotate access token using refresh cookie |
| `GET` | `me` | Current user profile |
| `PUT` | `profile` | Update name / email / password |

Cookies: `rm_access_token` (15 min) + `rm_refresh_token` (7 days).
`SameSite=None; Secure` in production (`COOKIE_SECURE=true`), `SameSite=Lax` in development.

---

### Resumes — `/api/resumes/`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `upload` | Upload PDF → extract text → embed → store in S3 |
| `GET` | `list` | All resumes for the authenticated user |
| `DELETE` | `<id>` | Delete record + S3 original + S3 customized |
| `GET` | `<id>/view` | Presigned GET URL for original PDF (10 min TTL) |
| `GET` | `<id>/structured` | Parse resume → structured JSON via Gemini (result cached in DB) |
| `POST` | `<id>/build` | Apply ATS recommendations via Gemini + decorator chain |
| `POST` | `<id>/export` | Render PDF → temp S3 key → presigned download URL |
| `GET` | `<id>/customized` | Presigned URL for the saved customized PDF |
| `POST` | `<id>/customized` | Render PDF → upload to permanent S3 key → persist key |

---

### Analysis — `/api/analysis`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `` | Run ATS analysis (pgvector retrieval + Gemini) |
| `GET` | `/history` | List all analyses for the authenticated user |
| `GET` | `/<id>` | Single analysis detail |

---

### Courses — `/api/courses`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `` | List all courses |
| `POST` | `/presign` | Presigned PUT URL for PDF/thumbnail upload |
| `GET/POST` | `/<id>/subtopics` | Get subtopics or trigger generation via RabbitMQ |
| `GET` | `/<id>/subtopics/status/<task_id>` | Poll subtopic generation |
| `POST` | `/<id>/content/generate` | Trigger content generation for all subtopics |
| `GET` | `/<id>/content/status/<task_id>` | Poll content generation |
| `GET` | `/<id>/subtopics/<order>` | Get single subtopic with generated content |
| `POST` | `/<id>/subtopics/<order>/chat` | RAG chat for a subtopic |

---

## Resume Builder — Design Patterns

```
resumes/services/
├── formatters/
│   ├── base_formatter.py     # Strategy interface — ResumeFormatter(ABC)
│   ├── pdf_formatter.py      # Concrete strategy — PDFResumeFormatter (ReportLab)
│   └── factory.py            # Factory — ResumeFormatterFactory.create("pdf")
│
├── enhancers/
│   ├── base_enhancer.py      # Decorator base — ResumeEnhancer(ABC), wraps chain
│   ├── skills_enhancer.py    # Merges missing skills into skills[]
│   ├── keyword_enhancer.py   # Injects job keywords into latest experience entry
│   └── summary_enhancer.py   # Prepends top recommendation to summary
│
├── resume_structurer_service.py   # Gemini: raw text → structured JSON
└── resume_builder_service.py      # Orchestrator: structure → enhance → render → upload
```

Decorator chain at runtime:
```python
SummaryEnhancer(KeywordEnhancer(SkillsEnhancer())).enhance(data, context)
```

---

## Resume Upload Flow

```
POST /api/resumes/upload
  ├─ 1. Write PDF to tempfile
  ├─ 2. PyMuPDF → extract text
  ├─ 3. SkillExtractionService → skills[]
  ├─ 4. S3Service.upload_file() → s3_key
  ├─ 5. os.unlink(tempfile)
  ├─ 6. ResumeRepository.save_resume()
  └─ 7. Thread: IndexingService → MiniLM → pgvector
```

## ATS Analysis Flow

```
POST /api/analysis
  ├─ 1. AnalysisService.analyze() — retrieval + Gemini
  ├─ 2. user_repo.decrement_uses()
  └─ 3. AnalysisRepository.save()
```

Credits are decremented **after** a successful Gemini response — a failed call never costs a credit.

---

## Environment Variables

```env
# Django
SECRET_KEY=
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/sahara

# AWS / MinIO
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_S3_BUCKET=matchkit
AWS_REGION=us-east-1
S3_ENDPOINT_URL=http://localhost:9000   # omit for real AWS

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash

# Auth
JWT_SECRET=
COOKIE_SECURE=false   # true in production → SameSite=None; Secure

# RabbitMQ
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Redis
REDIS_URL=redis://localhost:6379/0
```

---

## Local Setup

```bash
# 1. Start infrastructure (PostgreSQL, RabbitMQ, Redis, MinIO, Mailpit)
docker compose up -d

# 2. Create virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Apply migrations
python manage.py migrate

# 5. Run dev server
python manage.py runserver

# 6. Start async workers (separate terminals)
python workers/subtopic_worker.py
python workers/content_worker.py
python workers/bulk_content_worker.py
```

| Service | URL |
|---------|-----|
| Django API | http://localhost:8000 |
| MinIO console | http://localhost:9001 |
| RabbitMQ console | http://localhost:15672 |
| Mailpit | http://localhost:8025 |

---

## Database Migrations

| File | Change |
|------|--------|
| `0001_initial.py` | Initial Resume model |
| `0002_resume_s3_key.py` | Added `s3_key` |
| `0003_resume_builder_fields.py` | Added `customized_s3_key` + `structured_data` |

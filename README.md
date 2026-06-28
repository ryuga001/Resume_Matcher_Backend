# Sahara — Backend

Django REST API powering resume analysis, AI-driven ATS scoring, and the Sahara Academy course platform with RAG-based AI tutoring.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | Django 6 + Django REST Framework |
| Database | PostgreSQL 16 + pgvector |
| Task queue | RabbitMQ + pika — three dedicated worker processes |
| AI / LLM | Google Gemini via `google-genai` SDK |
| Resume embeddings | `sentence-transformers` — `all-MiniLM-L6-v2` (384-dim, local) |
| Course embeddings | Gemini `text-embedding-004` (768-dim) |
| Storage | AWS S3 (or any S3-compatible store via `S3_ENDPOINT_URL`) |
| Auth | PyJWT — stateless Bearer tokens issued as HTTP-only cookies |
| PDF parsing | PyMuPDF (`fitz`) |
| Package manager | uv |

---

## Project Structure

```
backend/
├── config/
│   ├── settings.py          # All config — env-driven
│   └── urls.py              # Root URL conf
├── users/                   # Auth: register, login, JWT, profile, refresh, logout
├── resumes/                 # PDF upload → S3, text extraction, MiniLM embedding + index
├── analysis/                # ATS scoring, skill-gap analysis, history
├── courses/                 # Academy: courses, subtopics, content generation, RAG chat
│   ├── api/
│   │   ├── views.py         # All course API views
│   │   └── urls.py
│   ├── models.py            # Course, Subtopic, TaskRecord (ORM)
│   ├── repository.py        # DB queries
│   └── task_handlers.py     # Business logic called by workers
├── embeddings/              # Resume embedding service (MiniLM)
│   ├── service/
│   └── repositories/
├── common/
│   ├── gemini.py            # GeminiService: subtopics, content gen, RAG chat
│   ├── embeddings.py        # EmbeddingService: Gemini text-embedding-004
│   ├── rabbitmq.py          # publish() / consume() helpers with auto-reconnect
│   └── s3.py                # S3Service: presign, upload, download, stream
├── workers/
│   ├── subtopic_worker.py   # Consumes 'subtopics_generation' queue
│   ├── content_worker.py    # Consumes 'content_generation' queue
│   └── bulk_content_worker.py  # Consumes 'bulk_content_generation' queue
└── manage.py
```

---

## API Endpoints

All routes except `register`, `login`, and `refresh` require `Authorization: Bearer <token>`.  
Admin routes additionally require `role == "SUPER_ADMIN"`.

### Auth — `/api/auth/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Create account |
| POST | `/api/auth/login` | — | Login, returns JWT (HTTP-only cookie + body) |
| POST | `/api/auth/logout` | — | Clear auth cookie |
| POST | `/api/auth/refresh` | — | Refresh access token |
| GET | `/api/auth/me` | ✓ | Current user profile |
| PATCH | `/api/auth/profile` | ✓ | Update name / password |

### Resumes — `/api/resumes/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/resumes/list` | ✓ | List user's resumes |
| POST | `/api/resumes/upload` | ✓ | Upload PDF, extract text, index embeddings |
| DELETE | `/api/resumes/<id>` | ✓ | Delete resume + S3 asset |

### Analysis — `/api/analysis`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/analysis` | ✓ | Run ATS analysis — returns score, skills, recommendations |
| GET | `/api/analysis/history` | ✓ | Full analysis history |
| GET | `/api/analysis/<id>` | ✓ | Single analysis detail |

### Academy — `/api/courses`

| Method | Path | Role | Description |
|--------|------|------|-------------|
| GET | `/api/courses` | any | List courses (search, category, status filters) |
| POST | `/api/courses` | admin | Create course |
| GET | `/api/courses/<id>` | any | Course detail |
| PATCH | `/api/courses/<id>` | admin | Update course |
| DELETE | `/api/courses/<id>` | admin | Delete course + S3 assets |
| POST | `/api/courses/presign` | admin | Presign S3 PUT for source PDF / thumbnail |
| POST | `/api/courses/<id>/subtopics/generate` | admin | Enqueue subtopic generation (returns `taskId`) |
| GET | `/api/courses/<id>/subtopics/status/<taskId>` | admin | Poll subtopic task status |
| PUT | `/api/courses/<id>/subtopics` | admin | Save / reorder subtopic list |
| POST | `/api/courses/<id>/content/generate` | admin | Enqueue content generation for all subtopics |
| GET | `/api/courses/<id>/content/status` | any | Per-subtopic generation status |
| GET/POST/PUT | `/api/courses/<id>/content/<order>` | any/admin | Fetch / generate / save subtopic content |
| POST | `/api/courses/<id>/content/<order>/chat` | any | RAG chat for a subtopic |

---

## Setup

**Prerequisites:** Python 3.12+, PostgreSQL 16 with pgvector, RabbitMQ 3+

```bash
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

Create `backend/.env`:

```env
DJANGO_SECRET_KEY=your-secret-key-32-chars-minimum
JWT_SECRET=your-jwt-secret-32-chars-minimum
DEBUG=True

POSTGRES_DB=sahara
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

RABBITMQ_URL=amqp://guest:guest@localhost:5672/

GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.0-flash

AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=sahara
AWS_REGION=us-east-1
# S3_ENDPOINT_URL=http://localhost:9000  # uncomment for local S3-compatible store

FRONTEND_URI=http://localhost:3000
COOKIE_SECURE=false
```

```bash
# Apply migrations (creates tables + enables pgvector extension)
python manage.py migrate

# Start the Django API
python manage.py runserver

# Start workers — each in its own terminal, .venv activated, from backend/
python workers/subtopic_worker.py
python workers/content_worker.py
python workers/bulk_content_worker.py
```

Or use Docker Compose for all infrastructure (PostgreSQL, RabbitMQ, Redis, Mailpit):

```bash
docker compose up -d
```

API available at `http://localhost:8000`.

---

## Key Concepts

### Authentication
JWT tokens are issued on register/login and set as HTTP-only cookies (7-day expiry). The `@require_auth` decorator validates the `Authorization: Bearer <token>` header and injects `request.user_id`, `request.user_email`, and `request.user_role`. Admin-only views additionally call `@require_role("SUPER_ADMIN")`.

### Resume Processing
Uploaded PDFs are stored in S3. Text is extracted with PyMuPDF, chunked, and embedded locally using `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim). Vectors are stored in PostgreSQL via pgvector. The `indexStatus` field (`processing → ready | error`) is polled by the frontend.

### Course Content Generation
1. Admin uploads a source PDF to S3 via a presigned URL
2. **Subtopic generation** — a `TaskRecord` is created, then a message is published to the `subtopics_generation` RabbitMQ queue. `subtopic_worker.py` picks it up, streams the PDF from S3, calls Gemini Flash, and writes a structured subtopic list to the DB. The frontend polls the task status endpoint every 2 s.
3. **Per-subtopic content generation** — admin triggers generation per subtopic. A message is published to `content_generation`; `content_worker.py` calls `GeminiService.generate_subtopic_content()`, uploads the result JSON to S3, and embeds content chunks (768-dim via Gemini `text-embedding-004`) into PostgreSQL for RAG search.
4. **Bulk generation** — `POST /content/generate` enqueues a single message to `bulk_content_generation`; `bulk_content_worker.py` runs subtopics sequentially, acting as a natural rate-limit throttle for the Gemini free tier.

### RabbitMQ Workers
Workers use `pika` with heartbeat disabled (`heartbeat=0`) so that long-running Gemini API calls (30–120 s for PDF analysis) never cause RabbitMQ to close the connection mid-task. Each worker auto-reconnects with exponential backoff (5 s → 60 s) on connection loss.

### RAG Chat
`POST /api/courses/<id>/content/<order>/chat`:
1. Loads subtopic content JSON from S3 as base context
2. Narrows context using cosine-similarity search over pgvector course chunk embeddings
3. Calls `GeminiService.chat_subtopic()` with the full conversation history
4. Returns the model's reply

### CI
GitHub Actions (`.github/workflows/django.yml`) runs on every push/PR to `main`:
- Spins up `pgvector/pgvector:pg16` as a service
- Installs dependencies via `uv` (GPU-only packages stripped for CPU-only runners)
- `manage.py check` → `migrate` → `test`

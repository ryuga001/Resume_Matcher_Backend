# Sahara — Backend

Django REST API powering resume analysis, AI-driven ATS scoring, and the Sahara Academy course platform with RAG-based AI tutoring.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | Django 5 + Django REST Framework |
| Database | MongoDB (PyMongo) — schemaless, no migrations |
| Task queue | Celery + Redis |
| AI / LLM | Google Gemini (via `google-generativeai`) |
| Embeddings | Gemini `text-embedding-004` — stored in `course_chunks` collection |
| Storage | MinIO (S3-compatible) — PDFs, thumbnails, generated content JSON |
| Auth | PyJWT — stateless Bearer tokens |
| PDF parsing | PyMuPDF (`fitz`) |

---

## Project Structure

```
backend/
├── config/
│   ├── settings.py        # All config — env-driven
│   └── urls.py            # Root URL conf
├── users/                 # Auth: register, login, JWT, profile
├── resumes/               # PDF upload → S3, text extraction, embedding index
├── analysis/              # ATS scoring, skill-gap analysis, history
├── courses/               # Academy: courses, subtopics, content generation, RAG chat
│   ├── api/
│   │   ├── views.py       # All course API views
│   │   └── urls.py        # Course URL patterns
│   ├── repository.py      # MongoDB queries for courses collection
│   └── tasks.py           # Celery tasks: subtopic gen, content gen
├── common/
│   ├── gemini.py          # GeminiService: subtopics, content, chat
│   ├── embeddings.py      # EmbeddingService: chunk → embed → MongoDB
│   ├── s3.py              # S3Service: presign, upload, download, stream
│   └── mongodb/           # MongoDBClient singleton
├── celery_app.py          # Celery app entry point
└── manage.py
```

---

## API Endpoints

### Auth — `/api/auth/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Create account |
| POST | `/api/auth/login` | — | Login, returns JWT |
| GET | `/api/auth/me` | ✓ | Current user profile |
| PATCH | `/api/auth/profile` | ✓ | Update name / password |

### Resumes — `/api/resumes/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/resumes/list` | ✓ | List user's resumes |
| POST | `/api/resumes/upload` | ✓ | Upload PDF resume |
| DELETE | `/api/resumes/<id>` | ✓ | Delete resume |

### Analysis — `/api/analysis`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/analysis` | ✓ | Run ATS analysis |
| GET | `/api/analysis/history` | ✓ | Analysis history |
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
| POST | `/api/courses/<id>/subtopics/generate` | admin | Async subtopic generation (returns `taskId`) |
| GET | `/api/courses/<id>/subtopics/status/<taskId>` | admin | Poll subtopic generation task |
| PUT | `/api/courses/<id>/subtopics` | admin | Save / reorder subtopic list |
| POST | `/api/courses/<id>/content/generate` | admin | Sequential content generation for all subtopics |
| GET | `/api/courses/<id>/content/status` | any | Per-subtopic generation status |
| POST | `/api/courses/<id>/content/<order>` | admin | Generate content for one subtopic |
| GET | `/api/courses/<id>/content/<order>` | any | Fetch generated content JSON |
| PUT | `/api/courses/<id>/content/<order>` | admin | Save edited content + re-embed |
| POST | `/api/courses/<id>/content/<order>/chat` | any | RAG chat for a subtopic |

All routes except register/login require `Authorization: Bearer <token>`.  
Admin routes additionally require `role == "SUPER_ADMIN"`.

---

## Setup

**Prerequisites:** Python 3.11+, MongoDB, Redis, MinIO (or any S3-compatible store)

```bash
# From repo root
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
DJANGO_SECRET_KEY=your-secret-key-32-chars-minimum
JWT_SECRET=your-jwt-secret-32-chars-minimum
DEBUG=True

MONGO_URI=mongodb://localhost:27017
MONGO_DB=sahara

REDIS_URL=redis://localhost:6379/0

GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash

S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=sahara
S3_REGION=us-east-1

FRONTEND_URI=http://localhost:3000
```

```bash
# Start Django
cd backend
python manage.py runserver

# Start Celery worker (separate terminal, .venv activated)
celery -A celery_app worker --loglevel=info
```

API available at `http://localhost:8000`.

---

## Key Concepts

### Authentication
JWT tokens are issued on register/login (7-day expiry). The `@require_auth` decorator validates the `Authorization: Bearer <token>` header and injects `request.user_id`, `request.user_email`, and `request.user_role`. Admin-only views use `@require_role("SUPER_ADMIN")`.

### Resume Processing
Uploaded PDFs are stored in S3. Text is extracted with PyMuPDF, chunked, embedded with Gemini `text-embedding-004`, and stored in MongoDB's `resume_chunks` collection. The `indexStatus` field (`processing → ready | error`) is polled by the frontend.

### Course Content Generation
1. Admin uploads a source PDF to S3 via a presigned URL
2. **Subtopic generation**: Celery task streams the PDF from S3, sends it to Gemini Flash, returns a structured subtopic list
3. **Content generation**: Admin clicks Generate on individual subtopics. Each task:
   - Calls `GeminiService.generate_subtopic_content()` → structured JSON (overview, theory, diagrams, code, quiz)
   - Uploads the JSON to S3 (`courses/content/<uuid>.json`)
   - Embeds content chunks into MongoDB `course_chunks` for RAG
   - Updates subtopic `status` → `"done"` with `contentKey`
4. **Rate limiting**: 429 errors parse Gemini's `retry_delay` and sleep + retry automatically

### RAG Chat
`POST /api/courses/<id>/content/<order>/chat`:
1. Loads subtopic content JSON from S3 as base context
2. Optionally narrows context using cosine similarity search over `course_chunks` embeddings
3. Calls `GeminiService.chat_subtopic()` with full conversation history
4. Returns the model's reply

# MatchKit — Backend

Django REST API powering resume parsing, embedding-based indexing, and AI-driven ATS analysis.

## Tech Stack

- **Django 6** + **Django REST Framework** — API layer
- **MongoDB** (via pymongo) — primary data store
- **LangChain / LangGraph** — LLM orchestration for analysis
- **sentence-transformers** — local embeddings for resume indexing
- **PyJWT** — stateless JWT authentication
- **PyMuPDF** — PDF text extraction

## Project Structure

```
backend/
├── config/          # Django settings, root URL conf
├── users/           # Auth: register, login, JWT, profile, credits
├── resumes/         # PDF upload, text extraction, skill indexing
├── analysis/        # ATS scoring, skill gap analysis, history
├── embeddings/      # Embedding models and vector utilities
├── rag/             # RAG pipeline (LangChain retrieval chain)
└── common/          # Shared utilities
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/auth/me` | Current user + credits remaining |
| PATCH | `/api/auth/profile` | Update name / password |
| POST | `/api/resumes/upload` | Upload PDF resume |
| GET | `/api/resumes/list` | List user's resumes |
| DELETE | `/api/resumes/<id>` | Delete a resume |
| POST | `/api/analysis` | Run ATS analysis (consumes 1 credit) |
| GET | `/api/analysis/history` | Analysis history |
| GET | `/api/analysis/<id>` | Single analysis detail |

All routes except register/login require `Authorization: Bearer <token>`.

## Setup

**Prerequisites:** Python 3.11+, MongoDB running locally or via URI

```bash
# From repo root
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
DJANGO_SECRET_KEY=your-secret-key
JWT_SECRET=your-jwt-secret
DEBUG=True
MONGO_URI=mongodb://localhost:27017
MONGO_DB=matchkit
OPENAI_API_KEY=sk-...        # or whichever LLM provider
FRONTEND_URI=http://localhost:3000
```

```bash
cd backend
python manage.py migrate
python manage.py runserver
```

The API will be available at `http://localhost:8000`.

## Authentication

JWT tokens are issued on register/login and expire after **7 days**. The `@require_auth` decorator validates the `Authorization: Bearer <token>` header on protected views and injects `request.user_id`, `request.user_email`, and `request.user_name`.

## Resume Processing

Uploaded PDFs are parsed with PyMuPDF, chunked, embedded with sentence-transformers, and stored in MongoDB. The `indexStatus` field (`processing → ready | error`) is polled by the frontend.

## Analysis Credits

Each user has a `usesLeft` counter. Running an analysis decrements it by 1. The `/api/auth/me` endpoint exposes the remaining count.

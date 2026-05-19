# Voice Matters — Sarkari Saathi

Sarkari Saathi is a Hindi-first voice PWA that helps Indian citizens discover
and apply for government schemes through natural conversation. The backend is
a Python FastAPI service that orchestrates Sarvam (speech), OpenAI (reasoning),
and Pinecone (scheme retrieval) over a curated corpus. The frontend is a
zero-build static PWA, optimized for low-end Android devices on flaky networks.

## Quickstart

```bash
git clone <repo-url> sarkari-saathi
cd sarkari-saathi

# Backend
cd backend
python3.11 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # fill in keys
uvicorn main:app --reload           # http://localhost:8000 (API on 8000? see below)

# Frontend (in a separate terminal)
cd ../web
python3 -m http.server 8000         # http://localhost:8000
```

Run the backend on a different port (e.g. `--port 8080`) when running the
frontend on 8000, and set `FRONTEND_ORIGIN=http://localhost:8000` in `.env`.

## Architecture

```
                    ┌──────────────────────────────────┐
                    │   Web PWA (/web, static HTML)    │
                    │   mic capture · TTS playback     │
                    │   service worker · manifest      │
                    └──────────────┬───────────────────┘
                                   │  HTTPS (JSON + multipart audio)
                                   ▼
                    ┌──────────────────────────────────┐
                    │   FastAPI Backend (/backend)     │
                    │   /api/v1 conversation · schemes │
                    │   structlog · CORS · async       │
                    └───┬───────────┬───────────┬──────┘
                        │           │           │
                ┌───────▼──┐  ┌─────▼─────┐  ┌──▼──────────┐
                │  Sarvam  │  │  OpenAI   │  │  Pinecone   │
                │ STT/TTS  │  │ chat+embed│  │ scheme RAG  │
                │ (hi-IN)  │  │           │  │             │
                └──────────┘  └───────────┘  └─────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │   Postgres (SQLAlchemy/asyncpg)  │
                    │   conversations · messages       │
                    │   user_actions · telemetry       │
                    │   schemes_meta · feedback        │
                    └──────────────────────────────────┘

       ┌──────────────────────────────────────────────┐
       │  /scheme-corpus  (raw PDFs → processed JSON  │
       │   → embeddings upserted to Pinecone index    │
       │   `voice-matters-schemes`)                   │
       └──────────────────────────────────────────────┘
```

## Repo layout

- `backend/` — FastAPI app, models, clients, services
- `web/` — static PWA (no Node toolchain)
- `scheme-corpus/` — source PDFs and processed JSON for RAG
- `docs/` — architecture, API contracts, build log
- `.github/workflows/` — CI (ruff lint)

## Build guide

See `docs/` for the full build guide. This repo is being built one prompt at a
time; each step is recorded in [docs/build-log.md](docs/build-log.md).

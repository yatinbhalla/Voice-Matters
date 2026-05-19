# Build Log

## Prompt 1 — 2026-05-20
- Created monorepo skeleton: `/backend`, `/web`, `/scheme-corpus`, `/docs`.
- FastAPI app with `/health` + v1 stub routes (conversation, schemes, admin).
- SQLAlchemy models for conversations, messages, user_actions, schemes_meta,
  telemetry, feedback.
- Stub clients: Sarvam, OpenAI, Pinecone.
- Static `/web` placeholder (index.html, manifest.json, sw.js).
- GitHub Actions CI: ruff lint on every push.
- Boot verified via uvicorn + `python -m http.server`.

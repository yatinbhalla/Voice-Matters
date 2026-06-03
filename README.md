# Voice Matters — Sarkari Saathi 🎙️

> **A Hindi-first voice PWA that helps underserved Indian citizens discover and apply for government schemes through natural conversation — no literacy required, no bureaucratic maze.**

[![Live Demo](https://img.shields.io/badge/Live-voice--matters--web.onrender.com-4CAF50?style=for-the-badge&logo=render&logoColor=white)](https://voice-matters-web.onrender.com/#/home)
[![Build](https://img.shields.io/github/actions/workflow/status/yatinbhalla/Voice-Matters/ci.yml?style=for-the-badge&logo=github-actions&logoColor=white&label=CI)](https://github.com/yatinbhalla/Voice-Matters/actions)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Last Commit](https://img.shields.io/github/last-commit/yatinbhalla/Voice-Matters?style=for-the-badge&logo=github&logoColor=white)](https://github.com/yatinbhalla/Voice-Matters/commits/main)


---

## 🧭 Overview

Over 90 crore Indian citizens are eligible for government welfare schemes but miss out — not because they aren't entitled, but because discovering schemes, checking eligibility, and completing applications requires navigating opaque English-language portals that assume literacy and internet fluency neither exists.

Sarkari Saathi eliminates that barrier. A citizen speaks a question in Hindi — *"Mujhe gas cylinder chahiye, kya karna hoga?"* — and receives a spoken, jargon-free answer naming the right scheme (Ujjwala Yojana), citing the official source, and giving one clear next step (helpline or CSC address).

Architected a 5-stage async voice pipeline — ffmpeg → Sarvam Saaras STT → OpenAI + Pinecone RAG → Sarvam-m LLM → Bulbul TTS — that reduces government scheme discovery from hours of confusing form-filling to a single spoken question, delivering structured answers and eligibility checks in ~15 s end-to-end on Render's free tier. Reduced per-query wall-clock time by 5–15 s by running TTS synthesis and eligibility checking concurrently via `asyncio.gather`, cutting latency to `max(TTS, eligibility)` instead of their sum.

---

## 📋 Table of Contents

- [Key Features](#-key-features)
- [Why Sarkari Saathi](#-why-sarkari-saathi)
- [Tech Stack](#%EF%B8%8F-tech-stack)
- [Project Layout](#%EF%B8%8F-project-layout)
- [Voice Pipeline & AI Routing](#-voice-pipeline--ai-routing)
- [NLP & Prompt Design](#-nlp--prompt-design)
- [API Endpoints](#-api-endpoints)
- [Data Models](#%EF%B8%8F-data-models)
- [Getting Started](#-getting-started)
- [Known Limitations & v2 Ideas](#%EF%B8%8F-known-limitations--v2-ideas)
- [Contributing](#-contributing)
- [Author](#author)

---

## ⚡ Key Features

- **Engineered a real-time Hindi voice pipeline** — records mic audio on mobile, normalizes via ffmpeg to 16 kHz mono WAV, transcribes with Sarvam Saaras (hi-IN), retrieves top-5 scheme chunks from Pinecone, reasons with Sarvam-m, and plays back spoken Hindi audio via Bulbul TTS — end-to-end in ~15 s on Render's free tier.

- **Reduced per-query latency by 5–15 s** by parallelizing TTS synthesis and eligibility checking via `asyncio.gather` — both stages are data-independent, so wall-clock drops from the sequential sum to `max(TTS, eligibility)`.

- **Shipped a zero-build-toolchain PWA** — vanilla HTML/CSS/JS with a service worker and Web App Manifest, installable on low-end Android devices with no Node.js, bundler, or app store required.

- **Optimized for 2G and flaky networks** — switchable 8 kHz TTS mode halves audio payload size for low-bandwidth connections; all TTS files served with 24 h `Cache-Control: immutable` headers so the service worker can re-serve without hitting the backend.

- **Integrated a RAG corpus of 7 Central Government schemes** — PDFs → structured JSON (eligibility rules, documents required, 5-step application guide, helpline) → OpenAI `text-embedding-3-small` → Pinecone index `voice-matters-schemes`.

- **Productionized a hallucination guard** — every LLM response is validated against the live scheme name list from Postgres; answers referencing unindexed schemes are soft-refused with helpline 14434, never fabricated.

- **Automated jargon sanitization** — a regex substitution table enforces conversational Hindi post-generation (*process → kaam, verification → jaanch*) even if the LLM slips, ensuring Bulbul TTS reads naturally to an 8th-class-pass listener.

- **Deployed declaratively on Render** via `render.yaml` Blueprint — Dockerized FastAPI backend in the Singapore region (minimizes Sarvam API round-trip latency) + static frontend, zero-downtime auto-deploy on every push to `main`.

---

## 🎯 Why Sarkari Saathi?

| Who | Why this works |
|---|---|
| **Rural citizens (primary)** | Hindi voice input removes the literacy and English barrier entirely; no app download needed — installable as a PWA on any Android. |
| **NGO and CSC field workers** | Walk a beneficiary through eligibility and document checklists on a basic Android phone, even on a 2G connection. |
| **Policy researchers** | Structured telemetry (per-stage latency, retrieval hit rate, confidence, feedback votes) surfaces exactly where scheme discovery breaks down at scale. |
| **Civic tech builders** | The voice + RAG architecture is language- and corpus-agnostic — reusable for any regional language × government knowledge base. |

---

## ⚙️ Tech Stack

**Frontend**

[![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white&style=flat-square)](https://developer.mozilla.org/en-US/docs/Web/HTML)
[![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white&style=flat-square)](https://developer.mozilla.org/en-US/docs/Web/CSS)
[![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black&style=flat-square)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![PWA](https://img.shields.io/badge/PWA-installable-5A0FC8?logo=pwa&logoColor=white&style=flat-square)](https://web.dev/progressive-web-apps/)
[![Service Worker](https://img.shields.io/badge/Service_Worker-offline_cache-orange?style=flat-square)](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)

**Backend**

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white&style=flat-square)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white&style=flat-square)](https://fastapi.tiangolo.com)
[![Uvicorn](https://img.shields.io/badge/Uvicorn-ASGI-purple?style=flat-square)](https://www.uvicorn.org)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-async-red?style=flat-square)](https://docs.sqlalchemy.org/en/20/)
[![Alembic](https://img.shields.io/badge/Alembic-migrations-red?style=flat-square)](https://alembic.sqlalchemy.org)

**AI / ML**

[![Sarvam AI](https://img.shields.io/badge/Sarvam_AI-STT_+_LLM_+_TTS-FF6B35?style=flat-square)](https://sarvam.ai)
[![OpenAI](https://img.shields.io/badge/OpenAI-Embeddings-412991?logo=openai&logoColor=white&style=flat-square)](https://platform.openai.com)
[![Pinecone](https://img.shields.io/badge/Pinecone-Vector_DB-00BFA6?style=flat-square)](https://www.pinecone.io)

**Infrastructure**

[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-asyncpg-4169E1?logo=postgresql&logoColor=white&style=flat-square)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-containerized-2496ED?logo=docker&logoColor=white&style=flat-square)](https://www.docker.com)
[![Render](https://img.shields.io/badge/Render-Singapore-46E3B7?logo=render&logoColor=white&style=flat-square)](https://render.com)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-ruff_CI-2088FF?logo=github-actions&logoColor=white&style=flat-square)](https://github.com/features/actions)

---

## 🗺️ Project Layout

<details>
<summary>Click to expand full file tree</summary>

```
Voice-Matters/
├── backend/                         # FastAPI application
│   ├── main.py                      # App entry point, CORS, static mounts, startup hook
│   ├── requirements.txt             # Python deps (no PyTorch — avoids 2 GB Render build bloat)
│   ├── Dockerfile                   # Python 3.11 + ffmpeg image
│   ├── render.yaml                  # Render Blueprint: 2-service declarative deploy
│   │
│   ├── api/v1/
│   │   ├── conversation.py          # Voice / chat endpoints, feedback, action tracking
│   │   ├── schemes.py               # Scheme detail, explain (cached), apply-steps
│   │   └── admin.py                 # Admin routes (scheme management)
│   │
│   ├── clients/
│   │   ├── sarvam_client.py         # STT (Saaras v2.5), LLM (sarvam-m), TTS (Bulbul v2) + retry pool
│   │   ├── openai_client.py         # text-embedding-3-small
│   │   ├── pinecone_client.py       # Pinecone index upsert + similarity query
│   │   └── local_embedder.py        # sentence-transformers fallback (dev / EMBED_PROVIDER=local)
│   │
│   ├── services/
│   │   ├── voice_pipeline.py        # 5-stage orchestrator: norm→STT→RAG→LLM→[TTS ‖ eligibility]
│   │   ├── answer_service.py        # LLM answer + hallucination guard + jargon sanitizer
│   │   ├── eligibility_service.py   # LLM fact extraction: maps query to eligibility rules
│   │   ├── rag_service.py           # OpenAI embed → Pinecone top-k retrieve
│   │   ├── conversation_service.py  # Conversation / message CRUD, feedback recording
│   │   └── audio.py                 # ffmpeg normalization (WAV 16 kHz mono)
│   │
│   ├── models/
│   │   ├── conversation.py          # Conversation, Message, UserAction, SchemeMeta
│   │   ├── feedback.py              # Feedback (rating / vote / chip tags)
│   │   ├── telemetry.py             # Per-pipeline-run timing JSONB
│   │   ├── scheme_explain_cache.py  # (scheme_id, length) → explanation text + audio URL
│   │   └── db.py                    # asyncpg engine, SessionLocal, Neon URL normalization
│   │
│   ├── prompts/
│   │   └── system_prompts.py        # SYSTEM_PROMPT_HINDI, RESPONSE_TEMPLATE, FEW_SHOT_EXAMPLES
│   │
│   ├── data/
│   │   └── scheme_corpus.py         # In-memory loader for processed scheme JSON
│   │
│   ├── scripts/
│   │   └── ingest_schemes.py        # PDF → JSON → embedding → Pinecone upsert pipeline
│   │
│   ├── alembic/                     # DB migrations (3 versions)
│   └── tests/
│       ├── persona_scripts.py       # Persona-based voice test scripts
│       ├── run_regression.py        # End-to-end regression runner
│       └── test_persona.py          # Pytest persona tests
│
├── web/                             # Static PWA (zero build toolchain)
│   ├── index.html                   # Main app: voice/chat UI, scheme cards, feedback
│   ├── admin.html                   # Admin dashboard
│   ├── manifest.json                # Web App Manifest (installable on Android)
│   ├── sw.js                        # Service Worker (offline caching strategy)
│   └── icons/                       # App icons (192 px, 512 px)
│
├── scheme-corpus/
│   └── schemes/
│       ├── raw/                     # Source PDFs — immutable, .gitignored
│       └── processed/               # 7 normalized Central Govt scheme JSONs
│           ├── pmjdy.json           # PM Jan Dhan Yojana
│           ├── pmuy.json            # PM Ujjwala Yojana 2.0
│           ├── pmmy.json            # PM Mudra Yojana
│           ├── pmjjby.json          # PM Jeevan Jyoti Bima Yojana
│           ├── kcc.json             # Kisan Credit Card
│           ├── day-nrlm.json        # DAY-NRLM (rural livelihoods)
│           └── mmsby.json           # MMSBY
│
├── docs/
│   ├── architecture.md
│   ├── api-contracts.md
│   └── build-log.md                 # Prompt-by-prompt build history
│
└── .github/workflows/
    └── ci.yml                       # ruff lint on every push
```

</details>

---

## 🧠 Voice Pipeline & AI Routing

### 5-Stage Voice Flow

```mermaid
sequenceDiagram
    participant User as 📱 User (Android)
    participant PWA as Web PWA
    participant API as FastAPI Backend
    participant Sarvam as Sarvam AI
    participant OAI as OpenAI
    participant Pine as Pinecone
    participant DB as PostgreSQL

    User->>PWA: Records voice (Hindi)
    PWA->>API: POST /api/v1/conversation/{id}/voice (multipart audio)
    Note over API: Stage 1 — ffmpeg: normalize to WAV 16kHz mono
    API->>Sarvam: Stage 2 — Saaras v2.5 STT (hi-IN)
    Sarvam-->>API: Hindi transcript
    API->>OAI: Stage 3a — text-embedding-3-small
    OAI-->>API: 1536-dim vector
    API->>Pine: Stage 3b — top-5 similarity search (voice-matters-schemes)
    Pine-->>API: Retrieved scheme chunks
    API->>Sarvam: Stage 4 — sarvam-m LLM (RAG context + system prompt + few-shots)
    Sarvam-->>API: Hindi response text (chain-of-thought stripped)

    par Stage 5a — TTS
        API->>Sarvam: Bulbul v2 TTS (anushka, 22050 Hz or 8000 Hz low)
        Sarvam-->>API: MP3 audio bytes
        API->>API: Write /static/audio/{uuid}.mp3 (24h cache)
    and Stage 5b — Eligibility (parallel)
        API->>Sarvam: sarvam-m eligibility fact extraction
        Sarvam-->>API: Eligibility rule results
    end

    API->>DB: Persist conversation turns + telemetry (per-stage ms)
    API-->>PWA: JSON envelope (transcript, response_text, audio_url, top_3_schemes, eligibility)
    PWA->>User: Plays spoken Hindi audio + renders scheme cards
```

> **Parallel optimization:** Stages 5a (TTS) and 5b (eligibility) share no data and run concurrently via `asyncio.gather`. This saves 5–15 s per query — wall-clock drops from `TTS_ms + eligibility_ms` to `max(TTS_ms, eligibility_ms)`.

### Confidence & Refusal Routing

```mermaid
flowchart TD
    RAG[RAG retrieves top-5 chunks from Pinecone] --> CHECK{Retrieved chunks empty?}
    CHECK -- Yes --> REFUSE[Soft refusal → helpline 14434]
    CHECK -- No --> LLM[sarvam-m reasons with retrieved context]
    LLM --> GUARD{Hallucination guard:\nresponse names a scheme\nnot in corpus?}
    GUARD -- Yes --> REFUSE
    GUARD -- No --> JARGON[Jargon sanitizer:\nEnglish terms → conversational Hindi]
    JARGON --> TTS_CHECK{answer.refused?}
    TTS_CHECK -- Yes --> DROP[Drop eligibility results — noise]
    TTS_CHECK -- No --> OUT[Deliver response + TTS + eligibility]
```

---

## 🧠 NLP & Prompt Design

| Component | Detail |
|---|---|
| **Persona** | "Sarkari Saathi" — a trusted *didi/bhaiya* at a local bank or scheme office; tone calibrated to an 8th-class-pass listener |
| **Language** | Devanagari Hindi throughout — Sarvam Bulbul TTS reads Latin-script words with an English accent, so even scheme names are written in Devanagari form (PMJDY → जन धन योजना) |
| **Response template** | 4-part structure enforced in every answer: (1) Acknowledge → (2) Mirror + key fact + concrete number → (3) Cite source domain → (4) One clear next step |
| **Few-shot examples** | 5 grounded worked examples: Jan Dhan, KCC, Ujjwala, fake-scheme refusal, sensitive-data refusal (Aadhaar/OTP) |
| **Jargon substitution** | 8-entry table enforced at *prompt level* and *post-generation* — belt-and-suspenders so LLM slippage never reaches TTS |
| **Refusal criteria** | Empty RAG retrieval OR LLM references a scheme not in the Postgres hallucination-guard list → redirect to helpline 14434 |
| **Model** | Sarvam-m (reasoning model); `<think>…</think>` chain-of-thought blocks stripped by regex before TTS |
| **TTS truncation** | Responses capped at 450 chars at last sentence boundary (`।`, `.`, `\n`) to stay within Sarvam Bulbul's ~500-char limit |
| **Scheme explain cache** | LLM explanation + TTS audio cached in Postgres by `(scheme_id, length)` — repeat requests skip LLM and Sarvam entirely |

---

## 🔌 API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/conversation/{id}/voice` | Submit audio → transcript + spoken response + scheme cards + eligibility |
| `POST` | `/api/v1/conversation/{id}/chat` | Submit text → identical response envelope as `/voice` (no STT/TTS) |
| `GET` | `/api/v1/conversation/{id}/messages` | List all messages in a conversation |
| `GET` | `/api/v1/conversations` | List conversations grouped |
| `POST` | `/api/v1/conversation/{id}/feedback` | Record rating / thumbs vote / chip tags per message |
| `POST` | `/api/v1/conversation/{id}/action` | Track scheme action steps taken by user |
| `GET` | `/api/v1/schemes/{id}` | Full scheme metadata (benefits, eligibility rules, documents needed, helpline) |
| `GET` | `/api/v1/schemes/{id}/explain?length=short\|medium\|long` | LLM-generated Hindi explanation + Bulbul TTS audio (DB-cached by scheme + length) |
| `GET` | `/api/v1/schemes/{id}/apply-steps` | 5-step structured application guide (Devanagari) |
| `GET` | `/api/v1/messages/{id}/explanation` | Per-message "Samjhao" payload + community up/down vote stats aggregated by top scheme |
| `GET` | `/health` | Health check (`{"status": "ok"}`) |

---

## 🗄️ Data Models

| Model | Key Fields |
|---|---|
| `Conversation` | `id` (UUID PK), `created_at` |
| `Message` | `id`, `conversation_id`, `role` (user/assistant), `modality` (voice/text), `content_text`, `content_audio_url`, `retrieved_schemes` (JSONB), `sources`, `confidence`, `eligibility_results` |
| `UserAction` | `id`, `conversation_id`, `scheme_id`, `action`, `step_number` |
| `SchemeMeta` | `scheme_id` (PK), `name`, `ministry`, `summary` |
| `Feedback` | `id`, `conversation_id`, `message_id` (FK → Message), `rating` (int), `comment` |
| `Telemetry` | `id`, `event_type`, `payload` (JSONB: norm_ms, stt_ms, rag_ms, llm_ms, elig_ms, tts_ms, total_ms + outcome flags) |
| `SchemeExplainCache` | `(scheme_id, length)` composite PK, `explanation_text_hi`, `explanation_audio_url` |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- `ffmpeg` on PATH (`brew install ffmpeg` / `apt install ffmpeg`)
- API keys: `SARVAM_API_KEY`, `OPENAI_API_KEY`, `PINECONE_API_KEY`
- PostgreSQL connection string (Neon serverless works out of the box)

### Install & Run

**1. Clone**
```bash
git clone https://github.com/yatinbhalla/Voice-Matters.git sarkari-saathi
cd sarkari-saathi
```

**2. Backend setup**
```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configure environment**
```bash
cp .env.example .env
# Fill in your keys — see table below
```

<details>
<summary>Required .env variables</summary>

```env
SARVAM_API_KEY=your_sarvam_key
OPENAI_API_KEY=your_openai_key
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=voice-matters-schemes
DATABASE_URL=postgresql://user:pass@host/db
FRONTEND_ORIGIN=http://localhost:8000
ENVIRONMENT=development
EMBED_PROVIDER=openai           # or "local" (needs: pip install sentence-transformers)
```

</details>

**4. Run database migrations**
```bash
alembic upgrade head
```

**5. Start backend** (different port from the frontend)
```bash
uvicorn main:app --reload --port 8080
# API: http://localhost:8080   |   Docs: http://localhost:8080/docs
```

**6. Start frontend**
```bash
cd ../web
python3 -m http.server 8000
# App: http://localhost:8000
```

**7. (Optional) Ingest scheme corpus into Pinecone**
```bash
cd backend
python scripts/ingest_schemes.py
```

### Deploy to Render

Push `render.yaml` to your repo, then in the Render dashboard: **New + → Blueprint → connect repo → Apply**. Render creates both services and prompts for the secret env vars.

---

## ⚠️ Known Limitations & v2 Ideas

**Current limitations**
- Scheme corpus covers 7 Central Government schemes; state-level and sector-specific schemes are not yet indexed.
- Sarvam Bulbul has a ~500 char ceiling per TTS request — long responses are truncated at the nearest sentence boundary.
- Render free tier sleeps after 15 min idle; first post-sleep request incurs a ~10 s cold start.
- Scheme JSON is static — eligibility changes (e.g., revised income ceilings) require a manual re-ingest cycle.
- TTS audio files accumulate in `/static/audio/` with no TTL cleanup in production.

**v2 ideas**
- Expand corpus to 50+ schemes including state-level, MSME, and agriculture schemes.
- Stream TTS audio chunks so playback starts before synthesis completes.
- Build a GPS → nearest CSC (Common Service Centre) lookup into every next-step response.
- Add a post-session CSAT survey to close the product feedback loop.
- Extend to Hinglish and regional languages (Tamil, Telugu, Bengali) via Sarvam's multilingual models.

---

## 🤝 Contributing

Sarkari Saathi is built prompt-by-prompt with every step recorded in `docs/build-log.md`. Whether you want to add a new scheme JSON, sharpen a jargon-substitution rule, or fix a frontend accessibility issue — contributions are very welcome.

- **Issues:** Open a GitHub Issue labeled `scheme-request`, `bug`, or `product-feedback`.
- **PRs:** Fork → feature branch → PR against `main`. Include the relevant scheme ID or pipeline stage in the PR title.
- **Product feedback:** Not sure it's a bug? Open a Discussion — I especially welcome input from NGO workers, CSC operators, or civic tech practitioners who've tried it in the field.

---

## Author

Yatin Bhalla · Product Manager & AI Product Builder  
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Yatin%20Bhalla-0A66C2?logo=linkedin&logoColor=white)](https://linkedin.com/in/yatinbhalla42)
[![Gmail](https://img.shields.io/badge/Gmail-yatinbhalla42%40gmail.com-EA4335?logo=gmail&logoColor=white)](mailto:yatinbhalla42@gmail.com)
[![X](https://img.shields.io/badge/X-@yatinbhalla42-000000?logo=x&logoColor=white)](https://x.com/yatinbhalla42)

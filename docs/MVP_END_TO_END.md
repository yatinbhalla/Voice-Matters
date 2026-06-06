# Voice Matters · Sarkari Saathi — Deployed MVP End-to-End

> A complete walkthrough of the live deployed product as of the current
> `main` branch. Written to be the source-of-truth document for a PRD —
> every user flow, every screen, every backend pipeline, every edge case
> and failure mode that the deployed system actually handles.
>
> **Live URLs**
> - Public app: <https://voice-matters-web.onrender.com>
> - Backend API: <https://voice-matters-n66k.onrender.com>
> - Trust dashboard: <https://voice-matters-web.onrender.com/admin.html>
> - Source: <https://github.com/yatinbhalla/Voice-Matters>

---

## 1. One-paragraph product summary

Voice Matters is a Hindi-first voice + chat assistant that helps Indian
citizens — especially low-literacy, low-income, and rural users —
discover and apply for central and state welfare schemes. The user
speaks in Hindi (or Hinglish), the system transcribes, retrieves the
most relevant schemes from an indexed corpus of seven major programs,
generates a warm conversational answer in Devanagari Hindi, speaks it
back, and walks the user through eligibility checks, document
requirements, and a step-by-step application flow. Every answer is
grounded in indexed official sources; the system explicitly refuses
rather than hallucinate when it doesn't have a confident match.

---

## 2. Target users and use case

| User | Primary need | How the app serves it |
|---|---|---|
| **Rural woman without a bank account** | "मुझे बैंक खाता खोलना है" | PMJDY recommended, walked through document list + nearest CSC |
| **Small farmer needing crop credit** | "मैं किसान हूँ लोन चाहिए" | KCC recommended, eligibility checklist, 4-step apply flow |
| **Family without LPG connection** | "घर में गैस नहीं है" | PMUY 2.0 recommended, deposit-free connection explained |
| **Daily-wage worker wanting basic insurance** | "सस्ता जीवन बीमा चाहिए" | PMJJBY recommended, ₹436/year premium spelled out |
| **First-time entrepreneur** | "व्यापार के लिए लोन चाहिए" | PMMY Shishu/Kishore/Tarun categories explained by amount |
| **Punjab resident needing free hospitalization** | "मुफ़्त इलाज की योजना" | MMSBY recommended (state-specific) |
| **SHG member or rural collective participant** | "महिला समूह को क्या मिलता है" | DAY-NRLM recommended |

Common across all personas: spoken Hindi as the primary input modality,
distrust of bureaucratic English, no patience for forms with no
audible feedback, and severe data caps. Every product decision reflects
those constraints.

---

## 3. Stack and deployment topology

```
┌─────────────────────────────────────────────────────────────┐
│ Browser (mobile or desktop)                                 │
│  - PWA, service worker, offline cache                       │
│  - Mic capture (MediaRecorder webm/opus)                    │
│  - Web Audio API VAD (5s silence auto-stop)                 │
│  - Devanagari + Hindi-Roman UI, lang-aware rendering        │
└────────────────────────────┬────────────────────────────────┘
                             │  HTTPS
┌────────────────────────────▼────────────────────────────────┐
│ Frontend — voice-matters-web.onrender.com  (Render Static)  │
│  Single-file vanilla JS app (web/index.html ~1.8k LOC)      │
│  Hash router · 6 nav screens · localStorage state           │
└────────────────────────────┬────────────────────────────────┘
                             │  HTTPS (cross-origin)
┌────────────────────────────▼────────────────────────────────┐
│ Backend — voice-matters-n66k.onrender.com  (Render Docker)  │
│  FastAPI + Uvicorn, Python 3.11                             │
│  ffmpeg, asyncpg, sqlalchemy                                │
│  Singleton clients (Sarvam, OpenAI, Pinecone)               │
└─────┬──────────┬────────────┬─────────────┬─────────────────┘
      │          │            │             │
   ┌──▼──┐  ┌────▼────┐  ┌────▼────┐  ┌─────▼─────┐
   │ Sarvam│ │ OpenAI  │  │Pinecone │  │   Neon    │
   │  STT  │ │ embed   │  │  index  │  │ Postgres  │
   │  LLM  │ │ 1536-dim│  │  60     │  │           │
   │  TTS  │ │         │  │  chunks │  │           │
   └───────┘ └─────────┘  └─────────┘  └───────────┘
```

| Component | Provider | Plan | Notes |
|---|---|---|---|
| Frontend | Render Static Site | Free | Global CDN |
| Backend | Render Docker Web Service | Free (Oregon) | Sleeps after 15min idle, 45–90s cold start |
| Vector DB | Pinecone Serverless (aws us-east-1) | Free | `voice-matters-schemes`, 1536-dim, cosine |
| Postgres | Neon Serverless (us-east-1) | Free | Async via asyncpg, sslmode=require |
| STT / LLM / TTS | Sarvam AI (India) | Pay-as-you-go | Saarika v2.5 / Sarvam-m / Bulbul v2 |
| Embeddings | OpenAI | Pay-as-you-go | `text-embedding-3-small`, ~$0.02/1M tokens |

---

## 4. The seven-scheme corpus

Seven schemes are fully indexed in Pinecone (60 vector chunks total) and
have detailed JSON metadata under `scheme-corpus/schemes/processed/`.

| ID | Name | Headline benefit | Category |
|---|---|---|---|
| `pmjdy` | प्रधानमंत्री जन धन योजना | Zero-balance account + ₹2 lakh accident insurance + ₹10k overdraft | Banking access |
| `pmuy` | प्रधानमंत्री उज्ज्वला योजना 2.0 | Free LPG connection + first refill + stove | Energy |
| `kcc` | किसान क्रेडिट कार्ड | ~4% interest farm loan, collateral-free up to ₹3L | Agriculture |
| `day-nrlm` | दीनदयाल अंत्योदय योजना (NRLM) | SHG bank linkage + skill training + ₹3L credit | Rural livelihood |
| `pmjjby` | प्रधानमंत्री जीवन ज्योति बीमा | ₹2 lakh life cover for ₹436/year | Insurance |
| `pmmy` | प्रधानमंत्री मुद्रा योजना | ₹50k–₹20L business loan, no collateral | MSME credit |
| `mmsby` | मुख्यमंत्री सेहत बीमा योजना (Punjab) | ₹5 lakh cashless hospitalization | Health (state) |

Per scheme stored: `summary_hi` (Devanagari), `eligibility_rules` (rules
engine with field/op/value/reason_hi/ask_hi), `documents_needed`,
`application_steps`, `helpline_phone`, `source_url`, `pdf_url`,
`category_label`, `tags`, plus a chunked representation for RAG:
overview, benefits, documents, application_process, helpline, and **two
synthetic intent chunks** (Hindi-Roman + Devanagari first-person query
templates like "मैं किसान हूँ" / "main kisan hu") that anchor voice
queries to the right scheme.

---

## 5. Screens and navigation map

The frontend has **6 nav destinations** plus the Vaani modal and the
admin trust dashboard, reachable via hash routes:

| Route | Screen | Owns |
|---|---|---|
| `#/home` | Home / Ask | Mic stage, prompt chips, response card |
| `#/schemes` | Schemes results | Top 3 cards from last query |
| `#/scheme/:id` | Scheme detail | Full info, hero, benefits, eligibility, docs, helpline, apply CTA |
| `#/apply/:id` | Apply steps | 4–5 step walkthrough + progress bar + reference number |
| `#/applied` (alias `#/myapps`) | My Applications | List of in-flight + completed applications |
| `#/saved` | Saved schemes | Bookmarks |
| `#/history` | History | Past Q&A conversations |
| `#/chat` | Vaani | Threaded chatbot fallback |
| `/admin.html` | Trust metrics | 6-card live dashboard (out-of-app) |

**Navigation chrome** adapts to viewport:

| Viewport | Nav surface | Visible chrome |
|---|---|---|
| Mobile (≤480px) | Sticky topbar with hamburger + drawer | Top: brand + menu, no bottom tabbar |
| Tablet (768–1023px) | Topbar + drawer | Crumb + Ask input + Trust link |
| Desktop (≥1024px) | Persistent 262px sidebar | Sidebar nav + top app-bar |
| Viewport simulator | User-forced via floating pill | Inherits to admin.html via localStorage |

Language toggle (HI / EN) lives in the sidebar/drawer. HI is the
default. The toggle calls `router()` so the active screen repaints
immediately with the new primary script for scheme names and copy.

---

## 6. End-to-end flows (happy paths)

### 6.1 Voice query — the canonical demo

1. User opens the app. First paint shows greeting card, prompt chips
   (`किसान / राशन / बेटी`), and the big mic button.
2. User taps the mic.
   - **First tap requests microphone permission.** Browser shows the
     standard permission prompt. Deny → `toast("Mic permission chahiye
     · settings mein allow kariye")` and the UI returns to idle.
   - Grant → `getUserMedia({audio:{sampleRate:16000, channelCount:1,
     echoCancellation:true}})` starts the stream.
3. `MediaRecorder` begins capturing `audio/webm;codecs=opus`. UI
   transitions to `recording` state: rings pulse, waveform animates,
   live transcript caption ("सुन रहा हूँ…").
4. **Voice activity detection (VAD)** monitors RMS level every 200ms via
   Web Audio AnalyserNode. Once it has seen at least one voice peak
   (RMS > 0.012), **5 seconds of silence** auto-stops the recording.
   Hard cap is 30 seconds either way.
5. User can also tap the mic again to manually stop. Either path leads
   to: `recording → processing` UI transition.
6. The captured blob (WebM Opus) is `POST`ed as `multipart/form-data` to
   `https://voice-matters-n66k.onrender.com/api/v1/conversation/{uuid}/voice?bitrate=high`.
7. Backend runs the voice pipeline (see §8.1). Returns JSON with
   `transcript_hi`, `response_text_hi`, `response_audio_url`,
   `top_3_schemes`, `sources`, `explanations`, `eligibility_results`.
8. Frontend transitions to `answered` state:
   - Response card slides in with: best-match scheme (Devanagari title
     primary in HI mode), one-line pitch, source row, Samjhao link
     (यह कैसे पता चला?), thumbs up/down + feedback chips, "see all 3
     options" CTA.
   - **Bulbul MP3 begins playing automatically** via `<Audio>` element.
   - A `Roko · Stop audio` button appears next to the mic. Tapping it
     calls `stopAudio()` which pauses, clears the source, and cancels
     any speech synthesis.
9. User can then: tap **Samjhao** (opens evidence modal), thumbs-up/down
   (POSTs feedback), tap a feedback chip, or tap **See all 3 options**
   to navigate to `#/schemes`.

**Total wall-clock**: ~13 s steady-state for `/chat`, ~18–22 s for
`/voice` (extra STT + TTS roundtrips). First-after-sleep request adds
45–90 s cold start on the free Render tier.

### 6.2 Text query (chip or ask-bar)

Same flow as voice, minus mic recording and minus TTS audio:

1. User taps a chip (`किसान`) or types into the "Kuch bhi poochho…"
   ask-bar at the top.
2. Frontend calls `VM_API.chat({text, language_hint:"hi"})` →
   `POST /api/v1/conversation/{uuid}/chat`.
3. Backend runs the chat pipeline (see §8.2). No STT, no TTS.
4. Response card renders. Since no `response_audio_url` is returned,
   `speak()` falls back to browser **speech synthesis** to read the
   Devanagari response aloud.

### 6.3 Browsing schemes

1. From the response card the user taps **सभी विकल्प देखो**, or taps the
   **Schemes** nav item.
2. Frontend renders 3 cards in `#/schemes`. Card 1 has a gold ribbon
   ("आपके लिए सबसे अच्छा"). Each card has:
   - Scheme name (Devanagari primary in HI mode)
   - One-line pitch
   - Effort badge (`Aasaan apply`)
   - Match-confidence percentage badge
   - **सुन लो** button (plays the Devanagari `summary_hi` via Bulbul)
   - **आगे बढ़ो** button (navigates to detail)
3. If the previous query refused (no scheme matched), the screen shows
   an amber banner ("Aapke sawaal se exact match nahi mila") and falls
   back to a top-3 default of popular schemes.

### 6.4 Scheme detail

1. User taps **आगे बढ़ो** → `#/scheme/:id`. Frontend calls
   `VM_API.scheme(id)` → `GET /api/v1/schemes/{id}`.
2. Backend returns the merged scheme JSON. Frontend renders:
   - Hero: scheme name (HI + EN), ministry badge, match-confidence pill
   - Pitch paragraph
   - 3-stat strip (amount, audience, effort)
   - About section (Devanagari summary)
   - Benefits list (head + sub bullets)
   - Eligibility checklist (each rule with `?` for unknown, ✓ for met,
     ✗ for not met)
   - Documents grid with icons
   - Links: official website row, PDF row, **toll-free helpline row**
     with phone number + "Call Now" button (`tel:` link)
3. Sticky bottom apply bar (mobile) or right-rail apply card (desktop)
   with: **Listen · सुन लो**, **Save** (bookmark), and big primary
   **आवेदन करें · How to Apply**.

### 6.5 Apply steps flow

1. User taps **आवेदन करें** → frontend calls `markApplied(id)` (writes
   to `localStorage.vm_applied`) and POSTs an `applied_started` action,
   then navigates to `#/apply/:id`.
2. Backend `GET /api/v1/schemes/{id}/apply-steps` returns the canonical
   4–5 step walkthrough.
3. Each step rendered as a card with one of three visual states:
   - **done** — green check, "कर लिया" tag, "↩ वापस जाओ · revisit" link
   - **current** — teal border, "अभी" badge, body text, "मदद चाहिए?"
     link (jumps to Vaani), big "पूरा हो गया · Done" CTA
   - **locked** — padlock icon
4. Tapping **Done** on the current step marks it done, advances current
   forward, POSTs a `step_done` action, persists state to
   `localStorage.vm_progress_<id>`.
5. When all steps done: a **reference number** (`VM-XXXXX`) is
   generated and persisted, an `applied_completed` action is POSTed,
   confetti animation, success banner stays at the top of the
   apply screen (steps remain visible + revisitable).
6. From success state, user can tap **Status** to jump to History.

### 6.6 My Applications

`#/applied` lists every scheme in `vm_applied`, newest first. Each row:
scheme name, progress bar, "X of Y kadam · NN%" label, **Detail** +
**Steps aage/dekho** buttons, and a small "Arzi hatao · Remove" link.
Empty state shows a friendly message + "Yojana dekho" CTA back to
Schemes.

### 6.7 Saved (bookmarks)

`#/saved` lists bookmarked schemes (the bookmark icon on the detail
page toggles `localStorage.vm_saved`). Bookmarks-only, no applied
schemes. Each card has a "Saved · hatao" remove button.

### 6.8 History

`#/history` lists past Q&A. Tabs: **Aaj / Pichla hafta / Saare**.
Two-paint strategy:
1. **Phase 1 — local cache.** Reads `localStorage.vm_messages` (which
   `runAskFlow` writes on every query) and paints immediately.
2. **Phase 2 — network.** Calls `GET /api/v1/conversations` in the
   background, updates the list when it lands. Cached for the session.

On desktop the screen is two-column: list left, selected conversation
detail right (re-render on click). Mobile is single column; tapping a
row jumps to the scheme detail of that answer.

### 6.9 Vaani chatbot

`#/chat` is a threaded chat with Vaani (वाणी), the AI sub-persona. Each
assistant message has a small **समझाओ · Why this?** link that opens the
evidence modal. Quick-reply chips appear below the latest assistant
message. Bottom: text input + voice button + send. Header has a back-
to-voice-mode toggle.

### 6.10 Trust metrics dashboard

`/admin.html` polls `GET /api/v1/admin/trust-metrics` every 30 s and
renders **6 cards**, each scoring against a target:

| Metric | Target |
|---|---|
| Hallucination rate | ≤ 2% |
| Eligibility false-positive | ≤ 1% |
| Comprehension pass rate | ≥ 85% |
| Refusal rate | ≤ 25% |
| p95 latency | ≤ 6,000 ms |
| Citation rate | ≥ 90% |

Cards turn **green PASS** or **red FAIL** based on the comparison.
Has its own viewport switcher (inherits from main app via
`localStorage.vm_viewport`), back-to-app pill at top-left.

---

## 7. Localization model

| Surface | HI mode | EN mode |
|---|---|---|
| Scheme card title | Devanagari name (primary) | English name (primary) |
| Scheme card subtitle | English (small) | Devanagari (small) |
| Best-match ribbon | "आपके लिए सबसे अच्छा" | "Best for you" |
| Voice query input language | `hi-IN` | `hi-IN` (current MVP transcribes Hindi only) |
| Backend LLM response | Devanagari Hindi | Devanagari Hindi (English not yet shipped) |
| Bulbul TTS voice | Sarvam `anushka` (Hindi female) | same |
| Sidebar nav labels | Mixed (English + Devanagari) | Mixed |

**Critical Devanagari-vs-Roman lesson learned**: Sarvam Bulbul (TTS)
reads Latin letters with an English accent. So the entire response path
is in Devanagari. The corpus `summary_hi`, the LLM system prompt, all 5
few-shot examples, and the user-intent chunks all have a Devanagari
script variant. Voice queries (which Sarvam Saaras returns as
Devanagari) now score 0.45–0.60 against the right scheme — up from
0.22 when the corpus was Hindi-Roman only.

---

## 8. Backend pipelines

### 8.1 `POST /api/v1/conversation/{conv_id}/voice` — Voice pipeline

1. **Audio normalize.** ffmpeg re-encodes the WebM blob to 16kHz mono
   WAV. Failures here log + fall through.
2. **STT** via Sarvam Saaras v2.5. Returns Devanagari transcript.
3. **RAG retrieval.** Embed the transcript with OpenAI
   `text-embedding-3-small`, search Pinecone for top-5 chunks above
   threshold 0.36. Refusal if no chunks pass.
4. **LLM answer + TTS + eligibility** all run in parallel via
   `asyncio.gather`. Answer uses Sarvam-m with the Devanagari system
   prompt and the retrieved chunks as context. TTS uses Bulbul v2,
   voice="anushka", sample rate 22050 (or 8000 in low-data mode).
   Eligibility runs a separate Sarvam-m call to extract 8 known facts
   (gender, age, income, state, occupation, family_members,
   has_aadhaar, has_bank_account) and evaluate the corpus rules.
5. **Hallucination guard.** Scan the LLM output for scheme names
   (including parenthetical abbreviations) that weren't in the
   retrieved context. If found, suffix `HALLUCINATION_SUFFIX_HI` to
   the response (counted in trust metrics).
6. **Jargon sanitizer.** Belt-and-suspenders regex replaces residual
   English jargon (process → kaam, verification → jaanch,
   documentation → kaagaz, etc.) in case the LLM slipped.
7. **Persist** the user + assistant messages to Postgres
   (`messages` table, JSONB columns for retrieved schemes, sources,
   eligibility results), and write a telemetry row.
8. **Return** the full envelope to the client.

Latency budget (steady state): RAG ~4 s, LLM answer 5–7 s, eligibility
3–10 s, TTS 3–5 s, network 1–2 s. Parallelization → ~13–18 s wall.

### 8.2 `POST /api/v1/conversation/{conv_id}/chat` — Chat pipeline

Same as voice without normalize / STT / TTS. Answer + eligibility still
run in parallel.

### 8.3 `GET /api/v1/schemes/{id}` — Scheme detail

Reads `scheme-corpus/schemes/processed/{id}.json` from disk, parses
documents from the application-process chunk using a small regex, and
returns a JSON envelope with `name_en`, `name_hi`, `ministry`,
`summary_hi`, `source_url`, `helpline_phone`, `tags`, `category_label`,
`benefits[]`, `eligibility_rules[]`, `documents_needed[]`.

### 8.4 `GET /api/v1/schemes/{id}/explain?length=short|medium|long`

- `short` → serves the curated Devanagari `summary_hi` directly (no
  LLM call). Audio synthesized via Bulbul if not cached.
- `medium / long` → expands via Sarvam-m with a structured prompt + the
  scheme's summary + benefits + application chunks.
- Result is cached in the `scheme_explain_cache` Postgres table keyed
  by `(scheme_id, length)`. Only rows with a valid `audio_url` are
  cached — TTS failures don't poison the cache.

### 8.5 `GET /api/v1/schemes/{id}/apply-steps`

Returns the canonical `application_steps` list from the scheme JSON
(title_hi, body_hi).

### 8.6 `GET /api/v1/conversation/{conv_id}/messages`

Returns the persisted message history for a conversation, in
chronological order with all JSONB fields hydrated.

### 8.7 `GET /api/v1/conversations`

Returns conversation list grouped into `today / week / all` buckets
with badge counts. Badges derived from `user_actions` table:
`searched / saved / in_progress / applied`.

### 8.8 `GET /api/v1/messages/{msg_id}/explanation` — Samjhao

Returns evidence for a specific assistant message: the matched span
text, why this scheme was chosen, source URL, plus aggregated feedback
counts (`up`, `down`) on that scheme across all users.

### 8.9 `POST /api/v1/conversation/{conv_id}/feedback`

Accepts `{vote:"up"|"down"|null, chips:[str], message_id}`. Persists a
row in the `feedback` table. Used in the response card and the Samjhao
modal.

### 8.10 `POST /api/v1/conversation/{conv_id}/action`

Records user actions on schemes: `searched / saved / applied_started /
step_done / applied_completed`. Drives the History badge logic and the
trust metrics dashboard's citation rate.

### 8.11 `GET /api/v1/admin/trust-metrics`

Aggregates 6 metrics from the last 100 assistant messages + telemetry
rows. Returns per-metric `{value, target, direction (lte|gte), pass}`.

---

## 9. Data model (Postgres on Neon)

| Table | Purpose | Key columns |
|---|---|---|
| `conversations` | One row per browser session | `id (uuid), created_at` |
| `messages` | User + assistant turns | `id, conversation_id, role, modality, content_text, retrieved_schemes (jsonb), sources (jsonb), eligibility_results (jsonb), created_at` |
| `user_actions` | Scheme lifecycle events | `id, conversation_id, scheme_id, action, step_number, reference_number, created_at` |
| `feedback` | User feedback on responses | `id, conversation_id, message_id (fk), rating, comment, created_at` |
| `telemetry` | Per-turn perf + correctness | `id, conversation_id, message_id, modality, rag_ms, llm_ms, elig_ms, tts_ms, total_ms, refused, confidence, eligibility_n` |
| `scheme_explain_cache` | LLM + TTS cache for `/explain` | `(scheme_id, length) → text + audio_url` |
| `schemes_meta` | Scheme name registry | `scheme_id, name (for hallucination guard alias lookup)` |

No personally-identifying information is stored. `conversation_id` is a
random UUID minted client-side, persisted in `localStorage`. There is
no auth / login.

---

## 10. Edge cases and failure modes

### 10.1 Cold-start (free Render tier)

The backend sleeps after 15 min of no traffic. First request takes
**45–90 seconds** while the container wakes, ffmpeg loads, the singleton
Sarvam/OpenAI/Pinecone clients perform their first TLS handshakes, and
the OpenAI India→US embedding call warms up. UI shows the processing
spinner the whole time; the frontend's apiFetch timeout is generous to
accommodate. After one warm request, subsequent calls are 13–18 s.

### 10.2 Mic permission denied / unavailable

`Mic.start()` throws → toast: "Mic permission chahiye · settings mein
allow kariye". UI returns to idle. User can tap a prompt chip instead
(text path) without needing mic permission.

### 10.3 No-match query → refusal

If RAG returns no chunks above threshold (0.36 cosine), the LLM is
**skipped entirely** and `REFUSAL_HI` is returned directly:

> अच्छा, समझा — आप इस योजना के बारे में पूछ रहे हैं।
> जैसे आपने कहा, इसके बारे में मुझे पक्की जानकारी नहीं है — ग़लत बात
> बताने से बेहतर है कि आप सही जगह से पुष्टि कर लें।
> सही जानकारी के लिए सरकारी हेल्पलाइन और सरकारी पोर्टल ही सबसे अच्छी
> जगह है।
> हेल्पलाइन 14434 पर बात कीजिए — 11 भाषाओं में मदद मिलती है। या अपने
> नज़दीकी सेवा केंद्र (CSC) में जाकर पूछ लीजिए।

This refusal is also spoken via Bulbul. Frontend `Schemes` screen falls
back to top-3 popular schemes with an amber "exact match nahi mila"
banner. **Off-topic queries (Bitcoin, weather, politics) refuse
correctly** — top score for "बिटकॉइन कैसे खरीदें" is 0.31, below
threshold. Off-topic adversarial tests pass 10/10.

### 10.4 Sensitive data (Aadhaar, OTP, bank password)

Few-shot examples in the LLM system prompt train Sarvam-m to refuse
and warn:

> अपना आधार नंबर, OTP, या बैंक का password कभी किसी को मत बताइए —
> यहाँ तक कि मुझे भी नहीं। सरकारी योजनाओं में OTP सिर्फ़ official portal
> या app पर ही माँगा जाता है …

The model also never echoes the sensitive value back. The pytest suite
exercises 10 sensitive-data cases.

### 10.5 Hallucination

The `_hallucination_guard()` in `answer_service.py` scans the LLM
output for scheme names and parenthetical abbreviations (PMJDY, KCC,
etc.) that weren't in the retrieved chunks. If a leak is detected, the
`HALLUCINATION_SUFFIX_HI` is appended to the response and the message
is flagged in telemetry so it lifts the dashboard's `hallucination_rate`.

### 10.6 Backend offline / unreachable

The service worker's fetch handler passes cross-origin requests
through, so CORS errors fall back to the page's own catch. If the
backend is truly unreachable, the page-level `VM_API.chat / voice /
…` falls back to `mockChat()` which uses a deterministic
keyword-based local response (PMJDY for bank, KCC for farmer, etc.).
The user can still browse the app and see seeded data. A discreet
console warning is logged.

### 10.7 Audio playback failure

`speak()` now tracks a `started` flag. If the Bulbul MP3 never starts
(404, network error, format unsupported), `useSynth()` falls back to
browser `speechSynthesis` reading the Devanagari text. If the MP3
*does* start successfully, no fallback fires — preventing the
"response repeats" bug we previously had.

### 10.8 Audio playback interruption on navigation

`router()` calls `stopAudio()` at the top, which pauses any active
`<Audio>` element, cancels `speechSynthesis.cancel()`, and increments
the monotonic `reqAudioId` so any in-flight `.play().catch()` handlers
no-op when they resolve.

### 10.9 Multiple rapid mic taps / stacking audio

`stopAudio()` is called at the start of `runAskFlow()`, in the chip
handler, and in `beginMicRecording()`. The monotonic `reqAudioId`
ensures only the latest playback fires lifecycle events that flip the
"speaking" UI state. Old audio elements are paused + cleared.

### 10.10 5-second silence auto-stop (VAD)

Web Audio API AnalyserNode samples the mic at 1024 fftSize every
200 ms. RMS above 0.012 marks "voice detected". Once detected at
least once, 5 s without crossing the threshold triggers
`onSilenceEnd` which auto-advances to processing. 30-second hard cap
applies regardless.

### 10.11 Stop-speak button while audio plays

A `body.vm-speaking` class is toggled by audio `play / ended / pause /
error` listeners. CSS reveals a `Roko · Stop audio` pill near the mic
only when that class is on. Tap → `stopAudio()`.

### 10.12 Low-data mode

Detected automatically via `navigator.connection.effectiveType in
("2g","slow-2g")`. Also user-toggleable in the drawer/sidebar. When
on:
- `/voice?bitrate=low` requests 8 kHz mono audio (~65% smaller MP3)
- Response audio does **not** auto-play; user must tap a button
- Service worker prefers cache more aggressively

### 10.13 PWA install

`beforeinstallprompt` is captured and stashed. We do **not** auto-fire
the prompt (browsers display it as an "Install app" sheet that users
were mistaking for an unwanted download). Instead, an explicit
"Install app" entry surfaces in the drawer when the deferred event
is available.

### 10.14 Service-worker stale cache

The SW has a `VERSION` constant (currently `v6-cross-origin-passthrough`).
Bumping it on every shipped change invalidates the old caches at next
visit. SW also passes through cross-origin requests entirely (added
after we saw it falsely triggering "offline" toasts on the backend's
separate Render domain).

### 10.15 Browser back from `/admin.html` → wrong page

The admin page has a top-left pill button + footer link that use
`window.location.assign(origin + "/index.html#/home")`, computed at
click time. Avoids stale browser-history entries to any archived
`_legacy_prototype.html`.

### 10.16 Network blip during the apply flow

State is in `localStorage` (`vm_progress_<id>`, `vm_applied`,
`vm_ref_<id>`), so even if the per-step action POST fails, the local
state advances and the user can complete the flow. Actions retry on
next online state via the SW's `vm-offline` notify (then a queued
POST on next online event).

### 10.17 Chat history empty on cold visit

`screenHistory` first paints from local cache (today's `vm_messages`)
so the user never stares at a blank screen waiting for `/conversations`
to return.

### 10.18 Stopping audio between screen changes

`router()` calls `stopAudio()` before painting the new screen, so the
voice that was reading the response stops the instant the user
navigates away.

### 10.19 The two-column "viewport simulator"

A floating bottom-right pill lets the demo audience pick **Mobile /
Tablet / Desktop / Auto**. Forces a CSS layout regardless of actual
window size by setting `body[data-viewport=…]`. Choice persists in
`localStorage.vm_viewport` and is read by `admin.html` so the trust
dashboard inherits the same simulated viewport when opened.

### 10.20 Applied-cap removed

We previously capped active applications at 3; that's gone. Users can
have N concurrent applications; My Apps shows them newest-first.

### 10.21 CORS

Backend in production mode (`ENVIRONMENT=production`) uses
`allow_origins=[FRONTEND_ORIGIN]` exact match. The
`FRONTEND_ORIGIN` env var is set to the deployed static-site URL.
Dev mode uses an `allow_origin_regex` matching `localhost` /
`127.0.0.1` so we don't have to reconfigure for the dev box.

### 10.22 Service-worker cross-origin passthrough

The SW's fetch handler returns early for any request whose origin
differs from the SW's own origin. Without this, the SW's path-based
routing would catch `/api/v1/conversation/.../voice` on the BACKEND's
domain too, and its internal `fetch(req)` would throw on cross-origin
POSTs, surfacing as a false "Internet nahi mil raha · backend offline"
toast on every mic tap.

### 10.23 Sarvam STT returning English mid-sentence

When Saaras transcribes a Hinglish phrase like "main kissan hu" (with
double-s misspelling), the Devanagari transcript may include partial
Roman fragments. Our threshold of 0.36 + the bilingual intent chunks
absorb most of this. Worst case: query falls below threshold → refuses.
Better-than-hallucinating.

### 10.24 Eligibility extraction returns null facts

If Sarvam-m can't extract any of the 8 facts from a short transcript
("मुझे loan चाहिए"), the eligibility service returns all rules as
`unk` status. UI shows them with `?` icons. User can still see the
rules and see what they would need to provide to evaluate properly.

### 10.25 Multiple device IDs from the same user

Each browser session gets its own `vm_conversation_id`. No identity
linking. Trust dashboard aggregates across all conversation IDs.

---

## 11. Performance characteristics

| Operation | Cold | Warm |
|---|---|---|
| Frontend first paint | ~500 ms | ~150 ms (SW cache) |
| Backend cold start (Render free) | 45–90 s | 0 |
| OpenAI embedding (India → US) | ~3–5 s | 200–500 ms |
| Pinecone retrieval | ~100–500 ms | ~50–200 ms |
| Sarvam-m answer LLM call | 5–7 s | 4–6 s |
| Sarvam-m eligibility LLM call | 3–10 s | 2–5 s |
| Sarvam Bulbul TTS | 3–5 s | 2–3 s |
| Sarvam Saaras STT | 1–2 s | 1–2 s |
| `/chat` wall-clock | ~18–25 s first | ~13 s steady |
| `/voice` wall-clock | ~22–30 s first | ~18 s steady |

Headline win during MVP build: latency cut from ~25 s → ~13 s
steady-state via (a) module-level singleton clients, (b) persistent
httpx connection pools to Sarvam, (c) parallel `asyncio.gather` of
answer + eligibility + TTS.

The remaining ~4s steady-state RAG block is dominated by OpenAI
embedding network roundtrip (India → US-East). Moving to an
India-hosted embedder (Cohere India or self-hosted MiniLM) would
shave 2–3 s; out of scope for this MVP.

---

## 12. Known limitations and roadmap candidates

| Limitation | Workaround | Roadmap fix |
|---|---|---|
| Backend cold-start on free tier | Keep one tab open in advance | Upgrade to Starter ($7/mo) for always-on |
| English language toggle is UI-only | None | Add English LLM system prompt + voice |
| Eligibility checker ignores some structured rules | Use detail page's checklist | Move to deterministic rule engine for facts engine cant extract |
| Sarvam Saaras may transcribe noisy environments poorly | Quiet room demo | None planned |
| No deep linking inside the app | Hash routes work | Server-side rendering not on roadmap |
| Admin auth | None (public dashboard) | Add basic auth for `/admin.html` if needed |
| No internationalization framework | Mixed-script strings inline in HTML | Out of scope for MVP |
| Single-region backend | Latency from India ~200ms RTT | Multi-region not on roadmap |
| Image / illustration content | None | Could add for low-literacy support |

---

## 13. How to run the regression suite

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/test_persona.py -v
```

53 test cases:
- 3 persona happy paths (Sushila → PMJDY, Ramesh → KCC, Pooja → PMJJBY)
- 50 adversarial (10 each: fake_scheme, off_topic, sensitive_data,
  out_of_scope, edge_dialect)

Last full run: **42 / 53 pass** (79%). The 11 failures are documented in
the Sprint H verify scorecard — mostly assertion brittleness against
the new Devanagari output, not real correctness regressions.

Trust-metrics injection demo:
```bash
.venv/Scripts/python.exe _inject_hallucination.py 8
# Then refresh /admin.html — hallucination_rate card flips red.
```

---

## 14. What the user actually experiences in 90 seconds

1. **0–5 s**: Opens
   `https://voice-matters-web.onrender.com` on phone. Sees the home
   screen with greeting + chips + mic.
2. **5–10 s**: Taps mic. Grants permission. Speaks: *"मैं किसान हूँ
   खेती के लिए लोन चाहिए"*.
3. **10–14 s**: Stops talking. After ~5 s of silence the recording
   auto-ends. UI shows processing.
4. **14–32 s** (warm) or **~75 s** (cold): Backend pipeline runs.
5. **32 s**: Response card slides in. Devanagari title "किसान क्रेडिट
   कार्ड", pitch "खेती और पशुपालन के लिए 4% ब्याज पर लोन — 5 साल का
   credit card", source "✓ सरकारी स्रोत · Kisan Credit Card".
6. **32–55 s**: Sarvam Bulbul speaks the answer aloud. User listens
   passively.
7. **55–60 s**: Taps **सभी विकल्प देखो**. Sees 3 scheme cards.
8. **60–65 s**: Taps **आगे बढ़ो** on KCC. Sees detail page: benefits,
   eligibility, documents, helpline `1800-180-1551` with "Call Now".
9. **65–70 s**: Scrolls. Taps **आवेदन करें**. Step 1 of 4 is current,
   rest locked.
10. **70–75 s**: Taps **यह कैसे पता चला?** (Samjhao) on a previous
    response. Modal opens with evidence: "Kyon sahi lag raha hai" +
    "Source: rbidocs.rbi.org.in" + community confidence bar.
11. **75–90 s**: Closes modal, taps History to see the question + answer
    persisted with a timestamp and "Searched" badge.

That's the demo.

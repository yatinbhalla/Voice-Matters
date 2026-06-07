# Demo Script — BITSOM Panel

Single demo, ~90 seconds. One query, one screen tour. Designed to land
the product's three claims: **Hindi-first, trustworthy, end-to-end**.

---

## Setup (do this before the panel starts)

1. Open `https://voice-matters-web.onrender.com` in a clean Chrome tab,
   ideally in incognito so no stale SW.
2. Tap the mic button once with no audio (just to wake the backend
   cold-start). Wait until you see *"Sun raha hoon"* — then tap to
   cancel. Backend is now warm.
3. Verify viewport switcher (bottom-right) is set to **Mobile** if you
   want to demo the phone-form factor, **Desktop** if showing the full
   sidebar. Both work.
4. Keep `https://voice-matters-web.onrender.com/admin.html` open in a
   second tab — you'll switch to it at the end.

---

## The query

Speak this, in Hindi, into the mic:

> **मैं अकेले अपनी बेटी को पाल रही हूँ, अगर मुझे कुछ हो जाए तो उसका
> क्या होगा, सस्ता बीमा चाहिए.**
>
> *I'm raising my daughter alone — if something happens to me, what
> happens to her? I need cheap insurance.*

**Why this query**: emotionally resonant (single-mother), specific
(insurance), open-ended (no scheme name mentioned). Forces the system
to do real semantic matching, not keyword spotting.

---

## What the user will see (and what you narrate)

### Stage 1: Capture (0–10 s)

- User taps mic, grants permission.
- Animated waveform + rings while recording.
- 5 seconds of silence after she finishes → auto-stop (no need to
  tap again).

**Narrate**: *"The user just spoke in Hindi. Notice we never asked her
to name a scheme. The system has to understand intent."*

### Stage 2: Processing (10–15 s)

- "Sukshma minute…" + spinner on the mic button.
- Behind the scenes: Sarvam Saaras STT → OpenAI embedding → Pinecone
  retrieval → Sarvam-m LLM answer + eligibility check (in parallel)
  → Sarvam Bulbul TTS.

**Narrate**: *"Every layer of the pipeline is running. STT, embedding,
retrieval, LLM generation, eligibility extraction, text-to-speech —
all in about 12 seconds."*

### Stage 3: Response (15–20 s)

The response card slides in with:

- **Top match**: प्रधानमंत्री जीवन ज्योति बीमा योजना (PMJJBY)
- **One-line pitch**: "₹436 साल में ₹2 लाख का जीवन बीमा"
- **Source row** with green tick: ✓ सरकारी स्रोत · PMJJBY
- **Voice plays automatically** — Bulbul TTS reads the LLM's Devanagari
  answer in a natural Hindi voice
- Samjhao link: "यह कैसे पता चला? · How do I know this?"
- Feedback row: thumbs up/down + "Sahi jawab" / "Helpful scheme" chips
- CTA: "सभी विकल्प देखो · See all 3 options"

**Narrate**: *"The system identified PM Jeevan Jyoti — life insurance
at ₹436 per year for ₹2 lakh of cover. Exactly what a single mother
worried about her daughter's future needs. The answer is in Devanagari
Hindi — no English-accented mispronunciation. And the source is cited
right there."*

### Stage 4: Three-option view (20–35 s)

Tap **सभी विकल्प देखो**. Schemes screen shows top 3:

1. **PMJJBY** (gold ribbon — best match) — life insurance
2. **DAY-NRLM** (supporting) — SHG livelihood for women
3. **PMJDY** (supporting) — bank account (prerequisite for PMJJBY)

**Narrate**: *"Three relevant schemes, ranked. PMJJBY is the answer to
her question. DAY-NRLM is the women's self-help group programme — it
addresses her broader livelihood. PMJDY is the bank account she'll
need to enrol in PMJJBY. The system understood not just the question
but the surrounding context."*

### Stage 5: Trust / evidence (35–50 s)

Tap **यह कैसे पता चला?** (Samjhao). Modal opens with:

- *"PMJJBY सिर्फ ₹436 में ₹2 लाख का जीवन बीमा देती है, जो आपके
  परिवार की आर्थिक सुरक्षा के लिए ज़रूरी है..."* (LLM's evidence)
- Verified source row: **✓ सरकारी सोर्स · verified** + URL link to
  jansuraksha.gov.in
- **Confidence card**: "पक्की जानकारी · Verified" + the matched span
- **Social proof**: "87% logon ke liye sahi tha · 4,030 votes"
- "ग़लत लग रहा है? बताइए" button

**Narrate**: *"This is the trust layer. Every answer carries its
evidence: the exact text the model retrieved, the source URL it came
from, and the community votes from previous users. Nothing is invented
— if we don't have a confident match, we refuse rather than
hallucinate."*

### Stage 6: Detail page (50–65 s)

Close the modal, tap **आगे बढ़ो** on the PMJJBY card. Detail screen:

- Hero: scheme name (DEV primary), ministry badge, match-confidence
- 3-stat strip: ₹2 lakh cover · ₹436 premium · 1 year renewable
- About (Devanagari)
- Benefits list (head + sub)
- Eligibility checklist
- Documents grid (Aadhaar, bank passbook, mobile)
- Links & Support — **Toll-free helpline** `1800-180-1111` with a
  "Call Now" button

**Narrate**: *"Full detail, in Hindi. Toll-free helpline visible —
tap the number, it dials. Documents listed. This is the bridge from
'I learned about it' to 'I can act on it'."*

### Stage 7: Apply flow (65–80 s)

Tap **आवेदन करें · How to Apply**. Steps screen:

- Progress bar "Step 1 of 5 · 0%"
- Documents tray (4 ready / X missing)
- Step 1 card is "current" with "Abhi" badge

Tap **पूरा हो गया · Done** on Step 1 to show the progress advance.

**Narrate**: *"Step-by-step walkthrough. The user's progress is
persisted in their browser, so they can come back tomorrow and pick up
where they left off. Reference number generated on completion."*

### Stage 8: Trust dashboard (80–90 s)

Switch to the **/admin.html** tab.

- 6 metric cards: hallucination rate, eligibility false-positive,
  comprehension pass rate, refusal rate, p95 latency, citation rate.
- Each card shows current value vs target, PASS or FAIL.

**Narrate**: *"And here's the operations side. We're measuring whether
the system is actually trustworthy in production. Hallucination rate
is at 1%, target is 2% — green. Eligibility false-positive is 0% —
green. If hallucinations spike, the card flips red and the team gets
paged. This is the trust + accuracy proof point for a panel of
non-technical users."*

---

## Backup queries (if the demo query somehow refuses)

| Query | Expected top match |
|---|---|
| `मैं किसान हूँ, खेती के लिए सस्ता लोन चाहिए` | **KCC** (Kisan Credit Card) |
| `मेरे पास बैंक खाता नहीं है, मुफ्त में खुलवाना है` | **PMJDY** (Jan Dhan) |
| `घर में चूल्हा है, गैस कैसे मिलेगी` | **PMUY** (Ujjwala) |
| `दुकान खोलनी है, थोड़ा सा लोन चाहिए` | **PMMY** (Mudra) |
| `मैं महिला हूँ, स्वयं सहायता समूह से जुड़ना है` | **DAY-NRLM** |

---

## What to do if the backend is sleeping

If your first mic tap shows "Sun raha hoon" for >30 seconds without
moving to "Sukshma minute…", the backend is in cold-start. Tap to
cancel, wait 20 seconds, try again. Or hit
`https://voice-matters-n66k.onrender.com/health` from a tab to wake
it before the panel starts.

---

## What to NOT do during the demo

- Don't tap mic multiple times rapidly — the SW + audio race-guard
  handles it, but visually it can look broken.
- Don't switch viewport during recording — it stops the mic stream.
- Don't promise things outside the 7-scheme corpus. The judges may ask
  "what about PMAY?" — say *"we ingested 7 schemes for the MVP, adding
  more is just a JSON file + re-ingest, takes 90 seconds."*

---

## Three lines to close the demo

1. *"We picked 7 schemes that cover banking, agriculture, energy,
   livelihood, insurance, MSME, and state health — the breadth of
   what an Indian household actually needs."*
2. *"Every answer is grounded in indexed official sources. The system
   refuses rather than hallucinates — that's the trust dashboard
   you just saw."*
3. *"Deployed on Render, free tier, accessible at
   `voice-matters-web.onrender.com` from any phone with a mic and an
   internet connection. The codebase is open on GitHub."*

That's the demo.

FROM python:3.11-slim

WORKDIR /app

# ffmpeg is required for voice-pipeline audio normalization (Sarvam STT
# expects 16kHz mono PCM). build-essential covers asyncpg / cryptography
# binary wheels falling back to source builds.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Build context is the REPO ROOT (set by render.yaml's dockerContext).
# All paths below are relative to that root.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend code -> /app  (so `from main import app` works inside /app)
COPY backend/ /app/

# Scheme corpus -> /scheme-corpus  (so data/scheme_corpus.py's
# Path(__file__).parent.parent.parent / "scheme-corpus" / "schemes" /
# "processed" resolves to /scheme-corpus/schemes/processed inside the
# container, matching the local dev path-resolution exactly).
COPY scheme-corpus/ /scheme-corpus/

# Render injects the port via $PORT (default 10000). Fall back to 8080 for
# local docker runs. uvicorn binds to 0.0.0.0 so the platform can route.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]

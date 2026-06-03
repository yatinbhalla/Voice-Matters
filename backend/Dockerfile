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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects the port via $PORT (default 10000). Fall back to 8080 for
# local docker runs. uvicorn binds to 0.0.0.0 so the platform can route.
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]

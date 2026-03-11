# ── Build stage: install Python deps + pre-cache embedding model ──
FROM python:3.14-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Pre-download the sentence-transformers model (~80 MB) so the runtime
# image never hits the network on first request.
ENV HF_HOME=/model_cache
ENV PYTHONPATH=/install/lib/python3.14/site-packages
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ── Runtime stage ──
FROM python:3.14-slim

ARG VERSION=dev
LABEL org.opencontainers.image.version=$VERSION

# tini: proper PID 1 for signal forwarding (graceful uvicorn shutdown).
# curl: used by Docker health checks.
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini curl && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -g 10001 synthesis && \
    useradd -u 10001 -g synthesis -s /sbin/nologin -M synthesis

WORKDIR /app

# Python packages
COPY --from=builder /install/lib /usr/local/lib
COPY --from=builder /install/bin /usr/local/bin

# Pre-cached embedding model
COPY --from=builder /model_cache /app/.cache_hf
ENV HF_HOME=/app/.cache_hf

# Application source
COPY . .

# Writable data directory (mounted as volume in production)
RUN mkdir -p data && chown -R synthesis:synthesis data /app/.cache_hf

ENV PYTHONUNBUFFERED=1

USER synthesis
EXPOSE 8000

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "app.main:asgi_app", "--host", "0.0.0.0", "--port", "8000"]

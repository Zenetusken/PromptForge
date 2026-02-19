FROM python:3.14-slim AS base

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency spec first for layer caching
COPY pyproject.toml ./
# Create minimal package structure so pip can resolve the package
RUN mkdir -p app && touch app/__init__.py
RUN pip install --no-cache-dir ".[all-providers]"

# Copy application code
COPY . .

# Create non-root user
RUN useradd -r -s /bin/false appuser && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app/data
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

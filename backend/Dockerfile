# ──────────────────────────────────────────────────────────────────────────────
# Enceladus Mission Control — Backend Dockerfile
# Uses uv for reproducible builds and fast layer caching
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Create virtualenv and install deps (no editable install)
RUN uv sync --frozen --no-dev

# Copy application source
COPY . .

# Expose API port
EXPOSE 8000

# Run via uv so the managed venv is used
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# ============================================================
# AI Data Analyst — Multi-Stage Dockerfile (Frontend + Backend)
# Target: Azure Container Apps (Linux/amd64)
# ============================================================

# ---- Stage 1: Frontend builder ----
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --quiet
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python dependency builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

# System libraries needed by weasyprint (PDF) and matplotlib (headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libssl-dev \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt


# ---- Stage 3: Runtime image ----
FROM python:3.11-slim AS runtime

# Non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Runtime system libs (same as builder, no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application source
COPY agents/       ./agents/
COPY api/          ./api/
COPY state/        ./state/
COPY tools/        ./tools/
COPY agent/        ./agent/
COPY config.py     ./config.py
COPY llm.py        ./llm.py
COPY graph.py      ./graph.py
COPY state.py      ./state.py
COPY app.py        ./app.py

# Copy built frontend static assets from Stage 1 (.output/public from TanStack Start)
COPY --from=frontend-builder /app/frontend/.output/public ./frontend/dist

# Pre-create output directories and set ownership
RUN mkdir -p output/profiles output/analysis output/reports uploads && \
    chown -R appuser:appuser /app

USER appuser

# Expose the FastAPI port
EXPOSE 8000

# Health check — Azure Container Apps polls this
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start uvicorn with production settings
CMD ["python", "-m", "uvicorn", "api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--timeout-keep-alive", "300", \
     "--log-level", "info"]


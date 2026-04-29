# Backend Dockerfile for TradeAdviser - Production Ready with Security Hardening
# Build:
#   docker build -f Dockerfile.backend -t tradeadviser-backend .
#
# Run:
#   docker run -p 8000:8000 \
#   -e DATABASE_URL=postgresql+asyncpg://user:pass@host/db \
#   tradeadviser-backend

# =========================
# Builder image
# =========================
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY server/app/backend/requirements.txt ./requirements.txt

# Build Python wheels
RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt


# =========================
# Production image
# =========================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/server \
    ENV=production \
    DEBUG=false

WORKDIR /app/server

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy wheels from builder
COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt ./requirements.txt

# Install Python dependencies from wheels
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Copy application code
COPY . /app/server/

# Create necessary directories and set permissions
RUN mkdir -p /app/server/app/frontend/dist /app/logs && \
    chown -R appuser:appuser /app/server /app/logs && \
    chmod -R 750 /app/server /app/logs

# Switch to non-root user
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start backend
CMD ["python", "main.py"]
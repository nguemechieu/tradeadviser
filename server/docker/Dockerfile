FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY server/app/frontend/package.json ./package.json
COPY server/app/frontend/vite.config.js ./vite.config.js
COPY server/app/frontend/index.html ./index.html
COPY server/app/frontend/src ./src

RUN npm install && npm run build


FROM python:3.12.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Install system dependencies and security updates
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy server requirements
COPY sqs_server/app/backend/requirements.txt ./requirements.txt

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r ./requirements.txt

# Copy shared modules (accessible via 'from shared import ...')
COPY shared/ ./shared/

# Copy server application structure (accessible via 'from app import ...')
COPY sqs_server/app/ ./app/
COPY --from=frontend-build /frontend/dist ./app/frontend/dist

# Copy entrypoint script
COPY sqs_server/docker/entrypoint.sh ./entrypoint.sh

# Set proper permissions
RUN chmod +x ./entrypoint.sh && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]



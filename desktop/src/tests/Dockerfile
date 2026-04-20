# -------- Builder Stage --------
FROM python:3.11-slim AS builder

WORKDIR /app
COPY pyproject.toml .
COPY ../sopotek_trading ./src

RUN pip install --upgrade pip setuptools wheel \
    && pip wheel --no-cache-dir --wheel-dir /wheels .

# -------- Runtime Stage --------
FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache /wheels/*

COPY ../sopotek_trading ./src

CMD ["python", "-m", "sopotek_trading"]
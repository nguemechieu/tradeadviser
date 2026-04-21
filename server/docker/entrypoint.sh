#!/bin/sh
set -e

echo "[Startup] Starting SQS Server..."

# Check if database connection is needed
if [ -n "$DATABASE_URL" ]; then
    echo "[Startup] Testing database connection..."
    python - <<'PY'
import asyncio
import os

try:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    
    if DATABASE_URL:
        async def test_db() -> None:
            engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
            for attempt in range(30):
                try:
                    async with engine.begin() as connection:
                        await connection.execute(text("SELECT 1"))
                    await engine.dispose()
                    print("[Startup] Database connection successful", flush=True)
                    return
                except Exception as exc:
                    if attempt == 29:
                        raise
                    print(f"[Startup] Waiting for database: {exc}", flush=True)
                    await asyncio.sleep(2)
        
        asyncio.run(test_db())
except ImportError:
    print("[Startup] SQLAlchemy not installed, skipping database check", flush=True)
except Exception as e:
    print(f"[Startup] Database check failed: {e}, continuing anyway", flush=True)
PY
else
    echo "[Startup] DATABASE_URL not set, skipping database check"
fi

echo "[Startup] Application starting..."
exec "$@"


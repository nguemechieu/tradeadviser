"""Lightweight FastAPI shell for the desktop/server integration contract."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add project root to path for shared imports
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

from backend.api.routes.auth import router as auth_router
from backend.api.routes.admin import router as admin_router
from backend.api.routes.agents import router as agents_router
from backend.api.routes.operations import router as operations_router
from backend.api.routes.performance import router as performance_router
from backend.api.routes.performance_audit import router as performance_audit_router
from backend.api.routes.portfolio import router as portfolio_router
from backend.api.routes.risk import router as risk_router
from backend.api.routes.session import router as session_router
from backend.api.routes.signals import router as signals_router
from backend.api.routes.trades import router as trades_router
from backend.api.routes.trading import router as trading_router
from backend.api.routes.users_licenses import router as users_licenses_router
from backend.api.routes.workspace import router as workspace_router
from backend.dependencies import get_services


FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"
RESERVED_FRONTEND_PREFIXES = {
    "admin",
    "api",
    "auth",
    "docs",
    "health",
    "openapi.json",
    "performance",
    "portfolio",
    "redoc",
    "signals",
    "trades",
    "workspace",
    "ws",
}

# Create FastAPI app
app = FastAPI(
    title="Sopotek Quant System Server",
    description="Server backend for the Sopotek Quant System desktop and web applications",
    version="1.0.0",
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(agents_router)
app.include_router(operations_router)
app.include_router(performance_router)
app.include_router(performance_audit_router)
app.include_router(portfolio_router)
app.include_router(risk_router)
app.include_router(session_router)
app.include_router(signals_router)
app.include_router(trades_router)
app.include_router(trading_router)
app.include_router(users_licenses_router)
app.include_router(workspace_router)

# Mount frontend assets if they exist
frontend_assets = FRONTEND_DIST / "assets"
if frontend_assets.exists():
    app.mount("/assets", StaticFiles(directory=frontend_assets), name="frontend-assets")


# Startup and shutdown events
@app.on_event("startup")
async def startup_event() -> None:
    """Initialize server resources on startup."""
    logger.info("Server startup event")
    try:
        services = get_services()
        logger.info(f"Services initialized successfully")
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Clean up server resources on shutdown."""
    logger.info("Server shutdown event")


# API Routes


@app.get("/health", tags=["system"])
async def health() -> dict[str, Any]:
    """Health route used by Docker and the desktop startup flow.
    
    Returns:
        dict: Health status including service name and status
    """
    try:
        return get_services().health_snapshot()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"service": "Sopotek Quant System", "status": "error", "error": str(e)}


@app.get("/", tags=["system"])
async def root() -> Any:
    """Root endpoint.
    
    Serves the frontend if built, otherwise returns service info.
    """
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    try:
        snapshot = get_services().health_snapshot()
        return {"service": snapshot.get("service"), "status": snapshot.get("status")}
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        return {"service": "Sopotek Quant System", "status": "ok"}


@app.websocket("/ws/events")
async def events_socket(websocket: WebSocket) -> None:
    """Desktop event stream endpoint.

    The reconnect contract uses ``session_id`` and ``last_sequence`` query
    parameters so the server can later rehydrate authoritative state.
    
    Args:
        websocket: WebSocket connection from the client
    """
    services = get_services()
    try:
        await websocket.accept()
    except Exception as e:
        logger.error(f"WebSocket accept failed: {e}")
        return

    session_id = str(websocket.query_params.get("session_id") or "").strip()
    correlation_id = str(websocket.query_params.get("correlation_id") or "").strip() or None
    
    logger.debug(f"WebSocket connection: session_id={session_id}")
    
    try:
        await services.register_connection(session_id, websocket)

        # Send session validated event
        await services.send_event(
            session_id,
            "session_validated",
            {"session_id": session_id, "status": "connected"},
            correlation_id=correlation_id,
        )

        # Send existing market subscription if present
        subscription = dict(services.market_data_subscriptions.get(session_id, {}) or {})
        if subscription:
            await services.send_event(
                session_id,
                "market_subscription_updated",
                dict(subscription),
                correlation_id=correlation_id,
            )

        # Keep connection alive
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                logger.debug(f"WebSocket disconnected: session_id={session_id}")
                break
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                break
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        await services.unregister_connection(session_id, websocket)
        logger.debug(f"WebSocket connection closed: session_id={session_id}")


@app.get("/{full_path:path}", include_in_schema=False)
async def frontend_routes(full_path: str) -> Any:
    """Serve the built React frontend with SPA-style fallback behavior.
    
    Args:
        full_path: The requested path
        
    Returns:
        FileResponse or JSONResponse
    """
    if not FRONTEND_INDEX.exists():
        return JSONResponse(
            status_code=404,
            content={"error": "Frontend bundle has not been built."},
        )

    normalized = str(full_path or "").strip().lstrip("/")
    leading_segment = normalized.split("/", 1)[0]
    
    # Check if this is an API route
    if leading_segment in RESERVED_FRONTEND_PREFIXES:
        return JSONResponse(
            status_code=404,
            content={"error": "Route not found."},
        )

    # Try to serve static file
    candidate = (FRONTEND_DIST / normalized).resolve() if normalized else FRONTEND_INDEX.resolve()
    if normalized and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
        return FileResponse(candidate)

    # Fallback to index.html for SPA routing
    return FileResponse(FRONTEND_INDEX)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )

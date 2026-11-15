"""FastAPI application entrypoint for AutoAnalyst."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes_runs import router as runs_router
from backend.app.api.routes_upload import router as upload_router
from backend.app.api.websocket import router as ws_router
from backend.app.core.event_store import event_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context initializing databases and background resources."""
    await event_store.init_db()
    yield


app = FastAPI(
    title="AutoAnalyst API",
    description="Autonomous data-science agent with sandboxed code execution and human review.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for local React/Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(upload_router)
app.include_router(runs_router)
app.include_router(ws_router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "AutoAnalyst"}

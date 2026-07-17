from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.graph_routes import router as graph_router
from app.core.config import settings
import structlog
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = structlog.get_logger()

# Setup Rate Limiting
limiter = Limiter(key_func=get_remote_address)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    LEARNING POINT: Lifespan Events
    In modern FastAPI, the 'lifespan' context manager is the preferred way to handle
    startup and shutdown logic. It replaces the older @app.on_event("startup") and
    @app.on_event("shutdown") decorators.

    Everything before 'yield' runs on STARTUP.
    Everything after 'yield' runs on SHUTDOWN.
    """
    # STARTUP LOGIC
    logger.info("Application starting up...")

    # Setup directories for file uploads
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    yield

    # SHUTDOWN LOGIC
    logger.info("Application shutting down...")

app = FastAPI(
    title="PDF RAG API",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(graph_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Welcome to PDF RAG API"}

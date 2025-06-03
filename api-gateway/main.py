# main.py - FastAPI Application Entry Point
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import time

# Internal imports
from config.settings import get_settings
from contextlib import asynccontextmanager
from core.dependencies import get_redis_client
from models.responses import HealthStatusResponse 

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan context manager for startup/shutdown 
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting GenoFlow API Gateway...")

    # Initialize Redis connection
    redis_client = await get_redis_client()
    app.state.redis = redis_client # Store redis client in app.state
    logger.info("Redis client initialized.")

    yield

    # Shutdown
    logger.info("Shutting down GenoFlow API Gateway...")
    if hasattr(app.state, 'redis'):
        await app.state.redis.close()
        logger.info("Redis client closed.")
    logger.info("GenoFlow API Gateway shutdown complete")

# Create FastAPI application
def create_application() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="GenoFlow API Gateway",
        description="Clinical Sequencing Pipeline API Gateway",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan 
    )

    # Add CORS middleware (essential for frontend interaction)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get("/health", response_model=HealthStatusResponse)
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "version": "1.0.0"
        }

    # Root endpoint
    @app.get("/")
    async def root():
        return {
            "message": "GenoFlow API Gateway",
            "version": "1.0.0",
            "docs": "/docs"
        }

    return app

# Create the app instance
app = create_application()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
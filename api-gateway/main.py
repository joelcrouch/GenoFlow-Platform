# main.py - FastAPI Application Entry Point
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from core.middleware import ErrorHandlingMiddleware, LoggingMiddleware, RateLimitMiddleware
from pydantic import BaseModel

import datetime
import logging
import time
import uvicorn

# Internal imports
from config.settings import get_settings
from contextlib import asynccontextmanager
from core.dependencies import get_redis_client
from models.responses import HealthStatusResponse 

# Routes imports
from api.routes.auth import auth_router # Import the router object

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

# This function CREATES and configures the FastAPI application.
# It should be the ONLY place where an app instance is configured.
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

    app.add_middleware(GZipMiddleware, minimum_size=1000) # Only compress responses > 1KB
    app.add_middleware(ErrorHandlingMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    
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
    
    # Include the authentication router
    app.include_router(auth_router, prefix="/auth") # <-- Router inclusion moved here!
    
    return app


# This block ensures that 'app' is only instantiated and run when main.py is executed directly.
# When main.py is imported (e.g., by pytest or another module), this block is skipped.
if __name__ == "__main__":
    app = create_application() # <-- App creation moved here!
    settings = get_settings() # You'll need settings for uvicorn.run
    uvicorn.run(
        "main:app", # Note: 'main:app' assumes 'app' is at top-level. 
                     # If you move app = create_application() inside this block, 
                     # you might need to run uvicorn with --factory:
                     # uvicorn main:create_application --factory
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )

# The 'app' variable should NOT be defined at the top level outside of __main__
# if you want proper test isolation with 'create_application()'.
# Remove the old `app = create_application()` and `app.include_router(...)` lines outside this block.



# # main.py - FastAPI Application Entry Point
# from fastapi import FastAPI, Depends, HTTPException, status
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.middleware.gzip import GZipMiddleware
# from core.middleware import ErrorHandlingMiddleware, LoggingMiddleware, RateLimitMiddleware# order of improts matters for middleware?
# from pydantic import BaseModel

# import datetime
# import logging
# import time
# import uvicorn

# # Internal imports
# from config.settings import get_settings
# from contextlib import asynccontextmanager
# from core.dependencies import get_redis_client
# from models.responses import HealthStatusResponse 

# # Routes imports
# from api.routes.auth import auth_router

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Lifespan context manager for startup/shutdown 
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup
#     logger.info("Starting GenoFlow API Gateway...")

#     # Initialize Redis connection
#     redis_client = await get_redis_client()
#     app.state.redis = redis_client # Store redis client in app.state
#     logger.info("Redis client initialized.")

#     # Initialize AuthHandler with secret key
#     # This ensures the AuthHandler is ready for use, though get_auth_handler() also initializes it.
#     # It's good practice to ensure core components are set up during lifespan.
#     # (No direct action needed here as get_auth_handler() is a dependency)
    
#     yield

#     # Shutdown
#     logger.info("Shutting down GenoFlow API Gateway...")
#     if hasattr(app.state, 'redis'):
#         await app.state.redis.close()
#         logger.info("Redis client closed.")
#     logger.info("GenoFlow API Gateway shutdown complete")

# # Create FastAPI application
# def create_application() -> FastAPI:
#     settings = get_settings()

#     app = FastAPI(
#         title="GenoFlow API Gateway",
#         description="Clinical Sequencing Pipeline API Gateway",
#         version="1.0.0",
#         docs_url="/docs",
#         redoc_url="/redoc",
#         lifespan=lifespan 
#     )

#     # Add CORS middleware (essential for frontend interaction)
#     app.add_middleware(
#         CORSMiddleware,
#         allow_origins=settings.allowed_origins,
#         allow_credentials=True,
#         allow_methods=["*"],
#         allow_headers=["*"],
#     )

#     app.add_middleware(GZipMiddleware, minimum_size=1000) # Only compress responses > 1KB
#     # --- ADD ERROR HANDLING MIDDLEWARE HERE ---  is it here that order matters? or in imports?
#     app.add_middleware(ErrorHandlingMiddleware)
#     app.add_middleware(LoggingMiddleware)
#     app.add_middleware(RateLimitMiddleware)
#     # Health check endpoint
#     @app.get("/health", response_model=HealthStatusResponse)
#     async def health_check():
#         return {
#             "status": "healthy",
#             "timestamp": time.time(),
#             "version": "1.0.0"
#         }

#     # Root endpoint
#     @app.get("/")
#     async def root():
#         return {
#             "message": "GenoFlow API Gateway",
#             "version": "1.0.0",
#             "docs": "/docs"
#         }
#     # Include the authentication router
    
    
#     return app


# # Create the app instance
# app = create_application()
# app.include_router(auth_router, prefix="/auth") 
# # if __name__ == "__main__":
# #     settings = get_settings()
# #     uvicorn.run(
# #         "main:app",
# #         host=settings.host,
# #         port=settings.port,
# #         reload=settings.debug,
# #         log_level="info"
# #     )
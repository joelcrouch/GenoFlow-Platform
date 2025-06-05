#core/middleware.py

import logging
from collections import defaultdict
from fastapi import Request, Response, HTTPException, status
# from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from core.exceptions import UnauthorizedException, ForbiddenException
import time
from typing import Dict, Any, Union, List, Optional

logger=logging.getLogger(__name__)

class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
    async def dispatch(self, request: Request, call_next):
        try:
            response=await call_next(request)
            return response
        except StarletteHTTPException as exc:
            #cathc fastapi/starlette buiilt in httpexception
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail":exc.detail}
            )
        except Exception as e:
            logger.exception(f"Unhandled exception during request to {request.url.path}: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal Server Error"}
            )
 
# --- Logging Middleware ---
class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log request details
        logger.info(f"Incoming Request: {request.method} {request.url.path} from {request.client.host}")

        response = await call_next(request)

        process_time = time.time() - start_time
        # Log response details
        logger.info(f"Outgoing Response: {response.status_code} {request.method} {request.url.path} - Processed in {process_time:.4f}s")

        return response
    
    


# --- Rate Limiting Middleware (Simple In-Memory) ---
# NOTE: In a production environment, use a distributed rate limiter like Redis.
# This is a basic in-memory implementation for demonstration.
# REQUEST_COUNTS: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "last_reset_time": 0})
# RATE_LIMIT_DURATION_SECONDS = 60 # 1 minute
# RATE_LIMIT_MAX_REQUESTS = 10 # Max 10 requests per minute per client IP

# --- Rate Limiting Middleware (CRITICAL CHANGES HERE) ---
class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to limit the number of requests from a client within a time window.
    Its state (request counts) is now per-instance, not global.
    """
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # These are now instance variables, ensuring each middleware instance is isolated
        self.request_counts: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "last_reset_time": 0.0})
        self.rate_limit_duration_seconds = 60 # 1 minute
        self.rate_limit_max_requests = 10 # Max 10 requests per minute per client IP

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Use self.request_counts for the instance's state
        if current_time - self.request_counts[client_ip]["last_reset_time"] > self.rate_limit_duration_seconds:
            self.request_counts[client_ip]["count"] = 0
            self.request_counts[client_ip]["last_reset_time"] = current_time
        
        self.request_counts[client_ip]["count"] += 1

        if self.request_counts[client_ip]["count"] > self.rate_limit_max_requests:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}. Requests: {self.request_counts[client_ip]['count']}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Too many requests. Please try again later."}
            )
        
        response = await call_next(request)
        return response     

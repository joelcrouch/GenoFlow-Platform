#core/middleware.py

import logging
from fastapi import Request, Response, HTTPException, status
# from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from core.exceptions import UnauthorizedException, ForbiddenException

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
       

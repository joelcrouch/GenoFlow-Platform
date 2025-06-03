from pydantic import BaseModel
from typing import Any, Optional, Dict

class MessageResponse(BaseModel):
    """Generic response model for simple messages."""
    message: str

class ErrorResponse(BaseModel):
    """Generic response model for errors."""
    detail: str
    code: Optional[str] = None
    data: Optional[Dict[str, Any]] = None # Optional additional error data

class HealthStatusResponse(BaseModel):
    """Response model for the health check endpoint."""
    status: str
    timestamp: float
    version: str
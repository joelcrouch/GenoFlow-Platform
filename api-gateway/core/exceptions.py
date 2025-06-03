# core/exceptions.py

from fastapi import HTTPException, status

class ServiceUnavailableException(HTTPException):
    def __init__(self, service_name: str, detail: str = "Service is currently unavailable"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{service_name} {detail}"
        )

class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Not authorized to perform this action"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )

class NotFoundException(HTTPException):
    def __init__(self, resource_name: str = "Resource", detail: str = "not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource_name} {detail}"
        )

class BadRequestException(HTTPException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

class ConflictException(HTTPException):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )

class InternalServerErrorException(HTTPException):
    def __init__(self, detail: str = "Internal server error"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )
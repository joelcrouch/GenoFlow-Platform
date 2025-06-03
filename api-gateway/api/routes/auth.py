# api/routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List

from core.auth import get_auth_handler
from core.exceptions import UnauthorizedException
from models.user import UserCreate, UserPublic # We'll reuse these if we add user registration
from models.responses import MessageResponse

# --- Pydantic Models for Authentication ---
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # refresh_token: Optional[str] = None # Add if you implement refresh tokens

# --- Authentication Router ---
auth_router = APIRouter(tags=["Auth"]) # Add a tag for FastAPI docs

@auth_router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    auth_handler = Depends(get_auth_handler) # Get the singleton AuthHandler
):
    """Authenticate user and return JWT access token."""
    # NOTE: In a real application, you would fetch user data from a User Service
    # and verify the password against the stored hash.
    # For this minimal example, we'll use a hardcoded user for demonstration.

    if credentials.username == "admin" and auth_handler.verify_password(credentials.password, auth_handler.get_password_hash("password")):
        # Mock user data - replace with actual user service call
        user_id = "1"
        user_roles = ["admin", "user"]
        # Generate token
        access_token = auth_handler.encode_token(user_id=user_id, roles=user_roles)
        return TokenResponse(access_token=access_token)
    elif credentials.username == "testuser" and auth_handler.verify_password(credentials.password, auth_handler.get_password_hash("testpassword")):
        user_id = "2"
        user_roles = ["user"]
        access_token = auth_handler.encode_token(user_id=user_id, roles=user_roles)
        return TokenResponse(access_token=access_token)
    else:
        raise UnauthorizedException(detail="Invalid credentials")

# Example of a protected endpoint (requires authentication)
@auth_router.get("/protected-admin", response_model=MessageResponse, dependencies=[Depends(get_auth_handler().has_role(["admin"]))])
async def protected_admin_route():
    """
    A protected endpoint accessible only by 'admin' role.
    """
    return {"message": "You have access to admin-only content!"}

@auth_router.get("/protected-user", response_model=MessageResponse, dependencies=[Depends(get_auth_handler().has_role(["user"]))])
async def protected_user_route():
    """
    A protected endpoint accessible by 'user' or 'admin' roles.
    """
    return {"message": "You have access to user content!"}
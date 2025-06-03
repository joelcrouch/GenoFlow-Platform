# core/auth.py

from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config.settings import get_settings
from core.exceptions import UnauthorizedException # Ensure this is imported

# --- AuthHandler Class (for JWT and password management) ---
class AuthHandler:
    def __init__(self, secret_key: str):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = secret_key
        self.algorithm = "HS256"
        self.oauth2_scheme = HTTPBearer() # For extracting token from headers

    def get_password_hash(self, password: str) -> str:
        """Hashes a plain-text password."""
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain-text password against a hashed password."""
        return self.pwd_context.verify(plain_password, hashed_password)

    def encode_token(self, user_id: str, roles: list[str], expiration_minutes: int = 30) -> str:
        """Encodes a JWT token with user ID, roles, and an expiration."""
        to_encode = {
            "sub": user_id,
            "roles": roles, # Include roles in the token
            "exp": datetime.utcnow() + timedelta(minutes=expiration_minutes)
        }
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_token(self, token: str) -> dict:
        """Decodes a JWT token and raises UnauthorizedException on error or expiry."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            raise UnauthorizedException(detail=f"Invalid or expired token: {e}")

    # --- Dependency for current user extraction from token ---
    async def get_current_user_payload(self, token: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> dict:
        """Dependency to extract and decode the token from the Authorization header."""
        return self.decode_token(token.credentials)

    # --- Dependency for protecting routes (requires specific roles) ---
    def has_role(self, required_roles: list[str]):
        async def role_checker(payload: dict = Depends(self.get_current_user_payload)):
            user_roles = payload.get("roles", [])
            if not any(role in user_roles for role in required_roles):
                raise UnauthorizedException(detail="Insufficient permissions")
            return payload # Return payload if roles match
        return role_checker

# --- Dependency for providing AuthHandler instance ---
_auth_handler: Optional[AuthHandler] = None

def get_auth_handler() -> AuthHandler:
    global _auth_handler
    if _auth_handler is None:
        settings = get_settings()
        _auth_handler = AuthHandler(secret_key=settings.jwt_secret_key)
    return _auth_handler
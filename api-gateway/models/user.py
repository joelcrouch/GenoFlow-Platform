from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    """Base schema for user data."""
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False

class UserCreate(UserBase):
    """Schema for creating a new user, requires a password."""
    password: str = Field(min_length=8) # Passwords should be hashed, this is for input validation

class UserInDB(UserBase):
    """Schema for user data as stored in the database."""
    id: int
    hashed_password: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Pydantic v2 equivalent of orm_mode = True

class UserPublic(UserBase):
    """Schema for user data exposed to the public (excluding sensitive info like password hash)."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
"""User Schema Definitions"""

from pydantic import BaseModel, EmailStr
from typing import List


class UserSchema(BaseModel):
    """User information schema."""
    user_id: str
    email: str
    username: str
    display_name: str
    role: str
    is_active: bool
    permissions: List[str] = []
    
    class Config:
        from_attributes = True


class UserCreateSchema(BaseModel):
    """Schema for creating a new user."""
    email: EmailStr
    username: str
    password: str
    display_name: str | None = None
    role: str = "trader"


class UserUpdateSchema(BaseModel):
    """Schema for updating user information."""
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserResponseSchema(BaseModel):
    """Schema for user response."""
    user_id: str
    email: str
    username: str
    display_name: str
    role: str
    is_active: bool
    created_at: str | None = None
    
    class Config:
        from_attributes = True

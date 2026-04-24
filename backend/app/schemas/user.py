"""
User Schemas
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from backend.app.schemas.common import BaseSchema


class UserBase(BaseSchema):
    """Base user schema."""
    
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    organization: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None


class UserCreate(UserBase):
    """User creation schema."""
    
    password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserUpdate(BaseSchema):
    """User update schema."""
    
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    organization: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None
    settings: Optional[dict] = None


class UserResponse(UserBase):
    """User response schema."""
    
    id: UUID
    is_active: bool
    is_verified: bool
    roles: List[str]
    settings: dict
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None


class UserLogin(BaseModel):
    """User login schema."""
    
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    """Password change schema."""
    
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v

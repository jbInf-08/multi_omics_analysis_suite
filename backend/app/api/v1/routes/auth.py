"""
Authentication Routes
"""

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.core.database import get_db
from backend.app.core.security import (
    Token,
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    decode_token,
    get_current_user,
    TokenPayload,
)
from backend.app.core.config import settings
from backend.app.models.user import User
from backend.app.schemas.user import UserCreate, UserResponse, UserLogin


router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user."""
    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )
    
    # Create user
    user = User(
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        organization=user_data.organization,
        bio=user_data.bio,
        hashed_password=get_password_hash(user_data.password),
        roles=["user"],
        permissions=["read", "write"],
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


@router.post("/login", response_model=Token)
async def login(
    username: str = Form(),
    password: str = Form(),
    db: AsyncSession = Depends(get_db),
):
    """Login and get access token (OAuth2-compatible form: username, password)."""
    # Find user by email or username
    result = await db.execute(
        select(User).where(
            (User.email == username) | (User.username == username)
        )
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is disabled",
        )
    
    # Create tokens
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "roles": user.roles,
            "permissions": user.permissions,
        }
    )
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token."""
    payload = decode_token(refresh_token)
    
    if payload.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    
    # Get user
    result = await db.execute(select(User).where(User.id == UUID(payload.sub)))
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Create new tokens
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "roles": user.roles,
            "permissions": user.permissions,
        }
    )
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user information."""
    result = await db.execute(select(User).where(User.id == UUID(current_user.sub)))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return user


@router.post("/logout")
async def logout(current_user: TokenPayload = Depends(get_current_user)):
    """Logout current user."""
    # In a production environment, you would invalidate the token here
    # (e.g., add to a blacklist in Redis)
    return {"message": "Successfully logged out"}

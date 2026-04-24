"""Security Module.
===============

Authentication, authorization, and security utilities.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, field_validator

from backend.app.core.config import settings

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
_tools_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class Token(BaseModel):
    """JWT Token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    """JWT Token payload."""

    sub: str
    exp: int | datetime
    iat: int | datetime
    type: str  # access or refresh
    roles: list[str] = []
    permissions: list[str] = []

    @field_validator("exp", "iat", mode="before")
    @classmethod
    def convert_timestamp(cls, v: int | datetime) -> datetime:
        """Convert Unix timestamp to datetime if needed."""
        if isinstance(v, int):
            return datetime.fromtimestamp(v, tz=timezone.utc)
        return v


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash using bcrypt."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "type": "access",
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update(
        {
            "exp": expire,
            "iat": now,
            "type": "refresh",
        }
    )

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        return TokenPayload(**payload)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenPayload:
    """Get current authenticated user from token."""
    payload = decode_token(token)

    if payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    return payload


async def get_tools_authorization(
    token: str | None = Depends(oauth2_scheme_optional),
    x_api_key: str | None = Depends(_tools_api_key_header),
) -> TokenPayload:
    """Authenticate /api/v1/tools callers via JWT, optional X-API-Key, or anonymous (if enabled).

    Precedence: valid ``X-API-Key`` matching ``TOOLS_API_KEY`` → JWT Bearer → anonymous (if
    ``TOOLS_ALLOW_ANONYMOUS``) → 401.
    """
    now = datetime.now(timezone.utc)

    key = (settings.TOOLS_API_KEY or "").strip()
    if key and x_api_key and x_api_key.strip() == key:
        return TokenPayload(
            sub="tools-api-key",
            exp=int((now + timedelta(days=365)).timestamp()),
            iat=int(now.timestamp()),
            type="access",
        )

    if token:
        payload = decode_token(token)
        if payload.type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        return payload

    if settings.TOOLS_ALLOW_ANONYMOUS:
        return TokenPayload(
            sub="anonymous",
            exp=int((now + timedelta(hours=24)).timestamp()),
            iat=int(now.timestamp()),
            type="access",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated: provide Bearer token, X-API-Key, or enable TOOLS_ALLOW_ANONYMOUS",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def check_chemistry_tools_rate_limit(request: Request) -> None:
    """429 when client IP exceeds TOOLS_CHEMISTRY_RATE_LIMIT per period."""
    from backend.app.core.rate_limit import get_chemistry_rate_limiter

    if settings.TOOLS_CHEMISTRY_RATE_LIMIT <= 0:
        return
    limiter = get_chemistry_rate_limiter(
        settings.TOOLS_CHEMISTRY_RATE_LIMIT,
        float(settings.TOOLS_CHEMISTRY_RATE_PERIOD_SECONDS),
    )
    client_host = request.client.host if request.client else "unknown"
    limiter.check(client_host)


def check_permission(required_permission: str):
    """Dependency to check user permissions."""

    async def permission_checker(current_user: TokenPayload = Depends(get_current_user)):
        if required_permission not in current_user.permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return permission_checker


def check_role(required_role: str):
    """Dependency to check user role."""

    async def role_checker(current_user: TokenPayload = Depends(get_current_user)):
        if required_role not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current_user

    return role_checker

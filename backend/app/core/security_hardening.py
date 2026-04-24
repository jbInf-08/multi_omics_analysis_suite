"""
Security Hardening
==================

Rate limiting, input sanitization, secrets management, and audit logging.
"""

from typing import Any, Callable, Dict, List, Optional, TypeVar
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import hashlib
import hmac
import re
import secrets
import logging
import json
from uuid import UUID

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, validator


logger = logging.getLogger(__name__)


# =============================================================================
# Rate Limiting
# =============================================================================

@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests: int  # Number of requests
    period: int    # Time period in seconds
    burst: int = 0  # Extra burst allowance


class RateLimitExceeded(HTTPException):
    """Rate limit exceeded exception."""
    def __init__(self, retry_after: int):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )


class RateLimiter:
    """Token bucket rate limiter with Redis backend."""
    
    # Default rate limits by endpoint type
    DEFAULT_LIMITS = {
        "default": RateLimitConfig(requests=100, period=60),
        "auth": RateLimitConfig(requests=10, period=60),
        "upload": RateLimitConfig(requests=10, period=3600),
        "analysis": RateLimitConfig(requests=20, period=60),
        "api": RateLimitConfig(requests=1000, period=60),
    }
    
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._local_cache: Dict[str, List[float]] = {}
    
    async def check_rate_limit(
        self,
        key: str,
        limit_type: str = "default",
        config: Optional[RateLimitConfig] = None,
    ) -> bool:
        """Check if request is within rate limit."""
        config = config or self.DEFAULT_LIMITS.get(limit_type, self.DEFAULT_LIMITS["default"])
        
        if self.redis:
            return await self._check_redis(key, config)
        return self._check_local(key, config)
    
    async def _check_redis(self, key: str, config: RateLimitConfig) -> bool:
        """Check rate limit using Redis."""
        import time
        now = time.time()
        window_start = now - config.period
        
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcount(key, window_start, now)
        pipe.expire(key, config.period)
        
        results = await pipe.execute()
        request_count = results[2]
        
        max_requests = config.requests + config.burst
        return request_count <= max_requests
    
    def _check_local(self, key: str, config: RateLimitConfig) -> bool:
        """Check rate limit using local cache (for single instance)."""
        import time
        now = time.time()
        window_start = now - config.period
        
        if key not in self._local_cache:
            self._local_cache[key] = []
        
        # Remove old entries
        self._local_cache[key] = [
            t for t in self._local_cache[key] if t > window_start
        ]
        
        # Check limit
        max_requests = config.requests + config.burst
        if len(self._local_cache[key]) >= max_requests:
            return False
        
        self._local_cache[key].append(now)
        return True
    
    def get_remaining(self, key: str, limit_type: str = "default") -> int:
        """Get remaining requests in current window."""
        config = self.DEFAULT_LIMITS.get(limit_type, self.DEFAULT_LIMITS["default"])
        max_requests = config.requests + config.burst
        
        if key in self._local_cache:
            return max_requests - len(self._local_cache[key])
        return max_requests


def rate_limit(
    limit_type: str = "default",
    key_func: Optional[Callable[[Request], str]] = None,
):
    """Rate limiting decorator for FastAPI routes."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Get rate limiter from app state
            limiter = getattr(request.app.state, "rate_limiter", None)
            if not limiter:
                limiter = RateLimiter()
            
            # Generate key
            if key_func:
                key = key_func(request)
            else:
                # Default: IP + endpoint
                client_ip = request.client.host if request.client else "unknown"
                key = f"rate:{client_ip}:{request.url.path}"
            
            # Check rate limit
            if not await limiter.check_rate_limit(key, limit_type):
                config = limiter.DEFAULT_LIMITS.get(limit_type, limiter.DEFAULT_LIMITS["default"])
                raise RateLimitExceeded(retry_after=config.period)
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# =============================================================================
# Input Sanitization
# =============================================================================

class InputSanitizer:
    """Input sanitization utilities."""
    
    # Patterns for dangerous content
    SCRIPT_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL)
    SQL_INJECTION_PATTERN = re.compile(
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE|TRUNCATE)\b)",
        re.IGNORECASE
    )
    PATH_TRAVERSAL_PATTERN = re.compile(r'\.\./|\.\.\\')
    NULL_BYTE_PATTERN = re.compile(r'\x00')
    
    # Allowed filename characters
    SAFE_FILENAME_PATTERN = re.compile(r'^[\w\-. ]+$')
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 10000) -> str:
        """Sanitize a string input."""
        if not value:
            return value
        
        # Truncate
        value = value[:max_length]
        
        # Remove null bytes
        value = cls.NULL_BYTE_PATTERN.sub('', value)
        
        # Remove script tags
        value = cls.SCRIPT_PATTERN.sub('', value)
        
        # Escape HTML entities
        value = value.replace('&', '&amp;')
        value = value.replace('<', '&lt;')
        value = value.replace('>', '&gt;')
        value = value.replace('"', '&quot;')
        value = value.replace("'", '&#x27;')
        
        return value
    
    @classmethod
    def sanitize_filename(cls, filename: str) -> str:
        """Sanitize a filename."""
        if not filename:
            return "unnamed"
        
        # Remove path components
        filename = filename.replace('/', '_').replace('\\', '_')
        
        # Remove null bytes
        filename = cls.NULL_BYTE_PATTERN.sub('', filename)
        
        # Remove path traversal
        filename = cls.PATH_TRAVERSAL_PATTERN.sub('', filename)
        
        # Keep only safe characters
        safe_chars = []
        for char in filename:
            if char.isalnum() or char in '.-_ ':
                safe_chars.append(char)
        filename = ''.join(safe_chars)
        
        # Ensure not empty
        if not filename or filename in ['.', '..']:
            filename = "unnamed"
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')
        
        return filename
    
    @classmethod
    def check_sql_injection(cls, value: str) -> bool:
        """Check for potential SQL injection."""
        return bool(cls.SQL_INJECTION_PATTERN.search(value))
    
    @classmethod
    def sanitize_path(cls, path: str, allowed_base: str) -> str:
        """Sanitize a file path, ensuring it stays within allowed base."""
        import os
        
        # Remove null bytes
        path = cls.NULL_BYTE_PATTERN.sub('', path)
        
        # Normalize path
        path = os.path.normpath(path)
        
        # Remove leading slashes
        path = path.lstrip('/\\')
        
        # Join with base and normalize
        full_path = os.path.normpath(os.path.join(allowed_base, path))
        
        # Verify it's still under base
        if not full_path.startswith(os.path.normpath(allowed_base)):
            raise ValueError("Path traversal detected")
        
        return full_path


class SanitizedInput(BaseModel):
    """Base model with input sanitization."""
    
    class Config:
        # Strip whitespace from strings
        anystr_strip_whitespace = True
    
    @validator('*', pre=True)
    def sanitize_strings(cls, v):
        if isinstance(v, str):
            return InputSanitizer.sanitize_string(v)
        return v


# =============================================================================
# Secrets Management
# =============================================================================

class SecretsManager:
    """Secrets management with support for various backends."""
    
    def __init__(self, backend: str = "env"):
        self.backend = backend
        self._cache: Dict[str, str] = {}
    
    def get_secret(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a secret value."""
        # Check cache first
        if key in self._cache:
            return self._cache[key]
        
        value = None
        
        if self.backend == "env":
            value = self._get_from_env(key)
        elif self.backend == "vault":
            value = self._get_from_vault(key)
        elif self.backend == "aws":
            value = self._get_from_aws_secrets(key)
        
        if value:
            self._cache[key] = value
            return value
        
        return default
    
    def _get_from_env(self, key: str) -> Optional[str]:
        """Get secret from environment variable."""
        import os
        return os.environ.get(key)
    
    def _get_from_vault(self, key: str) -> Optional[str]:
        """Read a secret from HashiCorp Vault KV v2 when ``VAULT_ADDR`` and ``VAULT_TOKEN`` are set."""
        import os

        url = os.environ.get("VAULT_ADDR")
        token = os.environ.get("VAULT_TOKEN")
        mount = os.environ.get("VAULT_KV_MOUNT", "secret")
        if not url or not token:
            return None
        try:
            import hvac

            client = hvac.Client(url=url, token=token)
            if not client.is_authenticated():
                return None
            path = key.lstrip("/")
            resp = client.secrets.kv.v2.read_secret_version(path=path, mount_point=mount)
            data = resp.get("data", {}).get("data", {})
            if not isinstance(data, dict):
                return None
            if "value" in data:
                return str(data["value"])
            if len(data) == 1:
                return str(next(iter(data.values())))
        except ImportError:
            logger.debug("hvac not installed; Vault backend unavailable")
        except Exception:
            logger.debug("Vault read failed for %s", key, exc_info=True)
        return None
    
    def _get_from_aws_secrets(self, key: str) -> Optional[str]:
        """Get secret from AWS Secrets Manager."""
        try:
            import boto3
            client = boto3.client('secretsmanager')
            response = client.get_secret_value(SecretId=key)
            return response.get('SecretString')
        except ImportError:
            pass
        except Exception:
            pass
        return None
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_secret(secret: str, salt: Optional[str] = None) -> str:
        """Hash a secret value."""
        if salt is None:
            salt = secrets.token_hex(16)
        
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            secret.encode(),
            salt.encode(),
            100000
        )
        return f"{salt}${hashed.hex()}"
    
    @staticmethod
    def verify_secret(secret: str, hashed: str) -> bool:
        """Verify a secret against its hash."""
        try:
            salt, hash_value = hashed.split('$')
            new_hash = hashlib.pbkdf2_hmac(
                'sha256',
                secret.encode(),
                salt.encode(),
                100000
            )
            return hmac.compare_digest(new_hash.hex(), hash_value)
        except Exception:
            return False


# =============================================================================
# Audit Logging
# =============================================================================

class AuditAction(str, Enum):
    """Audit action types."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    EXPORT = "export"
    IMPORT = "import"
    EXECUTE = "execute"
    ADMIN = "admin"


@dataclass
class AuditLogEntry:
    """Audit log entry."""
    timestamp: datetime
    user_id: Optional[str]
    action: AuditAction
    resource_type: str
    resource_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "action": self.action.value,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "details": self.details,
            "success": self.success,
            "error_message": self.error_message,
        }


class AuditLogger:
    """Audit logging for compliance and security monitoring."""

    def __init__(self, log_file: Optional[str] = None, db_session=None, max_memory_entries: int = 5000):
        self.log_file = log_file
        self.db_session = db_session
        self._max_memory = max(100, int(max_memory_entries))
        self._memory_entries: List[AuditLogEntry] = []
        self._logger = logging.getLogger("audit")
        
        # Configure file logging if specified
        if log_file:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)
    
    async def log(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Log an audit event."""
        entry = AuditLogEntry(
            timestamp=datetime.utcnow(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            details=details or {},
            success=success,
            error_message=error_message,
        )
        
        # Log to file
        self._logger.info(json.dumps(entry.to_dict()))

        self._memory_entries.append(entry)
        if len(self._memory_entries) > self._max_memory:
            self._memory_entries = self._memory_entries[-self._max_memory :]

        if self.db_session:
            await self._log_to_db(entry)

    async def _log_to_db(self, entry: AuditLogEntry) -> None:
        """Persist to SQL when an ``audit_logs``-compatible table exists (optional migration)."""
        try:
            from sqlalchemy import text

            if hasattr(self.db_session, "execute"):
                await self.db_session.execute(
                    text(
                        "INSERT INTO audit_logs (timestamp, user_id, action, resource_type, "
                        "resource_id, ip_address, user_agent, details, success, error_message) "
                        "VALUES (:ts, :uid, :act, :rtype, :rid, :ip, :ua, CAST(:details AS JSONB), :ok, :err)"
                    ),
                    {
                        "ts": entry.timestamp,
                        "uid": entry.user_id,
                        "act": entry.action.value,
                        "rtype": entry.resource_type,
                        "rid": entry.resource_id,
                        "ip": entry.ip_address,
                        "ua": entry.user_agent,
                        "details": json.dumps(entry.details),
                        "ok": entry.success,
                        "err": entry.error_message,
                    },
                )
                if hasattr(self.db_session, "commit"):
                    await self.db_session.commit()
        except Exception:
            if hasattr(self.db_session, "rollback"):
                try:
                    await self.db_session.rollback()
                except Exception:
                    pass
            logger.debug("Database audit logging unavailable; entry kept in memory only", exc_info=True)

    async def query_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditLogEntry]:
        """Filter the in-process audit ring (newest first)."""
        rows = list(reversed(self._memory_entries))
        out: List[AuditLogEntry] = []
        for e in rows:
            if user_id and e.user_id != user_id:
                continue
            if action and e.action != action:
                continue
            if resource_type and e.resource_type != resource_type:
                continue
            if start_time and e.timestamp < start_time:
                continue
            if end_time and e.timestamp > end_time:
                continue
            out.append(e)
            if len(out) >= limit:
                break
        return out


def audit(
    action: AuditAction,
    resource_type: str,
    resource_id_param: Optional[str] = None,
):
    """Decorator for auditing route handlers."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            audit_logger = getattr(request.app.state, "audit_logger", None)
            if not audit_logger:
                audit_logger = AuditLogger()
            
            # Get user ID from request state
            user_id = getattr(request.state, "user_id", None)
            
            # Get resource ID from kwargs if specified
            resource_id = None
            if resource_id_param and resource_id_param in kwargs:
                resource_id = str(kwargs[resource_id_param])
            
            try:
                result = await func(request, *args, **kwargs)
                
                await audit_logger.log(
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    request=request,
                    success=True,
                )
                
                return result
                
            except Exception as e:
                await audit_logger.log(
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    request=request,
                    success=False,
                    error_message=str(e),
                )
                raise
        
        return wrapper
    return decorator

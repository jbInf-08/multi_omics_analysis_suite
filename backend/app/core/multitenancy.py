"""Multi-tenancy Support Module.
============================

Tenant isolation and management for multi-tenant deployments.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


logger = logging.getLogger(__name__)


class TenantStatus(str, Enum):
    """Tenant status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DELETED = "deleted"


class TenantTier(str, Enum):
    """Tenant subscription tiers."""

    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass
class TenantQuotas:
    """Resource quotas for a tenant."""

    max_users: int = 5
    max_projects: int = 10
    max_datasets: int = 50
    max_storage_gb: int = 10
    max_analyses_per_day: int = 100
    max_concurrent_jobs: int = 2
    api_rate_limit: int = 1000  # requests per hour


@dataclass
class TenantSettings:
    """Tenant-specific settings."""

    default_genome: str = "GRCh38"
    default_organism: str = "human"
    enable_notifications: bool = True
    enable_ai_features: bool = False
    custom_branding: dict[str, str] = field(default_factory=dict)
    allowed_features: list[str] = field(default_factory=list)


@dataclass
class Tenant:
    """Represents a tenant."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    slug: str = ""
    status: TenantStatus = TenantStatus.PENDING
    tier: TenantTier = TenantTier.FREE
    owner_id: str | None = None
    quotas: TenantQuotas = field(default_factory=TenantQuotas)
    settings: TenantSettings = field(default_factory=TenantSettings)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


class TenantManager:
    """Manage tenants and tenant isolation.

    Provides:
    - Tenant CRUD operations
    - Quota management
    - Feature access control
    - Resource isolation
    """

    # Tier configurations
    TIER_QUOTAS = {
        TenantTier.FREE: TenantQuotas(
            max_users=3,
            max_projects=5,
            max_datasets=20,
            max_storage_gb=5,
            max_analyses_per_day=50,
            max_concurrent_jobs=1,
            api_rate_limit=500,
        ),
        TenantTier.BASIC: TenantQuotas(
            max_users=10,
            max_projects=25,
            max_datasets=100,
            max_storage_gb=50,
            max_analyses_per_day=200,
            max_concurrent_jobs=3,
            api_rate_limit=2000,
        ),
        TenantTier.PROFESSIONAL: TenantQuotas(
            max_users=50,
            max_projects=100,
            max_datasets=500,
            max_storage_gb=500,
            max_analyses_per_day=1000,
            max_concurrent_jobs=10,
            api_rate_limit=10000,
        ),
        TenantTier.ENTERPRISE: TenantQuotas(
            max_users=999999,
            max_projects=999999,
            max_datasets=999999,
            max_storage_gb=10000,
            max_analyses_per_day=999999,
            max_concurrent_jobs=100,
            api_rate_limit=999999,
        ),
    }

    TIER_FEATURES = {
        TenantTier.FREE: ["basic_analysis", "data_upload", "visualization"],
        TenantTier.BASIC: [
            "basic_analysis",
            "data_upload",
            "visualization",
            "pathway_analysis",
            "export",
            "api_access",
        ],
        TenantTier.PROFESSIONAL: [
            "basic_analysis",
            "data_upload",
            "visualization",
            "pathway_analysis",
            "export",
            "api_access",
            "ml_models",
            "survival_analysis",
            "biomarker_discovery",
            "custom_workflows",
            "collaboration",
        ],
        TenantTier.ENTERPRISE: [
            "basic_analysis",
            "data_upload",
            "visualization",
            "pathway_analysis",
            "export",
            "api_access",
            "ml_models",
            "survival_analysis",
            "biomarker_discovery",
            "custom_workflows",
            "collaboration",
            "ai_features",
            "custom_branding",
            "sso",
            "audit_logs",
            "dedicated_support",
            "on_premise",
        ],
    }

    def __init__(self):
        """Initialize tenant manager."""
        self._tenants: dict[str, Tenant] = {}
        self._tenant_context: dict[str, str] = {}  # user_id -> tenant_id

    def create_tenant(
        self,
        name: str,
        owner_id: str,
        tier: TenantTier = TenantTier.FREE,
        slug: str | None = None,
    ) -> Tenant:
        """Create a new tenant.

        Args:
            name: Tenant name
            owner_id: Owner user ID
            tier: Subscription tier
            slug: URL slug (generated from name if not provided)

        Returns:
            Created Tenant

        """
        slug = slug or self._generate_slug(name)

        # Check slug uniqueness
        if any(t.slug == slug for t in self._tenants.values()):
            raise ValueError(f"Tenant slug '{slug}' already exists")

        # Get tier-based quotas and features
        quotas = self.TIER_QUOTAS.get(tier, TenantQuotas())
        features = self.TIER_FEATURES.get(tier, [])

        tenant = Tenant(
            name=name,
            slug=slug,
            status=TenantStatus.ACTIVE,
            tier=tier,
            owner_id=owner_id,
            quotas=quotas,
            settings=TenantSettings(allowed_features=features),
        )

        self._tenants[tenant.id] = tenant
        self._tenant_context[owner_id] = tenant.id

        logger.info(f"Created tenant: {tenant.id} ({tenant.name})")
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID."""
        return self._tenants.get(tenant_id)

    def get_tenant_by_slug(self, slug: str) -> Tenant | None:
        """Get a tenant by slug."""
        for tenant in self._tenants.values():
            if tenant.slug == slug:
                return tenant
        return None

    def update_tenant(self, tenant_id: str, **updates) -> Tenant | None:
        """Update tenant properties."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return None

        for key, value in updates.items():
            if hasattr(tenant, key):
                setattr(tenant, key, value)

        tenant.updated_at = datetime.now(timezone.utc)
        return tenant

    def upgrade_tier(self, tenant_id: str, new_tier: TenantTier) -> Tenant | None:
        """Upgrade tenant tier."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return None

        tenant.tier = new_tier
        tenant.quotas = self.TIER_QUOTAS.get(new_tier, TenantQuotas())
        tenant.settings.allowed_features = self.TIER_FEATURES.get(new_tier, [])
        tenant.updated_at = datetime.now(timezone.utc)

        logger.info(f"Upgraded tenant {tenant_id} to tier {new_tier}")
        return tenant

    def suspend_tenant(self, tenant_id: str, reason: str = "") -> bool:
        """Suspend a tenant."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False

        tenant.status = TenantStatus.SUSPENDED
        tenant.metadata["suspension_reason"] = reason
        tenant.metadata["suspended_at"] = datetime.now(timezone.utc).isoformat()
        tenant.updated_at = datetime.now(timezone.utc)

        logger.warning(f"Suspended tenant {tenant_id}: {reason}")
        return True

    def reactivate_tenant(self, tenant_id: str) -> bool:
        """Reactivate a suspended tenant."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False

        tenant.status = TenantStatus.ACTIVE
        tenant.metadata.pop("suspension_reason", None)
        tenant.metadata.pop("suspended_at", None)
        tenant.updated_at = datetime.now(timezone.utc)

        logger.info(f"Reactivated tenant {tenant_id}")
        return True

    def delete_tenant(self, tenant_id: str) -> bool:
        """Mark tenant as deleted."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False

        tenant.status = TenantStatus.DELETED
        tenant.metadata["deleted_at"] = datetime.now(timezone.utc).isoformat()
        tenant.updated_at = datetime.now(timezone.utc)

        # Remove user associations
        self._tenant_context = {k: v for k, v in self._tenant_context.items() if v != tenant_id}

        logger.info(f"Deleted tenant {tenant_id}")
        return True

    def add_user_to_tenant(self, user_id: str, tenant_id: str) -> bool:
        """Associate a user with a tenant."""
        tenant = self.get_tenant(tenant_id)
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            return False

        self._tenant_context[user_id] = tenant_id
        return True

    def get_user_tenant(self, user_id: str) -> Tenant | None:
        """Get the tenant for a user."""
        tenant_id = self._tenant_context.get(user_id)
        if tenant_id:
            return self.get_tenant(tenant_id)
        return None

    def check_quota(
        self,
        tenant_id: str,
        resource: str,
        current_usage: int,
    ) -> bool:
        """Check if tenant is within quota limits.

        Args:
            tenant_id: Tenant ID
            resource: Resource type (users, projects, etc.)
            current_usage: Current usage count

        Returns:
            True if within limits

        """
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False

        quota_map = {
            "users": tenant.quotas.max_users,
            "projects": tenant.quotas.max_projects,
            "datasets": tenant.quotas.max_datasets,
            "storage_gb": tenant.quotas.max_storage_gb,
            "analyses_per_day": tenant.quotas.max_analyses_per_day,
            "concurrent_jobs": tenant.quotas.max_concurrent_jobs,
        }

        limit = quota_map.get(resource)
        if limit is None:
            return True

        return current_usage < limit

    def check_feature_access(self, tenant_id: str, feature: str) -> bool:
        """Check if tenant has access to a feature."""
        tenant = self.get_tenant(tenant_id)
        if not tenant:
            return False

        return feature in tenant.settings.allowed_features

    def list_tenants(
        self,
        status: TenantStatus | None = None,
        tier: TenantTier | None = None,
    ) -> list[Tenant]:
        """List tenants with optional filtering."""
        tenants = list(self._tenants.values())

        if status:
            tenants = [t for t in tenants if t.status == status]
        if tier:
            tenants = [t for t in tenants if t.tier == tier]

        return tenants

    def _generate_slug(self, name: str) -> str:
        """Generate URL-safe slug from name."""
        import re

        slug = name.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug)
        slug = slug.strip("-")
        return slug


# Global tenant manager instance
tenant_manager = TenantManager()


class TenantMiddleware:
    """FastAPI middleware for tenant context."""

    def __init__(self, app, tenant_manager: TenantManager):
        """Initialize middleware."""
        self.app = app
        self.tenant_manager = tenant_manager

    async def __call__(self, scope, receive, send):
        """Process request with tenant context."""
        if scope["type"] == "http":
            # Extract tenant from header or subdomain
            headers = dict(scope.get("headers", []))
            tenant_id = headers.get(b"x-tenant-id", b"").decode()

            if tenant_id:
                tenant = self.tenant_manager.get_tenant(tenant_id)
                if tenant and tenant.status == TenantStatus.ACTIVE:
                    scope["tenant"] = tenant
                else:
                    scope["tenant"] = None
            else:
                scope["tenant"] = None

        await self.app(scope, receive, send)

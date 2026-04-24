"""OAuth2 Enhancement Module.
=========================

Integration with OAuth2 providers: Auth0, Keycloak.
"""

import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class OAuth2Provider(str, Enum):
    """Supported OAuth2 providers."""

    AUTH0 = "auth0"
    KEYCLOAK = "keycloak"
    GOOGLE = "google"
    GITHUB = "github"
    MICROSOFT = "microsoft"


@dataclass
class OAuth2Config:
    """OAuth2 provider configuration."""

    provider: OAuth2Provider
    client_id: str
    client_secret: str
    domain: str  # Auth0 domain or Keycloak realm URL
    redirect_uri: str
    scopes: list[str] = field(default_factory=lambda: ["openid", "profile", "email"])
    audience: str | None = None  # Auth0 API audience


@dataclass
class OAuth2Token:
    """OAuth2 token response."""

    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str | None = None


@dataclass
class OAuth2User:
    """OAuth2 user information."""

    sub: str  # Subject identifier
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    picture: str | None = None
    locale: str | None = None
    provider: OAuth2Provider | None = None
    raw_info: dict[str, Any] = field(default_factory=dict)


class OAuth2Client:
    """OAuth2 client for authentication flows.

    Supports:
    - Authorization Code flow
    - Token refresh
    - User info retrieval
    - Token validation
    """

    def __init__(self, config: OAuth2Config):
        """Initialize OAuth2 client.

        Args:
            config: OAuth2 configuration

        """
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._state_store: dict[str, datetime] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @property
    def authorization_endpoint(self) -> str:
        """Get authorization endpoint URL."""
        if self.config.provider == OAuth2Provider.AUTH0:
            return f"https://{self.config.domain}/authorize"
        elif self.config.provider == OAuth2Provider.KEYCLOAK:
            return f"{self.config.domain}/protocol/openid-connect/auth"
        elif self.config.provider == OAuth2Provider.GOOGLE:
            return "https://accounts.google.com/o/oauth2/v2/auth"
        elif self.config.provider == OAuth2Provider.GITHUB:
            return "https://github.com/login/oauth/authorize"
        elif self.config.provider == OAuth2Provider.MICROSOFT:
            return f"https://login.microsoftonline.com/{self.config.domain}/oauth2/v2.0/authorize"
        else:
            raise ValueError(f"Unknown provider: {self.config.provider}")

    @property
    def token_endpoint(self) -> str:
        """Get token endpoint URL."""
        if self.config.provider == OAuth2Provider.AUTH0:
            return f"https://{self.config.domain}/oauth/token"
        elif self.config.provider == OAuth2Provider.KEYCLOAK:
            return f"{self.config.domain}/protocol/openid-connect/token"
        elif self.config.provider == OAuth2Provider.GOOGLE:
            return "https://oauth2.googleapis.com/token"
        elif self.config.provider == OAuth2Provider.GITHUB:
            return "https://github.com/login/oauth/access_token"
        elif self.config.provider == OAuth2Provider.MICROSOFT:
            return f"https://login.microsoftonline.com/{self.config.domain}/oauth2/v2.0/token"
        else:
            raise ValueError(f"Unknown provider: {self.config.provider}")

    @property
    def userinfo_endpoint(self) -> str:
        """Get userinfo endpoint URL."""
        if self.config.provider == OAuth2Provider.AUTH0:
            return f"https://{self.config.domain}/userinfo"
        elif self.config.provider == OAuth2Provider.KEYCLOAK:
            return f"{self.config.domain}/protocol/openid-connect/userinfo"
        elif self.config.provider == OAuth2Provider.GOOGLE:
            return "https://openidconnect.googleapis.com/v1/userinfo"
        elif self.config.provider == OAuth2Provider.GITHUB:
            return "https://api.github.com/user"
        elif self.config.provider == OAuth2Provider.MICROSOFT:
            return "https://graph.microsoft.com/oidc/userinfo"
        else:
            raise ValueError(f"Unknown provider: {self.config.provider}")

    def get_authorization_url(self, state: str | None = None) -> tuple[str, str]:
        """Generate authorization URL.

        Args:
            state: Optional state parameter (generated if not provided)

        Returns:
            Tuple of (authorization_url, state)

        """
        state = state or secrets.token_urlsafe(32)

        # Store state with expiration
        self._state_store[state] = datetime.now(timezone.utc) + timedelta(minutes=10)

        params = {
            "response_type": "code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "scope": " ".join(self.config.scopes),
            "state": state,
        }

        if self.config.audience:
            params["audience"] = self.config.audience

        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.authorization_endpoint}?{query}"

        return url, state

    def validate_state(self, state: str) -> bool:
        """Validate state parameter."""
        expiry = self._state_store.get(state)
        if expiry is None:
            return False

        if datetime.now(timezone.utc) > expiry:
            del self._state_store[state]
            return False

        del self._state_store[state]
        return True

    async def exchange_code(self, code: str) -> OAuth2Token:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code

        Returns:
            OAuth2Token

        """
        session = await self._get_session()

        data = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "code": code,
            "redirect_uri": self.config.redirect_uri,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.config.provider == OAuth2Provider.GITHUB:
            headers["Accept"] = "application/json"

        async with session.post(
            self.token_endpoint,
            data=data,
            headers=headers,
        ) as response:
            response.raise_for_status()
            token_data = await response.json()

        return OAuth2Token(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token"),
            id_token=token_data.get("id_token"),
            scope=token_data.get("scope"),
        )

    async def refresh_token(self, refresh_token: str) -> OAuth2Token:
        """Refresh access token.

        Args:
            refresh_token: Refresh token

        Returns:
            New OAuth2Token

        """
        session = await self._get_session()

        data = {
            "grant_type": "refresh_token",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "refresh_token": refresh_token,
        }

        async with session.post(
            self.token_endpoint,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as response:
            response.raise_for_status()
            token_data = await response.json()

        return OAuth2Token(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token", refresh_token),
            id_token=token_data.get("id_token"),
            scope=token_data.get("scope"),
        )

    async def get_user_info(self, access_token: str) -> OAuth2User:
        """Get user information from provider.

        Args:
            access_token: Access token

        Returns:
            OAuth2User

        """
        session = await self._get_session()

        headers = {"Authorization": f"Bearer {access_token}"}

        async with session.get(
            self.userinfo_endpoint,
            headers=headers,
        ) as response:
            response.raise_for_status()
            user_data = await response.json()

        return OAuth2User(
            sub=user_data.get("sub") or user_data.get("id", ""),
            email=user_data.get("email"),
            email_verified=user_data.get("email_verified", False),
            name=user_data.get("name"),
            given_name=user_data.get("given_name"),
            family_name=user_data.get("family_name"),
            picture=user_data.get("picture"),
            locale=user_data.get("locale"),
            provider=self.config.provider,
            raw_info=user_data,
        )

    async def logout_url(self, return_to: str | None = None) -> str | None:
        """Get logout URL (if supported by provider).

        Args:
            return_to: URL to redirect after logout

        Returns:
            Logout URL or None

        """
        if self.config.provider == OAuth2Provider.AUTH0:
            url = f"https://{self.config.domain}/v2/logout"
            url += f"?client_id={self.config.client_id}"
            if return_to:
                url += f"&returnTo={return_to}"
            return url

        elif self.config.provider == OAuth2Provider.KEYCLOAK:
            url = f"{self.config.domain}/protocol/openid-connect/logout"
            if return_to:
                url += f"?redirect_uri={return_to}"
            return url

        return None

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


class Auth0Client(OAuth2Client):
    """Auth0-specific OAuth2 client.

    Includes Auth0 Management API integration.
    """

    def __init__(self, config: OAuth2Config, management_token: str | None = None):
        """Initialize Auth0 client.

        Args:
            config: OAuth2 configuration
            management_token: Auth0 Management API token

        """
        super().__init__(config)
        self.management_token = management_token

    async def get_management_token(self) -> str:
        """Get Auth0 Management API token."""
        session = await self._get_session()

        async with session.post(
            f"https://{self.config.domain}/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "audience": f"https://{self.config.domain}/api/v2/",
            },
        ) as response:
            response.raise_for_status()
            data = await response.json()
            self.management_token = data["access_token"]
            return self.management_token

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Get user from Auth0 Management API."""
        if not self.management_token:
            await self.get_management_token()

        session = await self._get_session()

        async with session.get(
            f"https://{self.config.domain}/api/v2/users/{user_id}",
            headers={"Authorization": f"Bearer {self.management_token}"},
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def update_user(
        self,
        user_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update user in Auth0."""
        if not self.management_token:
            await self.get_management_token()

        session = await self._get_session()

        async with session.patch(
            f"https://{self.config.domain}/api/v2/users/{user_id}",
            headers={"Authorization": f"Bearer {self.management_token}"},
            json=updates,
        ) as response:
            response.raise_for_status()
            return await response.json()


class KeycloakClient(OAuth2Client):
    """Keycloak-specific OAuth2 client.

    Includes Keycloak Admin API integration.
    """

    def __init__(
        self,
        config: OAuth2Config,
        admin_username: str | None = None,
        admin_password: str | None = None,
    ):
        """Initialize Keycloak client.

        Args:
            config: OAuth2 configuration
            admin_username: Keycloak admin username
            admin_password: Keycloak admin password

        """
        super().__init__(config)
        self.admin_username = admin_username
        self.admin_password = admin_password
        self._admin_token: str | None = None

    async def get_admin_token(self) -> str:
        """Get Keycloak admin token."""
        if not self.admin_username or not self.admin_password:
            raise ValueError("Admin credentials required")

        session = await self._get_session()

        # Extract realm base URL
        realm_base = self.config.domain.rsplit("/realms/", 1)[0]

        async with session.post(
            f"{realm_base}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.admin_username,
                "password": self.admin_password,
            },
        ) as response:
            response.raise_for_status()
            data = await response.json()
            self._admin_token = data["access_token"]
            return self._admin_token

    async def get_users(self) -> list[dict[str, Any]]:
        """Get users from Keycloak."""
        if not self._admin_token:
            await self.get_admin_token()

        session = await self._get_session()
        realm_base = self.config.domain.rsplit("/realms/", 1)[0]
        realm_name = self.config.domain.rsplit("/realms/", 1)[1].split("/")[0]

        async with session.get(
            f"{realm_base}/admin/realms/{realm_name}/users",
            headers={"Authorization": f"Bearer {self._admin_token}"},
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def create_user(self, user_data: dict[str, Any]) -> bool:
        """Create a user in Keycloak."""
        if not self._admin_token:
            await self.get_admin_token()

        session = await self._get_session()
        realm_base = self.config.domain.rsplit("/realms/", 1)[0]
        realm_name = self.config.domain.rsplit("/realms/", 1)[1].split("/")[0]

        async with session.post(
            f"{realm_base}/admin/realms/{realm_name}/users",
            headers={"Authorization": f"Bearer {self._admin_token}"},
            json=user_data,
        ) as response:
            return response.status == 201

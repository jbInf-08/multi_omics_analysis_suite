"""GraphQL context, WebSocket connection capture, and JWT helpers."""

from __future__ import annotations

import weakref
from typing import Any, cast

from jose import JWTError, jwt
from starlette.requests import HTTPConnection, Request
from starlette.websockets import WebSocket
from strawberry.exceptions import ConnectionRejectionError
from strawberry.fastapi import GraphQLRouter
from strawberry.types import Info

from backend.app.core.config import settings

_ws_connection_params: weakref.WeakKeyDictionary[Any, dict] = weakref.WeakKeyDictionary()


def try_decode_bearer_sub(raw_token: str) -> str | None:
    """Return JWT ``sub`` for a valid access token, else ``None``."""
    if not raw_token:
        return None
    try:
        payload = jwt.decode(
            raw_token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        if payload.get("type") != "access":
            return None
        return str(payload.get("sub"))
    except JWTError:
        return None


def _bearer_sub_from_authorization_header(value: str | None) -> str | None:
    if not value or not value.startswith("Bearer "):
        return None
    return try_decode_bearer_sub(value[7:].strip())


def _bearer_sub_from_connection_params(params: Any) -> str | None:
    if not isinstance(params, dict):
        return None
    auth = params.get("Authorization") or params.get("authorization")
    if not isinstance(auth, str):
        return None
    if auth.lower().startswith("bearer "):
        return try_decode_bearer_sub(auth[7:].strip())
    return try_decode_bearer_sub(auth.strip())


async def get_graphql_context(connection: HTTPConnection) -> dict[str, Any]:
    """HTTP Bearer and/or WebSocket ``connection_params`` (after :meth:`AppGraphQLRouter.on_ws_connect`).

    Uses a single :class:`HTTPConnection` parameter so FastAPI can inject the active
    request or WebSocket (Strawberry merges this into its internal dependency).
    """
    request: Request | None = None
    ws: WebSocket | None = None
    token_sub: str | None = None

    if isinstance(connection, WebSocket):
        ws = connection
        params = _ws_connection_params.get(ws)
        token_sub = _bearer_sub_from_connection_params(params)
    else:
        request = cast(Request, connection)
        token_sub = _bearer_sub_from_authorization_header(request.headers.get("Authorization"))

    return {"token_sub": token_sub, "request": request, "websocket": ws}


def token_sub_from_graphql_info(info: Info) -> str | None:
    """Resolve authenticated ``sub`` from GraphQL ``info.context`` (HTTP or WebSocket)."""
    ctx = info.context
    if not isinstance(ctx, dict):
        return None
    sub = ctx.get("token_sub")
    if sub:
        return str(sub)
    ws = ctx.get("websocket")
    if ws is not None:
        return _bearer_sub_from_connection_params(_ws_connection_params.get(ws))
    return None


class AppGraphQLRouter(GraphQLRouter):
    """Captures graphql-transport-ws ``connection_init`` payload for :func:`get_graphql_context`."""

    async def on_ws_connect(self, context: dict[str, object]) -> Any:
        websocket = context.get("websocket")
        params = context.get("connection_params")
        if websocket is not None and isinstance(params, dict):
            _ws_connection_params[websocket] = params

        if not settings.DEBUG:
            if not isinstance(params, dict):
                raise ConnectionRejectionError(
                    {"reason": "connection_params must be a JSON object"},
                )
            auth = params.get("Authorization") or params.get("authorization")
            if not isinstance(auth, str) or not auth.strip():
                raise ConnectionRejectionError(
                    {"reason": "Missing Authorization bearer in connection_params"},
                )
            token = auth[7:].strip() if auth.lower().startswith("bearer ") else auth.strip()
            if try_decode_bearer_sub(token) is None:
                raise ConnectionRejectionError({"reason": "Invalid bearer token"})

        return await super().on_ws_connect(context)

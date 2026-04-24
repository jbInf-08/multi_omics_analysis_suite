"""GraphQL Schema.
==============

Strawberry GraphQL schema for the Multi-Omics Analysis Suite.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator
from uuid import UUID

import strawberry
from celery.result import AsyncResult
from sqlalchemy import select
from strawberry.types import Info

from backend.app.api.graphql.context import token_sub_from_graphql_info
from backend.app.api.graphql.mutations import Mutation
from backend.app.api.graphql.resolvers import (
    get_analyses,
    get_analysis,
    get_dataset,
    get_datasets,
    get_omics_modules,
    get_pipelines,
    get_project,
    get_projects,
    get_user,
    get_users,
)
from backend.app.api.graphql.types import (
    AnalysisType,
    DatasetType,
    OmicsModuleType,
    PipelineType,
    ProjectType,
    UserType,
)
from backend.app.core.analysis_progress_bus import progress_channel
from backend.app.core.celery_app import celery_app
from backend.app.core.config import settings
from backend.app.core.database import get_async_session


@strawberry.type
class AnalysisProgressType:
    """Analysis progress update (polls Celery result backend; falls back to DB status)."""

    analysis_id: strawberry.ID
    status: str
    progress: float
    current_step: str | None = None


@strawberry.type
class Query:
    """GraphQL Query root."""

    @strawberry.field
    async def user(self, id: strawberry.ID) -> UserType | None:
        """Get user by ID."""
        return await get_user(id)

    @strawberry.field
    async def users(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[UserType]:
        """Get list of users."""
        return await get_users(limit, offset)

    @strawberry.field
    async def project(self, id: strawberry.ID) -> ProjectType | None:
        """Get project by ID."""
        return await get_project(id)

    @strawberry.field
    async def projects(
        self,
        user_id: strawberry.ID | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ProjectType]:
        """Get list of projects."""
        return await get_projects(user_id, status, limit, offset)

    @strawberry.field
    async def dataset(self, id: strawberry.ID) -> DatasetType | None:
        """Get dataset by ID."""
        return await get_dataset(id)

    @strawberry.field
    async def datasets(
        self,
        project_id: strawberry.ID | None = None,
        omics_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[DatasetType]:
        """Get list of datasets."""
        return await get_datasets(project_id, omics_type, limit, offset)

    @strawberry.field
    async def analysis(self, id: strawberry.ID) -> AnalysisType | None:
        """Get analysis by ID."""
        return await get_analysis(id)

    @strawberry.field
    async def analyses(
        self,
        project_id: strawberry.ID | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[AnalysisType]:
        """Get list of analyses."""
        return await get_analyses(project_id, status, limit, offset)

    @strawberry.field
    async def omics_modules(
        self,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[OmicsModuleType]:
        """Get list of omics modules."""
        return await get_omics_modules(category, active_only)

    @strawberry.field
    async def pipelines(
        self,
        omics_type: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PipelineType]:
        """Get list of pipelines."""
        return await get_pipelines(omics_type, limit, offset)


def _celery_state_to_status(state: str) -> str:
    mapping = {
        "PENDING": "pending",
        "STARTED": "running",
        "RETRY": "running",
        "PROGRESS": "running",
        "SUCCESS": "completed",
        "FAILURE": "failed",
        "REVOKED": "cancelled",
    }
    return mapping.get(state, state.lower() if state else "pending")


@strawberry.type
class Subscription:
    """GraphQL Subscription root."""

    @strawberry.subscription
    async def analysis_progress(
        self,
        info: Info,
        analysis_id: strawberry.ID,
    ) -> AsyncGenerator[AnalysisProgressType, None]:
        """Subscribe to analysis progress.

        Requires a valid access JWT (HTTP ``Authorization`` or WebSocket ``connection_params``).
        Only the analysis owner receives updates. Merges Redis pub/sub (from Celery) with
        Celery result polling using exponential backoff up to 30s between polls.
        """
        from backend.app.models.analysis import Analysis as AnalysisModel

        token_sub = token_sub_from_graphql_info(info)
        if not token_sub:
            yield AnalysisProgressType(
                analysis_id=analysis_id,
                status="unauthenticated",
                progress=0.0,
                current_step=None,
            )
            return

        aid = UUID(str(analysis_id))
        celery_task_id: str | None = None
        db_status = "unknown"
        db_progress = 0.0
        owner_id: str | None = None

        async for session in get_async_session():
            try:
                result = await session.execute(select(AnalysisModel).where(AnalysisModel.id == aid))
                row = result.scalar_one_or_none()
                if row:
                    owner_id = str(row.user_id)
                    st = row.status
                    db_status = st.value if hasattr(st, "value") else str(st)
                    db_progress = float(row.progress or 0.0)
                    celery_task_id = row.celery_task_id
            finally:
                break

        if owner_id is None:
            yield AnalysisProgressType(
                analysis_id=analysis_id,
                status="not_found",
                progress=0.0,
                current_step=None,
            )
            return

        if owner_id != token_sub:
            yield AnalysisProgressType(
                analysis_id=analysis_id,
                status="forbidden",
                progress=0.0,
                current_step=None,
            )
            return

        if not celery_task_id:
            yield AnalysisProgressType(
                analysis_id=analysis_id,
                status=db_status,
                progress=db_progress,
                current_step=None,
            )
            return

        redis_pubsub = None
        redis_client = None
        url = (settings.REDIS_URL or "").strip()
        if url.startswith("redis"):
            try:
                import redis.asyncio as redis_async

                redis_client = redis_async.from_url(url, decode_responses=True)
                redis_pubsub = redis_client.pubsub()
                await redis_pubsub.subscribe(progress_channel(str(aid)))
            except Exception:
                redis_pubsub = None
                if redis_client is not None:
                    with contextlib.suppress(Exception):
                        await redis_client.close()
                redis_client = None

        max_iterations = 7200
        try:
            for i in range(max_iterations):
                if redis_pubsub is not None:
                    try:
                        msg = await redis_pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=0.05,
                        )
                        if msg and msg.get("type") == "message" and msg.get("data"):
                            payload = json.loads(msg["data"])
                            if isinstance(payload, dict):
                                prog = float(payload.get("progress", 0.0))
                                raw_step = payload.get("step")
                                pub_step = str(raw_step) if raw_step is not None else None
                                yield AnalysisProgressType(
                                    analysis_id=analysis_id,
                                    status="running",
                                    progress=prog,
                                    current_step=pub_step,
                                )
                                continue
                    except Exception:
                        pass

                ar = AsyncResult(celery_task_id, app=celery_app)
                state = ar.state or "PENDING"
                progress = 0.0
                poll_step: str | None = None
                if state == "PROGRESS" and ar.info:
                    cinfo = ar.info if isinstance(ar.info, dict) else {}
                    progress = float(cinfo.get("progress", 0.0))
                    raw_step = cinfo.get("step")
                    poll_step = str(raw_step) if raw_step is not None else None
                elif state == "SUCCESS":
                    progress = 1.0
                elif state == "FAILURE":
                    progress = db_progress

                yield AnalysisProgressType(
                    analysis_id=analysis_id,
                    status=_celery_state_to_status(state),
                    progress=progress,
                    current_step=poll_step,
                )

                if state in ("SUCCESS", "FAILURE", "REVOKED"):
                    return

                delay = min(30.0, 0.5 * (1.15 ** min(i, 45)))
                await asyncio.sleep(delay)

            yield AnalysisProgressType(
                analysis_id=analysis_id,
                status="failed",
                progress=db_progress,
                current_step="subscription_poll_limit_reached",
            )
        finally:
            if redis_pubsub is not None:
                try:
                    await redis_pubsub.unsubscribe(progress_channel(str(aid)))
                    await redis_pubsub.close()
                except Exception:
                    pass
            if redis_client is not None:
                with contextlib.suppress(Exception):
                    await redis_client.close()


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)

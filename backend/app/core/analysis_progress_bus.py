"""Redis pub/sub fan-out for analysis progress (Celery worker → API subscribers)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def progress_channel(analysis_id: str) -> str:
    return f"analysis_progress:{analysis_id}"


def publish_analysis_progress_sync(analysis_id: str, data: Dict[str, Any]) -> None:
    """Publish one progress payload (runs in Celery worker; best-effort)."""
    from backend.app.core.config import settings

    url = (settings.REDIS_URL or "").strip()
    if not url or not url.startswith("redis"):
        return
    try:
        import redis as redis_sync

        client = redis_sync.from_url(url, decode_responses=True)
        try:
            client.publish(progress_channel(analysis_id), json.dumps(data))
        finally:
            client.close()
    except Exception as exc:
        logger.debug("analysis_progress publish skipped: %s", exc)

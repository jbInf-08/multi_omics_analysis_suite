"""
Spill large Celery pipeline step payloads to disk; keep compact summaries for JSON columns.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.core.config import settings


def persist_pipeline_step_output(
    run_id: str,
    step_index: int,
    step_type: Optional[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    If ``payload`` serializes larger than ``PIPELINE_ARTIFACT_MAX_EMBED_BYTES``, write the full
    JSON under ``PIPELINE_ARTIFACTS_DIR/<run_id>/`` and return a stub with paths and counts.
    """
    max_bytes = int(settings.PIPELINE_ARTIFACT_MAX_EMBED_BYTES)
    safe_type = (step_type or "step").replace("/", "_").replace(" ", "_")[:80]
    raw = json.dumps(payload, default=str)
    encoded = raw.encode("utf-8")

    if len(encoded) <= max_bytes:
        return payload

    base = Path(settings.PIPELINE_ARTIFACTS_DIR) / str(run_id)
    base.mkdir(parents=True, exist_ok=True)
    stem = f"step_{step_index:03d}_{safe_type}"
    json_path = base / f"{stem}.json"
    json_path.write_text(raw, encoding="utf-8")

    summary: Dict[str, Any] = {
        "_artifact": True,
        "artifact_json": str(json_path.resolve()),
        "artifact_bytes": len(encoded),
        "step_index": step_index,
        "step_type": step_type,
    }

    if isinstance(payload.get("gff"), str) and len(payload["gff"]) > 4096:
        gff_path = base / f"{stem}.gff"
        gff_path.write_text(payload["gff"], encoding="utf-8")
        summary["gff_path"] = str(gff_path.resolve())
        summary["gff_line_count"] = len(payload["gff"].splitlines())

    genes = payload.get("genes")
    if isinstance(genes, list):
        summary["gene_count"] = len(genes)

    if "md" in payload:
        summary["has_md"] = True
    if "docking" in payload:
        summary["has_docking"] = True
    if "total_genes" in payload:
        summary["total_genes"] = payload["total_genes"]
    if "predictor" in payload:
        summary["predictor"] = payload["predictor"]

    return summary

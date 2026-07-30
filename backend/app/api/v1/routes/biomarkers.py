"""Multi-omics biomarker discovery.

The Integration page's Biomarker Discovery step had a button with no handler and
three selects with no state. This backs it.

The goal-posts here are taken from what the project already does rather than
invented: the outcome is resolved the way run_differential_expression resolves
its group column, significance uses the same Benjamini-Hochberg correction and
the same 0.05 / 1.0 default thresholds as that task, and feature selection and
cross-validation go through backend.ml's existing FeatureSelector and
ModelTrainer.

A feature is reported as a biomarker only when it is *both* statistically
associated with the outcome and retained by feature selection. Either signal
alone is weaker than it looks -- a p-value alone ignores multivariate
redundancy, and a selector's ranking alone carries no significance -- so the
intersection is what gets returned, with both pieces of evidence attached.
"""

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.v1.routes.omics import _for_log, _load_dataset_frame
from backend.app.core.database import get_db
from backend.app.core.security import TokenPayload, get_current_user
from backend.app.models.dataset import Dataset
from backend.app.models.project import Project

if TYPE_CHECKING:  # annotations only
    import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter()

#: Analysis types the UI offers.
_ANALYSIS_TYPES = {"differential", "survival", "classification"}

#: Feature selection methods, mapped onto backend.ml.FeatureSelector.
_SELECTION_METHODS = {"stability", "lasso", "random_forest"}

#: Cross-validation schemes. 0 means leave-one-out.
_CV_CHOICES = {0, 5, 10}

#: Leave-one-out refits once per sample, so it is capped rather than allowed to
#: run for minutes on a large cohort.
_LOO_MAX_SAMPLES = 200


class BiomarkerDiscoveryRequest(BaseModel):
    """Body for a biomarker discovery run over integrated datasets."""

    project_id: UUID
    dataset_ids: list[UUID] = Field(..., min_length=1)
    analysis_type: str = Field(
        "differential", description="differential | survival | classification"
    )
    outcome_column: str = Field(
        ...,
        min_length=1,
        description=(
            "Sample annotation holding the outcome. Resolved from the dataset's "
            "own columns first, then from sample_metadata, matching how "
            "run_differential_expression resolves its group column."
        ),
    )
    groups: list[str] | None = Field(
        None, description="The two outcome values to contrast. Differential analysis only."
    )
    event_column: str | None = Field(
        None, description="Event indicator (1 = event, 0 = censored). Survival analysis only."
    )
    feature_selection: str = Field("stability", description="stability | lasso | random_forest")
    cv_folds: int = Field(5, description="5, 10, or 0 for leave-one-out")
    fdr_threshold: float = Field(0.05, gt=0.0, le=1.0)
    log2fc_threshold: float = Field(1.0, ge=0.0, description="Differential analysis only")
    max_biomarkers: int = Field(100, ge=1, le=1000)


class Biomarker(BaseModel):
    """A feature that is both significantly associated and retained by selection."""

    feature: str
    dataset_id: UUID
    dataset_name: str
    omics_type: str
    effect: float = Field(
        ..., description="log2 fold change (differential) or log hazard ratio (survival)"
    )
    p_value: float
    q_value: float = Field(..., description="Benjamini-Hochberg adjusted p-value")
    selection_score: float = Field(..., description="Score from the feature selector, 0-1")


class ValidationSummary(BaseModel):
    """Cross-validated performance of a model built on the reported biomarkers."""

    scheme: str
    folds: int
    metric: str
    score: float
    std: float | None = None


class BiomarkerDiscoveryResponse(BaseModel):
    """Result of a biomarker discovery run."""

    analysis_type: str
    outcome_column: str
    outcome_groups: list[str] | None = None
    n_samples: int
    n_features_tested: int
    n_significant: int = Field(..., description="Features passing the FDR (and effect) thresholds")
    n_selected: int = Field(..., description="Features retained by the selector")
    biomarkers: list[Biomarker] = Field(
        ..., description="The intersection of significant and selected, best first"
    )
    selection_method: str
    fdr_threshold: float
    validation: ValidationSummary | None = None
    notes: list[str] = Field(
        default_factory=list, description="Anything the caller should know about this run"
    )


def _resolve_outcome(frames: dict, datasets: list, column: str) -> "pd.Series":
    """Find the outcome for each sample.

    Follows the order run_differential_expression already uses: a column in the
    data itself, otherwise the dataset's sample_metadata. Absent from both is an
    error rather than a silently dropped analysis.
    """
    import pandas as pd

    for frame in frames.values():
        if column in frame.columns:
            return frame[column]

    for dataset in datasets:
        metadata = dataset.sample_metadata or {}
        if not metadata:
            continue
        any_frame = next(iter(frames.values()))
        values = [metadata.get(str(sample), {}).get(column) for sample in any_frame.index]
        if any(v is not None for v in values):
            return pd.Series(values, index=any_frame.index, name=column)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"Outcome column '{column}' was not found in the selected datasets or "
            "their sample metadata. Biomarker discovery needs an outcome to test "
            "against."
        ),
    )


def _differential(joint, outcome, groups: list[str], log2fc_threshold: float):
    """Per-feature contrast between two outcome groups.

    Welch's t-test rather than Student's: it does not assume equal variance
    between the groups, which is the safer default for omics features. p-values
    are corrected with Benjamini-Hochberg, the same correction and function the
    existing differential expression task uses.
    """
    import numpy as np
    from scipy import stats
    from scipy.stats import false_discovery_control

    mask_a = outcome == groups[0]
    mask_b = outcome == groups[1]

    features, effects, pvalues = [], [], []
    for feature in joint.columns:
        a = joint.loc[mask_a, feature].dropna().values
        b = joint.loc[mask_b, feature].dropna().values
        if len(a) < 2 or len(b) < 2:
            continue
        mean_a, mean_b = float(a.mean()), float(b.mean())
        # Matches the existing task: only defined for strictly positive means.
        log2fc = float(np.log2(mean_b / mean_a)) if mean_a > 0 and mean_b > 0 else 0.0
        stat, pval = stats.ttest_ind(a, b, equal_var=False)
        if np.isnan(pval):
            continue
        features.append(feature)
        effects.append(log2fc)
        pvalues.append(float(pval))

    if not features:
        return {}, {}, {}

    qvalues = false_discovery_control(pvalues, method="bh")
    return (
        dict(zip(features, effects, strict=False)),
        dict(zip(features, pvalues, strict=False)),
        {f: float(q) for f, q in zip(features, qvalues, strict=False)},
    )


def _survival(joint, duration, event):
    """Univariate Cox proportional hazards per feature.

    Uses lifelines, already a project dependency. The effect reported is the log
    hazard ratio, so its sign is directly comparable with the log2 fold change
    from the differential path.
    """
    import numpy as np
    import pandas as pd
    from lifelines import CoxPHFitter
    from scipy.stats import false_discovery_control

    features, effects, pvalues = [], [], []
    for feature in joint.columns:
        frame = pd.DataFrame(
            {"T": duration.values, "E": event.values, "x": joint[feature].values}
        ).dropna()
        if frame.shape[0] < 5 or frame["E"].sum() < 2 or frame["x"].std() == 0:
            continue
        try:
            fitter = CoxPHFitter().fit(frame, duration_col="T", event_col="E")
        except Exception:
            # Non-convergence on a single feature should not abort the run.
            continue
        features.append(feature)
        effects.append(float(fitter.params_["x"]))
        pvalues.append(float(fitter.summary.loc["x", "p"]))

    if not features:
        return {}, {}, {}

    qvalues = false_discovery_control(np.clip(pvalues, 0.0, 1.0), method="bh")
    return (
        dict(zip(features, effects, strict=False)),
        dict(zip(features, pvalues, strict=False)),
        {f: float(q) for f, q in zip(features, qvalues, strict=False)},
    )


def _select_features(joint, target, method: str):
    """Run the requested selector from backend.ml."""
    from backend.ml.feature_selection import FeatureSelector

    selector = FeatureSelector()
    if method == "stability":
        return selector.stability_selection(joint, target)
    return selector.embedded_selection(joint, target, method=method)


def _cross_validate(joint, target, features: list[str], cv_folds: int):
    """Cross-validated performance of a model built on the reported biomarkers.

    Reported so the returned set can be judged, not to select it -- the features
    were chosen on the full data, so this is a summary of separability rather
    than an unbiased generalisation estimate. That caveat is returned in `notes`.
    """
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import LeaveOneOut, StratifiedKFold, cross_val_score

    X = joint[features].values
    y = np.asarray(target)

    if cv_folds == 0:
        cv, scheme, folds = LeaveOneOut(), "leave_one_out", len(y)
        metric = "accuracy"
    else:
        smallest = min(np.bincount(y).tolist()) if y.dtype.kind in "iu" else cv_folds
        splits = max(2, min(cv_folds, smallest))
        cv, scheme, folds = (
            StratifiedKFold(n_splits=splits, shuffle=True, random_state=42),
            "stratified_k_fold",
            splits,
        )
        metric = "roc_auc" if len(set(y.tolist())) == 2 else "accuracy"

    scores = cross_val_score(
        RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1),
        X,
        y,
        cv=cv,
        scoring=metric,
    )
    return ValidationSummary(
        scheme=scheme,
        folds=int(folds),
        metric=metric,
        score=float(np.mean(scores)),
        std=float(np.std(scores)) if len(scores) > 1 else None,
    )


@router.post("/discover", response_model=BiomarkerDiscoveryResponse)
async def discover_biomarkers(
    body: BiomarkerDiscoveryRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BiomarkerDiscoveryResponse:
    """Find features associated with an outcome across the selected datasets."""
    if body.analysis_type not in _ANALYSIS_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"analysis_type must be one of {sorted(_ANALYSIS_TYPES)}",
        )
    if body.feature_selection not in _SELECTION_METHODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"feature_selection must be one of {sorted(_SELECTION_METHODS)}",
        )
    if body.cv_folds not in _CV_CHOICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"cv_folds must be one of {sorted(_CV_CHOICES)} (0 = leave-one-out)",
        )

    result = await db.execute(select(Project).where(Project.id == body.project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if str(project.owner_id) != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to read datasets in this project",
        )

    result = await db.execute(
        select(Dataset).where(
            Dataset.id.in_(body.dataset_ids), Dataset.project_id == body.project_id
        )
    )
    datasets = list(result.scalars().all())
    found = {d.id for d in datasets}
    missing = [str(d) for d in body.dataset_ids if d not in found]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Datasets not found in this project: {missing}",
        )
    unreadable = [d.name for d in datasets if not d.storage_path]
    if unreadable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Datasets have no stored data yet: {unreadable}",
        )

    import pandas as pd
    from starlette.concurrency import run_in_threadpool

    frames: dict[str, Any] = {}
    origin: dict[str, Dataset] = {}
    for dataset in datasets:
        try:
            frame = await run_in_threadpool(_load_dataset_frame, dataset.storage_path)
        except Exception as exc:
            logger.error("Failed to read dataset %s: %s", dataset.id, _for_log(exc))
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Could not read stored data for dataset '{dataset.name}'",
            ) from exc
        frames[str(dataset.id)] = frame
        origin[str(dataset.id)] = dataset

    outcome = _resolve_outcome(frames, datasets, body.outcome_column)

    # Restrict to samples shared by every dataset and having an outcome.
    shared = None
    for frame in frames.values():
        index = set(frame.index)
        shared = index if shared is None else shared & index
    shared = sorted(s for s in (shared or set()) if outcome.get(s) is not None)
    if len(shared) < 4:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Fewer than four samples are shared across these datasets and have a "
                f"value for '{body.outcome_column}'. There is not enough to test."
            ),
        )

    # One wide matrix, columns prefixed so the source dataset stays visible.
    blocks, feature_origin = [], {}
    for key, frame in frames.items():
        numeric = frame.loc[shared].select_dtypes(include="number")
        numeric = numeric.drop(columns=[body.outcome_column], errors="ignore")
        if body.event_column:
            numeric = numeric.drop(columns=[body.event_column], errors="ignore")
        renamed = numeric.rename(columns={c: f"{origin[key].name}::{c}" for c in numeric.columns})
        for column in renamed.columns:
            feature_origin[column] = origin[key]
        blocks.append(renamed)
    joint = pd.concat(blocks, axis=1)
    outcome = outcome.loc[shared]

    if joint.shape[1] == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The selected datasets carry no numeric features to test.",
        )

    notes: list[str] = []
    groups_used: list[str] | None = None

    def _compute():
        if body.analysis_type == "survival":
            if not body.event_column:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Survival analysis needs event_column, the event indicator.",
                )
            events = _resolve_outcome(frames, datasets, body.event_column).loc[shared]
            return _survival(joint, outcome.astype(float), events.astype(float)), None

        values = [str(v) for v in outcome.tolist()]
        chosen = body.groups or sorted(set(values))
        if len(chosen) != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"'{body.outcome_column}' has {len(set(values))} distinct values "
                    f"({sorted(set(values))[:6]}). Give exactly two in `groups` to contrast."
                ),
            )
        as_str = outcome.astype(str)
        return _differential(joint, as_str, chosen, body.log2fc_threshold), chosen

    (effects, pvalues, qvalues), groups_used = await run_in_threadpool(_compute)

    if not pvalues:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No feature could be tested. Check that the datasets carry numeric "
                "values and that each outcome group has at least two samples."
            ),
        )

    significant = {
        f
        for f, q in qvalues.items()
        if q <= body.fdr_threshold
        and (
            body.analysis_type != "differential"
            or abs(effects.get(f, 0.0)) >= body.log2fc_threshold
        )
    }

    # Selection runs against a binary target in both cases: group membership for
    # differential, event indicator for survival.
    if body.analysis_type == "survival":
        target = _resolve_outcome(frames, datasets, body.event_column).loc[shared].astype(int)
    else:
        target = (outcome.astype(str) == groups_used[1]).astype(int)

    try:
        selection = await run_in_threadpool(_select_features, joint, target, body.feature_selection)
        selected = set(selection.selected_features)
        scores = selection.feature_scores
    except Exception as exc:
        logger.error("Feature selection failed: %s", _for_log(exc))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Feature selection ({body.feature_selection}) could not run on this data.",
        ) from exc

    keep = sorted(
        significant & selected,
        key=lambda f: (qvalues.get(f, 1.0), -abs(effects.get(f, 0.0))),
    )[: body.max_biomarkers]

    if not keep:
        notes.append(
            "No feature was both significant and retained by selection. "
            f"{len(significant)} passed the FDR threshold and {len(selected)} were "
            "selected, but the two sets do not overlap."
        )

    validation = None
    if keep:
        if body.cv_folds == 0 and len(shared) > _LOO_MAX_SAMPLES:
            notes.append(
                f"Leave-one-out was not run: it refits once per sample and this "
                f"cohort has {len(shared)}, above the {_LOO_MAX_SAMPLES} cap. "
                "Choose 5- or 10-fold."
            )
        else:
            try:
                validation = await run_in_threadpool(
                    _cross_validate, joint, target, keep, body.cv_folds
                )
                notes.append(
                    "Cross-validated score is reported on features chosen using all "
                    "samples, so it summarises separability rather than estimating "
                    "generalisation to unseen data."
                )
            except Exception as exc:
                logger.info("Cross-validation skipped: %s", _for_log(exc))
                notes.append(f"Cross-validation could not run: {_for_log(exc, 120)}")

    return BiomarkerDiscoveryResponse(
        analysis_type=body.analysis_type,
        outcome_column=body.outcome_column,
        outcome_groups=groups_used,
        n_samples=len(shared),
        n_features_tested=len(pvalues),
        n_significant=len(significant),
        n_selected=len(selected),
        biomarkers=[
            Biomarker(
                feature=f.split("::", 1)[1] if "::" in f else f,
                dataset_id=feature_origin[f].id,
                dataset_name=feature_origin[f].name,
                omics_type=getattr(
                    feature_origin[f].omics_type, "value", str(feature_origin[f].omics_type)
                ),
                effect=float(effects.get(f, 0.0)),
                p_value=float(pvalues.get(f, 1.0)),
                q_value=float(qvalues.get(f, 1.0)),
                selection_score=float(scores.get(f, 0.0)),
            )
            for f in keep
        ],
        selection_method=body.feature_selection,
        fdr_threshold=body.fdr_threshold,
        validation=validation,
        notes=notes,
    )

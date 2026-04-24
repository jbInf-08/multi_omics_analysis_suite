"""Data Processing Background Tasks.
================================

Celery tasks for file processing, quality control, normalization,
data cleanup, and batch import from external sources.
"""

import hashlib
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd

from backend.app.core.celery_app import OmicsTask, celery_app

logger = logging.getLogger(__name__)


def get_sync_session():
    """Get a synchronous database session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.app.core.config import settings

    sync_url = str(settings.DATABASE_URL).replace("+asyncpg", "")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)
    return Session()


def get_storage_path(dataset_id: str, filename: str = "data") -> Path:
    """Get storage path for dataset files."""
    from backend.app.core.config import settings

    base_path = Path(getattr(settings, "DATA_STORAGE_PATH", "./data"))
    dataset_path = base_path / dataset_id
    dataset_path.mkdir(parents=True, exist_ok=True)
    return dataset_path / filename


def compute_file_checksum(file_path: str) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


@celery_app.task(base=OmicsTask, bind=True, name="process_uploaded_file")
def process_uploaded_file(
    self,
    dataset_id: str,
    file_path: str,
    file_type: str,
    parameters: dict[str, Any] = None,
):
    """Process an uploaded data file.

    Args:
        dataset_id: Dataset ID
        file_path: Path to uploaded file
        file_type: File type (csv, tsv, parquet, vcf, maf, gct, h5ad)
        parameters: Processing parameters
            - index_col: int or str (column to use as index)
            - header: int (row number for header)
            - transpose: bool (transpose the data)
            - sample_col: str (column containing sample names)

    Returns:
        Dict with processing results and dataset statistics

    """
    parameters = parameters or {}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Reading file"})
        logger.info(f"Processing file {file_path} for dataset {dataset_id}")

        # Read file based on type
        df = None
        metadata = {}

        if file_type in ("csv", "txt"):
            df = pd.read_csv(
                file_path,
                index_col=parameters.get("index_col", 0),
                header=parameters.get("header", 0),
            )
        elif file_type == "tsv":
            df = pd.read_csv(
                file_path,
                sep="\t",
                index_col=parameters.get("index_col", 0),
                header=parameters.get("header", 0),
            )
        elif file_type == "parquet":
            df = pd.read_parquet(file_path)
            if parameters.get("index_col"):
                df = df.set_index(parameters["index_col"])
        elif file_type == "feather":
            df = pd.read_feather(file_path)
            if parameters.get("index_col"):
                df = df.set_index(parameters["index_col"])
        elif file_type == "excel" or file_type in ("xls", "xlsx"):
            df = pd.read_excel(
                file_path,
                index_col=parameters.get("index_col", 0),
                sheet_name=parameters.get("sheet_name", 0),
            )
        elif file_type == "gct":
            # GCT format (gene expression)
            df = pd.read_csv(file_path, sep="\t", skiprows=2, index_col=0)
            df = df.drop(columns=["Description"], errors="ignore")
            metadata["format"] = "GCT"
        elif file_type == "vcf":
            # VCF format (variant calls) - basic parsing
            try:
                import io

                with open(file_path) as f:
                    lines = [l for l in f if not l.startswith("##")]
                df = pd.read_csv(io.StringIO("\n".join(lines)), sep="\t")
                metadata["format"] = "VCF"
                metadata["n_variants"] = len(df)
            except Exception as e:
                logger.warning(f"VCF parsing error: {e}")
                df = pd.DataFrame()
        elif file_type == "maf":
            # MAF format (mutation annotation)
            df = pd.read_csv(file_path, sep="\t", comment="#")
            metadata["format"] = "MAF"
            metadata["n_mutations"] = len(df)
        elif file_type == "h5ad":
            # AnnData format
            try:
                import scanpy as sc

                adata = sc.read_h5ad(file_path)
                df = pd.DataFrame(
                    adata.X.toarray() if hasattr(adata.X, "toarray") else adata.X,
                    index=adata.obs_names,
                    columns=adata.var_names,
                )
                metadata["format"] = "h5ad"
                metadata["obs_columns"] = list(adata.obs.columns)
                metadata["var_columns"] = list(adata.var.columns)
            except ImportError:
                raise ImportError("scanpy not installed for h5ad support")
        else:
            # Try generic CSV
            df = pd.read_csv(file_path, index_col=parameters.get("index_col", 0))

        self.update_state(state="PROGRESS", meta={"progress": 0.3, "step": "Validating data"})

        # Transpose if requested
        if parameters.get("transpose", False):
            df = df.T

        # Basic validation
        if df is None or df.empty:
            raise ValueError("Failed to read file or file is empty")

        # Infer data types
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        non_numeric_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

        # Compute statistics
        n_samples = df.shape[0]
        n_features = df.shape[1]

        stats = {
            "n_samples": n_samples,
            "n_features": n_features,
            "n_numeric_features": len(numeric_cols),
            "n_non_numeric_features": len(non_numeric_cols),
            "missing_values": int(df.isna().sum().sum()),
            "missing_percentage": float(df.isna().sum().sum() / (n_samples * n_features) * 100),
        }

        # Numeric feature statistics
        if numeric_cols:
            numeric_df = df[numeric_cols]
            stats["numeric_stats"] = {
                "mean_of_means": float(numeric_df.mean().mean()),
                "mean_of_stds": float(numeric_df.std().mean()),
                "min": float(numeric_df.min().min()),
                "max": float(numeric_df.max().max()),
            }

        self.update_state(state="PROGRESS", meta={"progress": 0.6, "step": "Saving processed data"})

        # Save processed data
        storage_path = get_storage_path(dataset_id, "data.parquet")
        df.to_parquet(storage_path)

        # Compute checksum
        file_checksum = compute_file_checksum(str(storage_path))

        self.update_state(state="PROGRESS", meta={"progress": 0.8, "step": "Updating database"})

        # Update dataset in database
        session = get_sync_session()
        try:
            from backend.app.models.dataset import Dataset, DatasetStatus

            dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
            if dataset:
                dataset.sample_count = n_samples
                dataset.feature_count = n_features
                dataset.storage_path = str(storage_path)
                dataset.data_format = "parquet"
                dataset.status = DatasetStatus.READY
                dataset.dataset_metadata = {
                    **dataset.dataset_metadata,
                    "original_file": file_path,
                    "original_format": file_type,
                    "processing_stats": stats,
                    "checksum": file_checksum,
                    **metadata,
                }
                dataset.updated_at = datetime.now(timezone.utc)
                session.commit()
        finally:
            session.close()

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"File processing completed: {n_samples} samples, {n_features} features")

        return {
            "status": "completed",
            "dataset_id": dataset_id,
            "file_type": file_type,
            "storage_path": str(storage_path),
            "statistics": stats,
            "sample_names": df.index.tolist()[:100],
            "feature_names": df.columns.tolist()[:100],
        }

    except Exception as e:
        logger.error(f"File processing failed: {e}\n{traceback.format_exc()}")

        # Update dataset status to error
        session = get_sync_session()
        try:
            from backend.app.models.dataset import Dataset, DatasetStatus

            dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
            if dataset:
                dataset.status = DatasetStatus.ERROR
                dataset.dataset_metadata = {
                    **dataset.dataset_metadata,
                    "error": str(e),
                }
                session.commit()
        finally:
            session.close()

        return {
            "status": "failed",
            "dataset_id": dataset_id,
            "file_type": file_type,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="run_quality_control")
def run_quality_control(
    self,
    dataset_id: str,
    parameters: dict[str, Any] = None,
):
    """Run quality control on a dataset.

    Args:
        dataset_id: Dataset ID
        parameters: QC parameters
            - missing_threshold: float (max missing % per sample, default 0.5)
            - variance_threshold: float (min variance per feature, default 0.01)
            - outlier_method: str (zscore, iqr, default zscore)
            - outlier_threshold: float (default 3.0 for zscore)
            - min_samples: int (min samples per group)

    Returns:
        Dict with QC metrics and recommendations

    """
    parameters = parameters or {}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading data"})
        logger.info(f"Running QC on dataset {dataset_id}")

        # Load dataset
        session = get_sync_session()
        try:
            from backend.app.models.dataset import Dataset

            dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
            if not dataset or not dataset.storage_path:
                raise ValueError(f"Dataset {dataset_id} not found")

            df = pd.read_parquet(dataset.storage_path)
        finally:
            session.close()

        n_samples = df.shape[0]
        n_features = df.shape[1]

        qc_results = {
            "n_samples": n_samples,
            "n_features": n_features,
            "metrics": {},
            "warnings": [],
            "recommendations": [],
            "passed": True,
        }

        self.update_state(
            state="PROGRESS", meta={"progress": 0.2, "step": "Checking missing values"}
        )

        # 1. Missing value analysis
        missing_per_sample = df.isna().mean(axis=1)
        missing_per_feature = df.isna().mean(axis=0)

        missing_threshold = parameters.get("missing_threshold", 0.5)
        samples_high_missing = (missing_per_sample > missing_threshold).sum()
        features_high_missing = (missing_per_feature > missing_threshold).sum()

        qc_results["metrics"]["missing"] = {
            "total_missing": int(df.isna().sum().sum()),
            "missing_percentage": float(df.isna().sum().sum() / (n_samples * n_features) * 100),
            "samples_high_missing": int(samples_high_missing),
            "features_high_missing": int(features_high_missing),
            "max_sample_missing": float(missing_per_sample.max()),
            "max_feature_missing": float(missing_per_feature.max()),
        }

        if samples_high_missing > 0:
            qc_results["warnings"].append(
                f"{samples_high_missing} samples have >{missing_threshold*100}% missing values"
            )
            qc_results["recommendations"].append(
                "Consider removing samples with high missing rates"
            )

        if features_high_missing > 0:
            qc_results["warnings"].append(
                f"{features_high_missing} features have >{missing_threshold*100}% missing values"
            )
            qc_results["recommendations"].append(
                "Consider removing features with high missing rates"
            )

        self.update_state(state="PROGRESS", meta={"progress": 0.4, "step": "Analyzing variance"})

        # 2. Variance analysis (numeric columns only)
        numeric_df = df.select_dtypes(include=[np.number])

        if not numeric_df.empty:
            variances = numeric_df.var()
            variance_threshold = parameters.get("variance_threshold", 0.01)
            low_variance_features = (variances < variance_threshold).sum()

            qc_results["metrics"]["variance"] = {
                "mean_variance": float(variances.mean()),
                "median_variance": float(variances.median()),
                "low_variance_features": int(low_variance_features),
                "zero_variance_features": int((variances == 0).sum()),
            }

            if low_variance_features > n_features * 0.1:
                qc_results["warnings"].append(f"{low_variance_features} features have low variance")
                qc_results["recommendations"].append("Consider filtering low-variance features")

        self.update_state(state="PROGRESS", meta={"progress": 0.6, "step": "Detecting outliers"})

        # 3. Outlier detection
        if not numeric_df.empty:
            outlier_method = parameters.get("outlier_method", "zscore")
            outlier_threshold = parameters.get("outlier_threshold", 3.0)

            if outlier_method == "zscore":
                from scipy import stats

                z_scores = np.abs(
                    stats.zscore(numeric_df.fillna(numeric_df.median()), nan_policy="omit")
                )
                outlier_mask = z_scores > outlier_threshold
                outlier_samples = outlier_mask.any(axis=1).sum()
                outlier_features = outlier_mask.any(axis=0).sum()
            elif outlier_method == "iqr":
                Q1 = numeric_df.quantile(0.25)
                Q3 = numeric_df.quantile(0.75)
                IQR = Q3 - Q1
                outlier_mask = (numeric_df < (Q1 - 1.5 * IQR)) | (numeric_df > (Q3 + 1.5 * IQR))
                outlier_samples = outlier_mask.any(axis=1).sum()
                outlier_features = outlier_mask.any(axis=0).sum()
            else:
                outlier_samples = 0
                outlier_features = 0

            qc_results["metrics"]["outliers"] = {
                "method": outlier_method,
                "threshold": outlier_threshold,
                "samples_with_outliers": int(outlier_samples),
                "features_with_outliers": int(outlier_features),
            }

            if outlier_samples > n_samples * 0.1:
                qc_results["warnings"].append(f"{outlier_samples} samples contain outlier values")

        self.update_state(
            state="PROGRESS", meta={"progress": 0.8, "step": "Computing distribution metrics"}
        )

        # 4. Distribution analysis
        if not numeric_df.empty:
            # Compute skewness and kurtosis
            skewness = numeric_df.skew()
            kurtosis = numeric_df.kurtosis()

            highly_skewed = (np.abs(skewness) > 2).sum()

            qc_results["metrics"]["distribution"] = {
                "mean_skewness": float(skewness.mean()),
                "mean_kurtosis": float(kurtosis.mean()),
                "highly_skewed_features": int(highly_skewed),
            }

            if highly_skewed > n_features * 0.3:
                qc_results["recommendations"].append(
                    "Consider log-transformation for highly skewed features"
                )

        # 5. Overall QC pass/fail
        fail_conditions = [
            qc_results["metrics"]["missing"]["missing_percentage"] > 50,
            samples_high_missing > n_samples * 0.3,
            features_high_missing > n_features * 0.3,
        ]

        qc_results["passed"] = not any(fail_conditions)

        self.update_state(state="PROGRESS", meta={"progress": 0.95, "step": "Updating database"})

        # Update dataset in database
        session = get_sync_session()
        try:
            from backend.app.models.dataset import Dataset

            dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
            if dataset:
                dataset.qc_passed = qc_results["passed"]
                dataset.qc_metrics = qc_results["metrics"]
                dataset.updated_at = datetime.now(timezone.utc)
                session.commit()
        finally:
            session.close()

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"QC completed: passed={qc_results['passed']}")

        return {
            "status": "completed",
            "dataset_id": dataset_id,
            "qc_passed": qc_results["passed"],
            **qc_results,
        }

    except Exception as e:
        logger.error(f"QC failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "dataset_id": dataset_id,
            "qc_passed": False,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="normalize_dataset")
def normalize_dataset(
    self,
    dataset_id: str,
    method: str = "quantile",
    parameters: dict[str, Any] = None,
):
    """Normalize a dataset.

    Args:
        dataset_id: Dataset ID
        method: Normalization method
            - zscore: Z-score standardization
            - minmax: Min-max scaling
            - quantile: Quantile normalization
            - log2: Log2 transformation (adds pseudocount)
            - vst: Variance stabilizing transformation
            - tmm: TMM normalization (for RNA-seq)
            - rpkm: RPKM normalization (requires gene lengths)
            - tpm: TPM normalization (requires gene lengths)
        parameters: Method parameters
            - pseudocount: float (for log transforms, default 1)
            - target_sum: float (for TPM/RPKM, default 1e6)

    Returns:
        Dict with normalization statistics

    """
    parameters = parameters or {}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading data"})
        logger.info(f"Normalizing dataset {dataset_id} with method={method}")

        # Load dataset
        session = get_sync_session()
        try:
            from backend.app.models.dataset import Dataset

            dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
            if not dataset or not dataset.storage_path:
                raise ValueError(f"Dataset {dataset_id} not found")

            df = pd.read_parquet(dataset.storage_path)
        finally:
            session.close()

        # Get numeric columns only
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        non_numeric_df = df.drop(columns=numeric_cols)
        numeric_df = df[numeric_cols]

        self.update_state(
            state="PROGRESS", meta={"progress": 0.2, "step": f"Applying {method} normalization"}
        )

        # Store pre-normalization stats
        pre_stats = {
            "mean": float(numeric_df.mean().mean()),
            "std": float(numeric_df.std().mean()),
            "min": float(numeric_df.min().min()),
            "max": float(numeric_df.max().max()),
        }

        # Apply normalization
        if method == "zscore":
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            normalized = scaler.fit_transform(numeric_df.fillna(0))
            normalized_df = pd.DataFrame(
                normalized, index=numeric_df.index, columns=numeric_df.columns
            )

        elif method == "minmax":
            from sklearn.preprocessing import MinMaxScaler

            scaler = MinMaxScaler()
            normalized = scaler.fit_transform(numeric_df.fillna(0))
            normalized_df = pd.DataFrame(
                normalized, index=numeric_df.index, columns=numeric_df.columns
            )

        elif method == "quantile":
            from sklearn.preprocessing import QuantileTransformer

            transformer = QuantileTransformer(output_distribution="normal", random_state=42)
            normalized = transformer.fit_transform(numeric_df.fillna(numeric_df.median()))
            normalized_df = pd.DataFrame(
                normalized, index=numeric_df.index, columns=numeric_df.columns
            )

        elif method == "log2":
            pseudocount = parameters.get("pseudocount", 1)
            # Ensure non-negative values
            min_val = numeric_df.min().min()
            if min_val < 0:
                numeric_df = numeric_df - min_val
            normalized_df = np.log2(numeric_df + pseudocount)

        elif method == "log10":
            pseudocount = parameters.get("pseudocount", 1)
            min_val = numeric_df.min().min()
            if min_val < 0:
                numeric_df = numeric_df - min_val
            normalized_df = np.log10(numeric_df + pseudocount)

        elif method == "vst":
            # Variance Stabilizing Transformation (simplified)
            # For proper VST, use DESeq2 or similar
            pseudocount = parameters.get("pseudocount", 1)
            min_val = numeric_df.min().min()
            if min_val < 0:
                numeric_df = numeric_df - min_val
            normalized_df = np.sqrt(numeric_df + pseudocount)

        elif method == "tmm":
            # Trimmed Mean of M-values (simplified)
            # Scale each sample to have the same sum
            sample_sums = numeric_df.sum(axis=1)
            scaling_factors = sample_sums / sample_sums.median()
            normalized_df = numeric_df.div(scaling_factors, axis=0)

        elif method == "tpm":
            # Transcripts Per Million
            target_sum = parameters.get("target_sum", 1e6)
            sample_sums = numeric_df.sum(axis=1)
            normalized_df = numeric_df.div(sample_sums, axis=0) * target_sum

        elif method == "rpkm":
            # Reads Per Kilobase per Million (simplified - assumes 1kb genes)
            target_sum = parameters.get("target_sum", 1e6)
            sample_sums = numeric_df.sum(axis=1)
            normalized_df = numeric_df.div(sample_sums, axis=0) * target_sum

        elif method == "median_center":
            # Center each feature by its median
            normalized_df = numeric_df - numeric_df.median()

        elif method == "robust":
            # Robust scaling using median and IQR
            from sklearn.preprocessing import RobustScaler

            scaler = RobustScaler()
            normalized = scaler.fit_transform(numeric_df.fillna(numeric_df.median()))
            normalized_df = pd.DataFrame(
                normalized, index=numeric_df.index, columns=numeric_df.columns
            )

        else:
            raise ValueError(f"Unknown normalization method: {method}")

        self.update_state(
            state="PROGRESS", meta={"progress": 0.6, "step": "Saving normalized data"}
        )

        # Combine with non-numeric columns
        if not non_numeric_df.empty:
            final_df = pd.concat([normalized_df, non_numeric_df], axis=1)
        else:
            final_df = normalized_df

        # Post-normalization stats
        post_stats = {
            "mean": float(normalized_df.mean().mean()),
            "std": float(normalized_df.std().mean()),
            "min": float(normalized_df.min().min()),
            "max": float(normalized_df.max().max()),
        }

        # Save normalized data
        storage_path = get_storage_path(dataset_id, "data_normalized.parquet")
        final_df.to_parquet(storage_path)

        self.update_state(state="PROGRESS", meta={"progress": 0.8, "step": "Updating database"})

        # Update dataset in database
        session = get_sync_session()
        try:
            from backend.app.models.dataset import Dataset

            dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
            if dataset:
                dataset.storage_path = str(storage_path)
                dataset.normalization_method = method
                dataset.preprocessing_applied = dataset.preprocessing_applied + [
                    f"normalized_{method}"
                ]
                dataset.dataset_metadata = {
                    **dataset.dataset_metadata,
                    "normalization": {
                        "method": method,
                        "parameters": parameters,
                        "pre_stats": pre_stats,
                        "post_stats": post_stats,
                    },
                }
                dataset.updated_at = datetime.now(timezone.utc)
                session.commit()
        finally:
            session.close()

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"Normalization completed: {method}")

        return {
            "status": "completed",
            "dataset_id": dataset_id,
            "method": method,
            "pre_normalization_stats": pre_stats,
            "post_normalization_stats": post_stats,
            "storage_path": str(storage_path),
        }

    except Exception as e:
        logger.error(f"Normalization failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "dataset_id": dataset_id,
            "method": method,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, name="cleanup_old_results")
def cleanup_old_results(
    max_age_days: int = 30,
    dry_run: bool = False,
):
    """Clean up old analysis results.

    Runs periodically to remove old/expired results.

    Args:
        max_age_days: Maximum age in days for results
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with cleanup statistics

    """
    try:
        logger.info(f"Running cleanup for results older than {max_age_days} days")

        from datetime import timedelta

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        session = get_sync_session()
        cleanup_stats = {
            "analysis_results_deleted": 0,
            "files_deleted": 0,
            "space_freed_mb": 0,
        }

        try:
            from backend.app.models.analysis import Analysis, AnalysisResult, AnalysisStatus

            # Find old completed/failed analyses
            old_analyses = (
                session.query(Analysis)
                .filter(
                    Analysis.created_at < cutoff_date,
                    Analysis.status.in_([AnalysisStatus.COMPLETED, AnalysisStatus.FAILED]),
                )
                .all()
            )

            for analysis in old_analyses:
                # Get associated results
                results = (
                    session.query(AnalysisResult)
                    .filter(AnalysisResult.analysis_id == analysis.id)
                    .all()
                )

                for result in results:
                    if not dry_run:
                        session.delete(result)
                    cleanup_stats["analysis_results_deleted"] += 1

            # Clean up orphaned files
            from backend.app.core.config import settings

            data_path = Path(getattr(settings, "DATA_STORAGE_PATH", "./data"))
            model_path = Path(getattr(settings, "MODEL_STORAGE_PATH", "./models"))

            for path in [data_path, model_path]:
                if path.exists():
                    for item in path.iterdir():
                        if item.is_file():
                            file_age = datetime.now(timezone.utc) - datetime.fromtimestamp(
                                item.stat().st_mtime, tz=timezone.utc
                            )
                            if file_age > timedelta(days=max_age_days):
                                size_mb = item.stat().st_size / (1024 * 1024)
                                if not dry_run:
                                    item.unlink()
                                cleanup_stats["files_deleted"] += 1
                                cleanup_stats["space_freed_mb"] += size_mb

            if not dry_run:
                session.commit()

        finally:
            session.close()

        logger.info(f"Cleanup completed: {cleanup_stats}")

        return {
            "status": "completed",
            "dry_run": dry_run,
            "max_age_days": max_age_days,
            **cleanup_stats,
        }

    except Exception as e:
        logger.error(f"Cleanup failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, name="update_data_sources")
def update_data_sources(
    sources: list[str] = None,
):
    """Update data from external sources.

    Runs periodically to fetch new data from configured sources.

    Args:
        sources: List of sources to update (None for all)

    Returns:
        Dict with update statistics

    """
    try:
        logger.info(f"Updating data sources: {sources or 'all'}")

        update_stats = {
            "sources_checked": 0,
            "sources_updated": 0,
            "new_records": 0,
            "errors": [],
        }

        # Import collectors
        from backend.data_collection.base_collector import CollectorRegistry, DataSource

        # Get sources to update
        if sources:
            sources_to_check = [DataSource(s) for s in sources if hasattr(DataSource, s.upper())]
        else:
            sources_to_check = list(DataSource)

        import asyncio

        async def check_source(source: DataSource):
            try:
                collector = CollectorRegistry.get(source)
                if collector:
                    # Just verify connectivity
                    result = await collector.collect()
                    return {
                        "source": source.value,
                        "success": result.success,
                        "records": result.records_collected,
                    }
            except Exception as e:
                return {
                    "source": source.value,
                    "success": False,
                    "error": str(e),
                }
            return None

        # Run checks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            for source in sources_to_check[:5]:  # Limit to 5 sources
                result = loop.run_until_complete(check_source(source))
                if result:
                    update_stats["sources_checked"] += 1
                    if result.get("success"):
                        update_stats["sources_updated"] += 1
                        update_stats["new_records"] += result.get("records", 0)
                    elif result.get("error"):
                        update_stats["errors"].append(result)
        finally:
            loop.close()

        logger.info(f"Data source update completed: {update_stats}")

        return {
            "status": "completed",
            **update_stats,
        }

    except Exception as e:
        logger.error(f"Data source update failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="batch_import_datasets")
def batch_import_datasets(
    self,
    source: str,
    query: dict[str, Any],
    parameters: dict[str, Any] = None,
    project_id: str = None,
):
    """Batch import datasets from an external source.

    Args:
        source: Data source (tcga, geo, icgc, encode, gtex, ccle)
        query: Query parameters
            - cancer_type: str (for TCGA, ICGC)
            - accessions: List[str] (for GEO)
            - genes: List[str]
            - data_types: List[str]
        parameters: Import parameters
            - max_datasets: int
            - save_raw: bool
        project_id: Project ID to associate datasets with

    Returns:
        Dict with import statistics and created dataset IDs

    """
    parameters = parameters or {}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Connecting to source"})
        logger.info(f"Batch importing from {source}")

        from backend.data_collection.base_collector import CollectorRegistry, DataSource

        # Get collector
        try:
            data_source = DataSource(source.upper())
        except ValueError:
            raise ValueError(f"Unknown data source: {source}")

        collector = CollectorRegistry.get(data_source)
        if not collector:
            raise ValueError(f"No collector registered for {source}")

        self.update_state(state="PROGRESS", meta={"progress": 0.1, "step": "Fetching data"})

        # Run collection
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(collector.collect(**query))
        finally:
            loop.close()

        if not result.success:
            raise ValueError(f"Collection failed: {result.errors}")

        self.update_state(state="PROGRESS", meta={"progress": 0.4, "step": "Processing results"})

        # Process collected data
        import_stats = {
            "source": source,
            "datasets_created": 0,
            "datasets_failed": 0,
            "dataset_ids": [],
            "total_records": result.records_collected,
        }

        max_datasets = parameters.get("max_datasets", 10)

        # Create datasets from collected data
        session = get_sync_session()
        try:
            from backend.app.models.dataset import Dataset, DatasetStatus, OmicsType
            from backend.app.models.project import Project

            # Get project
            if project_id:
                session.query(Project).filter(Project.id == UUID(project_id)).first()

            # Process each data item
            data_items = result.data if isinstance(result.data, dict) else {"data": result.data}

            for i, (key, data) in enumerate(list(data_items.items())[:max_datasets]):
                try:
                    # Skip non-data items
                    if not data or key.startswith("note"):
                        continue

                    # Create dataset
                    dataset_id = str(uuid_lib.uuid4())

                    # Determine omics type
                    omics_type = OmicsType.GENOMICS
                    if "expression" in key.lower():
                        omics_type = OmicsType.TRANSCRIPTOMICS
                    elif "protein" in key.lower():
                        omics_type = OmicsType.PROTEOMICS
                    elif "methylation" in key.lower():
                        omics_type = OmicsType.EPIGENOMICS

                    # Convert data to DataFrame if possible
                    if isinstance(data, list):
                        df = pd.DataFrame(data)
                    elif isinstance(data, dict):
                        df = pd.DataFrame([data])
                    else:
                        continue

                    if df.empty:
                        continue

                    # Save data
                    storage_path = get_storage_path(dataset_id, "data.parquet")
                    df.to_parquet(storage_path)

                    # Create dataset record
                    dataset = Dataset(
                        id=UUID(dataset_id),
                        name=f"{source}_{key}",
                        description=f"Imported from {source}",
                        omics_type=omics_type,
                        data_format="parquet",
                        sample_count=len(df),
                        feature_count=len(df.columns),
                        status=DatasetStatus.READY,
                        source=source,
                        source_id=key,
                        storage_path=str(storage_path),
                        project_id=UUID(project_id) if project_id else None,
                        dataset_metadata={
                            "import_query": query,
                            "import_timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                    session.add(dataset)
                    import_stats["datasets_created"] += 1
                    import_stats["dataset_ids"].append(dataset_id)

                    progress = 0.4 + 0.5 * (i + 1) / min(len(data_items), max_datasets)
                    self.update_state(
                        state="PROGRESS",
                        meta={"progress": progress, "step": f"Created {i+1} datasets"},
                    )

                except Exception as e:
                    logger.warning(f"Failed to create dataset for {key}: {e}")
                    import_stats["datasets_failed"] += 1

            session.commit()

        finally:
            session.close()

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"Batch import completed: {import_stats}")

        return {
            "status": "completed",
            **import_stats,
        }

    except Exception as e:
        logger.error(f"Batch import failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "source": source,
            "error": str(e),
        }


# Add missing import
import uuid as uuid_lib

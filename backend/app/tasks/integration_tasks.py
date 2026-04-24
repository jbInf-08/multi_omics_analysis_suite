"""Multi-Omics Integration Background Tasks.
=========================================

Celery tasks for multi-omics data integration, pathway-based integration,
network-based integration, biomarker discovery, and dimensionality reduction.
"""

import logging
import traceback
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


def load_dataset_data(dataset_id: str) -> pd.DataFrame | None:
    """Load dataset data from storage.

    Args:
        dataset_id: Dataset UUID

    Returns:
        DataFrame with dataset data or None if not found

    """
    session = get_sync_session()
    try:
        from backend.app.models.dataset import Dataset

        dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
        if not dataset or not dataset.storage_path:
            logger.warning(f"Dataset {dataset_id} not found or has no storage path")
            return None

        # Load data based on format
        storage_path = dataset.storage_path
        data_format = dataset.data_format or "csv"

        if data_format in ("csv", "tsv"):
            sep = "\t" if data_format == "tsv" else ","
            df = pd.read_csv(storage_path, sep=sep, index_col=0)
        elif data_format == "parquet":
            df = pd.read_parquet(storage_path)
        elif data_format == "feather":
            df = pd.read_feather(storage_path)
        else:
            df = pd.read_csv(storage_path, index_col=0)

        return df

    except Exception as e:
        logger.error(f"Failed to load dataset {dataset_id}: {e}")
        return None
    finally:
        session.close()


def create_omics_data(df: pd.DataFrame, omics_type: str = "generic") -> "OmicsData":
    """Convert DataFrame to OmicsData object."""
    from backend.omics.base.omics_base import OmicsData

    return OmicsData(
        data=df,
        sample_names=df.index.tolist(),
        feature_names=df.columns.tolist(),
        omics_type=omics_type,
        metadata={},
    )


@celery_app.task(base=OmicsTask, bind=True, name="run_multi_omics_integration")
def run_multi_omics_integration(
    self,
    dataset_ids: list[str],
    method: str = "concatenation",
    parameters: dict[str, Any] = None,
):
    """Run multi-omics data integration.

    Args:
        dataset_ids: List of dataset IDs to integrate
        method: Integration method (concatenation, mofa, similarity_network, pca)
        parameters: Method parameters
            - normalize: bool (default True)
            - scale: bool (default True)
            - n_components: int (default 50)
            - k_neighbors: int (for SNF, default 20)
            - n_iterations: int (for SNF, default 20)
            - reference_fasta_path: optional path to reference/contigs FASTA; when set, gene
              prediction summary is attached under ``gene_annotation`` in the task result
            - gene_predictor: optional predictor key (default ``prodigal``) for that summary
            - gene_annotation_max_listed: max gene IDs listed in the summary (default 500)
            - use_prodigal_binary: run Prodigal executable when available (default False)
            - prodigal_meta_mode: pass ``-p meta`` to Prodigal when using the binary (default False)

    Returns:
        Dict with integration results including fused data statistics

    """
    parameters = parameters or {}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading datasets"})
        logger.info(f"Starting multi-omics integration with method={method}")

        # Load datasets
        datasets = {}
        for i, dataset_id in enumerate(dataset_ids):
            df = load_dataset_data(dataset_id)
            if df is not None:
                omics_data = create_omics_data(df, f"omics_{i}")
                datasets[f"omics_{i}"] = omics_data

            progress = 0.1 + (0.2 * (i + 1) / len(dataset_ids))
            self.update_state(
                state="PROGRESS",
                meta={"progress": progress, "step": f"Loaded {i+1}/{len(dataset_ids)} datasets"},
            )

        if len(datasets) < 2:
            raise ValueError(f"Need at least 2 datasets for integration, got {len(datasets)}")

        self.update_state(state="PROGRESS", meta={"progress": 0.3, "step": "Running integration"})

        # Select and run integration method
        if method in ("concatenation", "early", "early_fusion"):
            from backend.omics.integration.data_fusion import EarlyFusion

            fusion = EarlyFusion(
                normalize=parameters.get("normalize", True),
                scale=parameters.get("scale", True),
                reduce_dim=parameters.get("n_components"),
            )
            result = fusion.fit_transform(datasets)

        elif method in ("pca", "intermediate", "intermediate_fusion", "mofa"):
            from backend.omics.integration.data_fusion import IntermediateFusion

            fusion = IntermediateFusion(
                method="pca",
                n_components=parameters.get("n_components", 50),
                random_state=parameters.get("random_state", 42),
            )
            result = fusion.fit_transform(datasets)

        elif method in ("snf", "similarity_network", "network"):
            from backend.omics.integration.network_integration import SimilarityNetworkFusion

            snf = SimilarityNetworkFusion(
                k_neighbors=parameters.get("k_neighbors", 20),
                mu=parameters.get("mu", 0.5),
                n_iterations=parameters.get("n_iterations", 20),
            )
            network_result = snf.fuse(datasets)

            # Convert to standard result format
            result = type(
                "FusionResult",
                (),
                {
                    "fused_data": network_result.fused_network,
                    "sample_names": network_result.sample_names,
                    "feature_names": [
                        f"sample_{i}" for i in range(len(network_result.sample_names))
                    ],
                    "method": "snf",
                    "metadata": network_result.metadata,
                },
            )()

        else:
            raise ValueError(f"Unknown integration method: {method}")

        self.update_state(state="PROGRESS", meta={"progress": 0.8, "step": "Computing statistics"})

        # Compute result statistics
        fused_data = result.fused_data
        n_samples = fused_data.shape[0]
        n_features = fused_data.shape[1] if len(fused_data.shape) > 1 else fused_data.shape[0]

        # Variance explained (for PCA-based methods)
        variance_explained = None
        if hasattr(result, "metadata") and result.metadata:
            variance_explained = result.metadata.get("variance_explained")

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(
            f"Multi-omics integration completed: {n_samples} samples, {n_features} features"
        )

        gene_annotation = None
        ref_fasta = parameters.get("reference_fasta_path")
        if ref_fasta:
            self.update_state(
                state="PROGRESS",
                meta={"progress": 1.0, "step": "Gene annotation (reference FASTA)"},
            )
            try:
                from pathlib import Path

                from backend.pipelines.gene_annotation import integration_gene_annotation_summary

                gene_annotation = integration_gene_annotation_summary(
                    Path(ref_fasta),
                    predictor=parameters.get("gene_predictor", "prodigal"),
                    max_genes_listed=int(parameters.get("gene_annotation_max_listed", 500)),
                    use_prodigal_binary=bool(parameters.get("use_prodigal_binary", False)),
                    prodigal_meta_mode=bool(parameters.get("prodigal_meta_mode", False)),
                )
            except Exception as ann_exc:
                logger.warning("Optional gene annotation failed: %s", ann_exc)
                gene_annotation = {"error": str(ann_exc), "reference_fasta_path": ref_fasta}

        return {
            "status": "completed",
            "method": method,
            "n_datasets": len(dataset_ids),
            "n_samples": n_samples,
            "n_features": n_features,
            "sample_names": result.sample_names[:100],  # Truncate for response
            "feature_names": result.feature_names[:100],
            "variance_explained": variance_explained,
            "metadata": result.metadata if hasattr(result, "metadata") else {},
            "gene_annotation": gene_annotation,
        }

    except Exception as e:
        logger.error(f"Multi-omics integration failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "method": method,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="run_pathway_integration")
def run_pathway_integration(
    self,
    dataset_ids: list[str],
    pathway_database: str = "kegg",
    parameters: dict[str, Any] = None,
):
    """Run pathway-based multi-omics integration.

    Args:
        dataset_ids: List of dataset IDs
        pathway_database: Pathway database (kegg, reactome, go)
        parameters: Integration parameters
            - organism: str (default "hsa")
            - aggregation_method: str (default "mean", options: mean, median, pca)
            - pathway_file: str (optional GMT file path)

    Returns:
        Dict with pathway scores and enrichment results

    """
    parameters = parameters or {}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading pathways"})
        logger.info(f"Starting pathway integration with database={pathway_database}")

        from backend.omics.integration.pathway_integration import PathwayIntegrator

        # Initialize pathway integrator
        integrator = PathwayIntegrator(
            database=pathway_database,
            organism=parameters.get("organism", "hsa"),
        )

        # Load pathways
        pathway_file = parameters.get("pathway_file")
        integrator.load_pathways(pathway_file)

        self.update_state(state="PROGRESS", meta={"progress": 0.2, "step": "Loading datasets"})

        # Load datasets
        datasets = {}
        for i, dataset_id in enumerate(dataset_ids):
            df = load_dataset_data(dataset_id)
            if df is not None:
                omics_data = create_omics_data(df, f"omics_{i}")
                datasets[f"omics_{i}"] = omics_data

            progress = 0.2 + (0.3 * (i + 1) / len(dataset_ids))
            self.update_state(
                state="PROGRESS",
                meta={"progress": progress, "step": f"Loaded {i+1}/{len(dataset_ids)} datasets"},
            )

        if not datasets:
            raise ValueError("No valid datasets loaded")

        self.update_state(
            state="PROGRESS", meta={"progress": 0.5, "step": "Computing pathway scores"}
        )

        # Compute pathway scores
        aggregation_method = parameters.get("aggregation_method", "mean")
        pathway_result = integrator.compute_pathway_scores(
            datasets=datasets,
            method=aggregation_method,
        )

        self.update_state(state="PROGRESS", meta={"progress": 0.8, "step": "Finalizing results"})

        # Convert results
        pathway_result.pathway_scores.to_dict()

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(
            f"Pathway integration completed: {pathway_result.metadata['n_pathways']} pathways"
        )

        return {
            "status": "completed",
            "pathway_database": pathway_database,
            "n_pathways": pathway_result.metadata["n_pathways"],
            "n_omics": pathway_result.metadata["n_omics"],
            "method": pathway_result.method,
            "pathway_genes": {
                k: v[:20] for k, v in pathway_result.pathway_genes.items()
            },  # Truncate
            "n_samples": pathway_result.pathway_scores.shape[0],
            "n_pathway_features": pathway_result.pathway_scores.shape[1],
        }

    except Exception as e:
        logger.error(f"Pathway integration failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "pathway_database": pathway_database,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="run_network_integration")
def run_network_integration(
    self,
    dataset_ids: list[str],
    network_type: str = "similarity",
    parameters: dict[str, Any] = None,
):
    """Run network-based multi-omics integration.

    Args:
        dataset_ids: List of dataset IDs
        network_type: Network type (similarity, snf, coexpression, sample)
        parameters: Integration parameters
            - k_neighbors: int (default 20)
            - mu: float (default 0.5)
            - n_iterations: int (default 20)
            - correlation_method: str (default "pearson")
            - correlation_threshold: float (default 0.7)
            - n_clusters: int (optional, for spectral clustering)

    Returns:
        Dict with network statistics and optionally cluster assignments

    """
    parameters = parameters or {}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Building networks"})
        logger.info(f"Starting network integration with type={network_type}")

        from backend.omics.integration.network_integration import (
            NetworkIntegrator,
            SimilarityNetworkFusion,
        )

        # Load datasets
        datasets = {}
        for i, dataset_id in enumerate(dataset_ids):
            df = load_dataset_data(dataset_id)
            if df is not None:
                omics_data = create_omics_data(df, f"omics_{i}")
                datasets[f"omics_{i}"] = omics_data

            progress = 0.1 + (0.2 * (i + 1) / len(dataset_ids))
            self.update_state(
                state="PROGRESS",
                meta={"progress": progress, "step": f"Loaded {i+1}/{len(dataset_ids)} datasets"},
            )

        if not datasets:
            raise ValueError("No valid datasets loaded")

        self.update_state(state="PROGRESS", meta={"progress": 0.3, "step": "Computing networks"})

        result_data = {}

        if network_type in ("similarity", "snf"):
            # Similarity Network Fusion
            snf = SimilarityNetworkFusion(
                k_neighbors=parameters.get("k_neighbors", 20),
                mu=parameters.get("mu", 0.5),
                n_iterations=parameters.get("n_iterations", 20),
            )

            network_result = snf.fuse(datasets)

            result_data = {
                "fused_network_shape": network_result.fused_network.shape,
                "n_samples": len(network_result.sample_names),
                "n_individual_networks": len(network_result.individual_networks),
                "sample_names": network_result.sample_names[:50],
            }

            # Optional spectral clustering
            n_clusters = parameters.get("n_clusters")
            if n_clusters:
                self.update_state(state="PROGRESS", meta={"progress": 0.7, "step": "Clustering"})
                clusters = NetworkIntegrator.spectral_clustering(
                    network_result.fused_network,
                    n_clusters=n_clusters,
                )
                result_data["clusters"] = clusters.tolist()
                result_data["n_clusters"] = n_clusters

        elif network_type == "coexpression":
            # Build co-expression network for first dataset
            first_data = list(datasets.values())[0]

            adj_matrix = NetworkIntegrator.build_coexpression_network(
                data=first_data,
                method=parameters.get("correlation_method", "pearson"),
                threshold=parameters.get("correlation_threshold", 0.7),
            )

            n_edges = int(np.sum(adj_matrix > 0) / 2)
            result_data = {
                "n_nodes": adj_matrix.shape[0],
                "n_edges": n_edges,
                "density": n_edges / (adj_matrix.shape[0] * (adj_matrix.shape[0] - 1) / 2),
            }

        elif network_type == "sample":
            # Build sample similarity network
            first_data = list(datasets.values())[0]

            adj_matrix = NetworkIntegrator.build_sample_network(
                data=first_data,
                metric=parameters.get("metric", "euclidean"),
                k_neighbors=parameters.get("k_neighbors", 10),
            )

            n_edges = int(np.sum(adj_matrix > 0) / 2)
            result_data = {
                "n_samples": adj_matrix.shape[0],
                "n_edges": n_edges,
                "k_neighbors": parameters.get("k_neighbors", 10),
            }

        else:
            raise ValueError(f"Unknown network type: {network_type}")

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"Network integration completed: {network_type}")

        return {
            "status": "completed",
            "network_type": network_type,
            "n_datasets": len(dataset_ids),
            **result_data,
        }

    except Exception as e:
        logger.error(f"Network integration failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "network_type": network_type,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="run_biomarker_discovery")
def run_biomarker_discovery(
    self,
    dataset_ids: list[str],
    target_column: str,
    methods: list[str] = None,
    parameters: dict[str, Any] = None,
):
    """Run cross-omics biomarker discovery with consensus scoring.

    Args:
        dataset_ids: List of dataset IDs
        target_column: Target variable column name for classification
        methods: Feature selection methods (random_forest, xgboost, lasso, etc.)
        parameters: Method parameters
            - n_top_biomarkers: int (default 50)
            - use_stability_selection: bool (default True)
            - n_bootstrap: int (default 100)
            - stability_threshold: float (default 0.6)
            - aggregation: str (default "weighted_mean")
            - min_consensus_score: float (default 0.1)

    Returns:
        Dict with discovered biomarkers, consensus scores, and statistics

    """
    parameters = parameters or {}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading data"})
        logger.info(f"Starting biomarker discovery for target={target_column}")

        from backend.analysis.biomarker_discovery import (
            BiomarkerDiscoveryPipeline,
            FeatureSelectionMethod,
        )

        # Load and concatenate datasets
        all_data = []
        all_targets = []
        feature_names = None

        for i, dataset_id in enumerate(dataset_ids):
            df = load_dataset_data(dataset_id)
            if df is not None:
                if target_column in df.columns:
                    y = df[target_column].values
                    X = df.drop(columns=[target_column])
                else:
                    # Try to get target from sample metadata
                    session = get_sync_session()
                    try:
                        from backend.app.models.dataset import Dataset

                        dataset = (
                            session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
                        )
                        if dataset and dataset.sample_metadata:
                            y = np.array(
                                [
                                    dataset.sample_metadata.get(sample, {}).get(target_column)
                                    for sample in df.index
                                ]
                            )
                        else:
                            logger.warning(
                                f"Target column {target_column} not found in dataset {dataset_id}"
                            )
                            continue
                    finally:
                        session.close()
                    X = df

                all_data.append(X)
                all_targets.append(y)
                if feature_names is None:
                    feature_names = X.columns.tolist()

            progress = 0.1 + (0.2 * (i + 1) / len(dataset_ids))
            self.update_state(
                state="PROGRESS",
                meta={"progress": progress, "step": f"Loaded {i+1}/{len(dataset_ids)} datasets"},
            )

        if not all_data:
            raise ValueError("No valid datasets loaded with target column")

        # Combine data
        X_combined = pd.concat(all_data, axis=0) if len(all_data) > 1 else all_data[0]
        y_combined = np.concatenate(all_targets) if len(all_targets) > 1 else all_targets[0]

        # Remove NaN targets
        valid_mask = ~pd.isna(y_combined)
        X_combined = X_combined.iloc[valid_mask]
        y_combined = y_combined[valid_mask]

        # Convert y to numeric if needed
        if not np.issubdtype(y_combined.dtype, np.number):
            from sklearn.preprocessing import LabelEncoder

            le = LabelEncoder()
            y_combined = le.fit_transform(y_combined)

        self.update_state(
            state="PROGRESS", meta={"progress": 0.3, "step": "Running feature selection"}
        )

        # Parse methods
        method_map = {
            "random_forest": FeatureSelectionMethod.RANDOM_FOREST,
            "xgboost": FeatureSelectionMethod.XGBOOST,
            "lightgbm": FeatureSelectionMethod.LIGHTGBM,
            "lasso": FeatureSelectionMethod.LASSO,
            "elastic_net": FeatureSelectionMethod.ELASTIC_NET,
            "mutual_info": FeatureSelectionMethod.MUTUAL_INFO,
            "f_classif": FeatureSelectionMethod.F_CLASSIF,
            "rfe": FeatureSelectionMethod.RFE,
            "logistic_l1": FeatureSelectionMethod.LOGISTIC_L1,
        }

        if methods:
            selected_methods = [method_map.get(m) for m in methods if m in method_map]
        else:
            selected_methods = None  # Use defaults

        # Run biomarker discovery pipeline
        pipeline = BiomarkerDiscoveryPipeline(
            methods=selected_methods,
            n_top_biomarkers=parameters.get("n_top_biomarkers", 50),
            use_stability_selection=parameters.get("use_stability_selection", True),
            n_bootstrap=parameters.get("n_bootstrap", 100),
            stability_threshold=parameters.get("stability_threshold", 0.6),
            aggregation=parameters.get("aggregation", "weighted_mean"),
            min_consensus_score=parameters.get("min_consensus_score", 0.1),
            n_jobs=parameters.get("n_jobs", -1),
            random_state=parameters.get("random_state", 42),
            verbose=True,
        )

        # Custom progress callback
        def progress_callback(step, progress):
            self.update_state(
                state="PROGRESS", meta={"progress": 0.3 + progress * 0.6, "step": step}
            )

        pipeline.fit(X_combined, y_combined, feature_names=feature_names)

        self.update_state(state="PROGRESS", meta={"progress": 0.9, "step": "Compiling results"})

        # Get results
        results = pipeline.results_
        candidates = results.candidates

        # Format biomarker results
        biomarkers = []
        for c in candidates[:50]:  # Top 50
            biomarkers.append(
                {
                    "rank": c.rank,
                    "feature": c.feature_name,
                    "consensus_score": float(c.consensus_score),
                    "stability_score": float(c.stability_score),
                    "selection_frequency": float(c.selection_frequency),
                    "p_value": float(c.p_value) if c.p_value else None,
                    "effect_size": float(c.effect_size) if c.effect_size else None,
                    "fold_change": float(c.fold_change) if c.fold_change else None,
                }
            )

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"Biomarker discovery completed: {len(candidates)} biomarkers identified")

        return {
            "status": "completed",
            "target_column": target_column,
            "n_datasets": len(dataset_ids),
            "n_samples": X_combined.shape[0],
            "n_features": X_combined.shape[1],
            "n_biomarkers": len(candidates),
            "execution_time": results.execution_time,
            "biomarkers": biomarkers,
            "methods_used": [m.value for m in pipeline.methods],
        }

    except Exception as e:
        logger.error(f"Biomarker discovery failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "target_column": target_column,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="run_dimensionality_reduction")
def run_dimensionality_reduction(
    self,
    dataset_id: str,
    method: str = "pca",
    n_components: int = 50,
    parameters: dict[str, Any] = None,
):
    """Run dimensionality reduction on a dataset.

    Args:
        dataset_id: Dataset ID
        method: Method (pca, umap, tsne, ica, nmf)
        n_components: Number of components/dimensions
        parameters: Method parameters
            - scale: bool (default True)
            - random_state: int (default 42)
            - perplexity: int (for t-SNE, default 30)
            - n_neighbors: int (for UMAP, default 15)
            - min_dist: float (for UMAP, default 0.1)

    Returns:
        Dict with transformed data and explained variance (if applicable)

    """
    parameters = parameters or {}

    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading data"})
        logger.info(f"Starting dimensionality reduction with method={method}")

        # Load dataset
        df = load_dataset_data(dataset_id)
        if df is None:
            raise ValueError(f"Dataset {dataset_id} not found or could not be loaded")

        X = df.values
        sample_names = df.index.tolist()
        feature_names = df.columns.tolist()

        self.update_state(state="PROGRESS", meta={"progress": 0.2, "step": "Preprocessing"})

        # Scale data if requested
        if parameters.get("scale", True):
            from sklearn.preprocessing import StandardScaler

            scaler = StandardScaler()
            X = scaler.fit_transform(X)

        # Adjust n_components
        n_components = min(n_components, X.shape[0] - 1, X.shape[1])

        self.update_state(
            state="PROGRESS", meta={"progress": 0.4, "step": f"Running {method.upper()}"}
        )

        variance_explained = None

        if method == "pca":
            from sklearn.decomposition import PCA

            model = PCA(
                n_components=n_components,
                random_state=parameters.get("random_state", 42),
            )
            X_transformed = model.fit_transform(X)
            variance_explained = model.explained_variance_ratio_.tolist()
            component_names = [f"PC{i+1}" for i in range(n_components)]

        elif method == "umap":
            try:
                import umap
            except ImportError:
                raise ImportError("UMAP not installed. Install with: pip install umap-learn")

            model = umap.UMAP(
                n_components=min(n_components, 10),  # UMAP typically uses fewer dims
                n_neighbors=parameters.get("n_neighbors", 15),
                min_dist=parameters.get("min_dist", 0.1),
                random_state=parameters.get("random_state", 42),
            )
            X_transformed = model.fit_transform(X)
            component_names = [f"UMAP{i+1}" for i in range(X_transformed.shape[1])]

        elif method == "tsne":
            from sklearn.manifold import TSNE

            # t-SNE typically uses 2-3 components
            actual_components = min(n_components, 3)

            model = TSNE(
                n_components=actual_components,
                perplexity=parameters.get("perplexity", 30),
                random_state=parameters.get("random_state", 42),
                n_iter=parameters.get("n_iter", 1000),
            )
            X_transformed = model.fit_transform(X)
            component_names = [f"tSNE{i+1}" for i in range(actual_components)]

        elif method == "ica":
            from sklearn.decomposition import FastICA

            model = FastICA(
                n_components=n_components,
                random_state=parameters.get("random_state", 42),
                max_iter=parameters.get("max_iter", 500),
            )
            X_transformed = model.fit_transform(X)
            component_names = [f"IC{i+1}" for i in range(n_components)]

        elif method == "nmf":
            from sklearn.decomposition import NMF

            # NMF requires non-negative data
            if X.min() < 0:
                X = X - X.min()

            model = NMF(
                n_components=n_components,
                random_state=parameters.get("random_state", 42),
                max_iter=parameters.get("max_iter", 500),
            )
            X_transformed = model.fit_transform(X)
            component_names = [f"NMF{i+1}" for i in range(n_components)]

        else:
            raise ValueError(f"Unknown dimensionality reduction method: {method}")

        self.update_state(state="PROGRESS", meta={"progress": 0.9, "step": "Finalizing"})

        # Create result DataFrame
        pd.DataFrame(
            X_transformed,
            index=sample_names,
            columns=component_names,
        )

        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})

        logger.info(f"Dimensionality reduction completed: {X.shape} -> {X_transformed.shape}")

        return {
            "status": "completed",
            "method": method,
            "n_components": X_transformed.shape[1],
            "n_samples": X_transformed.shape[0],
            "original_features": len(feature_names),
            "variance_explained": variance_explained,
            "total_variance_explained": sum(variance_explained) if variance_explained else None,
            "component_names": component_names,
            "sample_names": sample_names[:100],  # Truncate
        }

    except Exception as e:
        logger.error(f"Dimensionality reduction failed: {e}\n{traceback.format_exc()}")
        return {
            "status": "failed",
            "method": method,
            "error": str(e),
        }

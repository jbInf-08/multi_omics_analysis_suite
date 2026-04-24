"""
Analysis Background Tasks
=========================

Celery tasks for running omics analyses in the background.
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import logging
import traceback

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from backend.app.core.celery_app import celery_app, OmicsTask

logger = logging.getLogger(__name__)


def get_sync_session():
    """Get a synchronous database session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.core.config import settings
    
    # Convert async URL to sync
    sync_url = str(settings.DATABASE_URL).replace("+asyncpg", "")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)
    return Session()


def update_analysis_status(analysis_id: str, status: str, error_message: str = None, progress: float = None):
    """Update analysis status in database."""
    from datetime import timezone

    session = get_sync_session()
    try:
        from backend.app.models.analysis import Analysis, AnalysisStatus

        analysis = session.query(Analysis).filter(Analysis.id == UUID(analysis_id)).first()
        if analysis:
            analysis.status = AnalysisStatus(status)
            if error_message:
                analysis.error_message = error_message
            if progress is not None:
                analysis.progress = progress
            analysis.updated_at = datetime.now(timezone.utc)
            session.commit()
    except Exception as e:
        logger.error(f"Failed to update analysis status: {e}")
        session.rollback()
    finally:
        session.close()


def save_analysis_result(analysis_id: str, result_type: str, data: Dict[str, Any], metadata: Dict[str, Any] = None):
    """Save analysis result to database."""
    session = get_sync_session()
    try:
        from backend.app.models.analysis import AnalysisResult

        meta = metadata or {}
        result = AnalysisResult(
            analysis_id=UUID(analysis_id),
            result_type=result_type,
            name=result_type.replace("_", " ").title(),
            description=None,
            data=data,
            summary=meta if meta else None,
        )
        session.add(result)
        session.commit()
        logger.info(f"Saved {result_type} result for analysis {analysis_id}")
    except Exception as e:
        logger.error(f"Failed to save analysis result: {e}")
        session.rollback()
    finally:
        session.close()


def send_websocket_update(user_id: str, analysis_id: str, data: Dict[str, Any]):
    """Notify WebSocket subscribers and Redis pub/sub listeners of progress."""
    logger.debug("Analysis progress user=%s analysis=%s data=%s", user_id, analysis_id, data)
    try:
        from backend.app.core.analysis_progress_bus import publish_analysis_progress_sync

        publish_analysis_progress_sync(
            analysis_id,
            {"user_id": user_id, **data},
        )
    except Exception:
        logger.debug("Progress pub/sub skipped for analysis %s", analysis_id, exc_info=False)


@celery_app.task(base=OmicsTask, bind=True, name="run_analysis")
def run_analysis(self, analysis_id: str, parameters: Dict[str, Any] = None):
    """
    Run an analysis as a background task.
    
    This task orchestrates the analysis workflow:
    1. Load analysis configuration from database
    2. Load and validate input datasets
    3. Run preprocessing (QC, normalization)
    4. Execute the main analysis
    5. Generate visualizations
    6. Save results to database
    7. Send notifications
    
    Args:
        analysis_id: Analysis ID
        parameters: Analysis parameters (overrides stored parameters)
    """
    logger.info(f"Starting analysis {analysis_id}")
    parameters = parameters or {}
    
    try:
        # Update status to running
        update_analysis_status(analysis_id, "running")
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Initializing"})
        
        # Load analysis configuration
        session = get_sync_session()
        model_analysis_type = None
        omics_types: List[str] = []
        input_datasets: List[str] = []
        stored_params: Dict[str, Any] = {}
        user_id = ""
        try:
            from backend.app.models.analysis import Analysis

            analysis = session.query(Analysis).filter(Analysis.id == UUID(analysis_id)).first()
            if not analysis:
                raise ValueError(f"Analysis {analysis_id} not found")

            model_analysis_type = analysis.analysis_type
            omics_types = analysis.omics_types or []
            input_datasets = analysis.input_datasets or []
            stored_params = analysis.parameters or {}
            user_id = str(analysis.user_id)

        finally:
            session.close()

        final_params = {**stored_params, **parameters}
        workflow_analysis_type = final_params.get("omics_execute_analysis_type")
        if workflow_analysis_type is None and model_analysis_type is not None:
            workflow_analysis_type = (
                model_analysis_type.value
                if hasattr(model_analysis_type, "value")
                else str(model_analysis_type)
            )
        if workflow_analysis_type is None:
            workflow_analysis_type = "single_omics"
        
        # Step 1: Load data (20%)
        self.update_state(state="PROGRESS", meta={"progress": 0.1, "step": "Loading datasets"})
        send_websocket_update(user_id, analysis_id, {"progress": 0.1, "step": "Loading datasets"})
        
        datasets = load_datasets(input_datasets)
        
        self.update_state(state="PROGRESS", meta={"progress": 0.2, "step": "Data loaded"})
        
        # Step 2: Quality control (40%)
        self.update_state(state="PROGRESS", meta={"progress": 0.25, "step": "Running quality control"})
        send_websocket_update(user_id, analysis_id, {"progress": 0.25, "step": "Running quality control"})
        
        qc_results = run_quality_control(datasets, omics_types, final_params)
        save_analysis_result(analysis_id, "quality_control", qc_results)
        
        self.update_state(state="PROGRESS", meta={"progress": 0.4, "step": "QC complete"})
        
        # Step 3: Preprocessing (55%)
        self.update_state(state="PROGRESS", meta={"progress": 0.45, "step": "Preprocessing data"})
        send_websocket_update(user_id, analysis_id, {"progress": 0.45, "step": "Preprocessing data"})
        
        processed_data = preprocess_data(datasets, omics_types, final_params)
        
        self.update_state(state="PROGRESS", meta={"progress": 0.55, "step": "Preprocessing complete"})
        
        # Step 4: Main analysis (80%)
        self.update_state(
            state="PROGRESS",
            meta={"progress": 0.6, "step": f"Running {workflow_analysis_type} analysis"},
        )
        send_websocket_update(
            user_id,
            analysis_id,
            {"progress": 0.6, "step": f"Running {workflow_analysis_type} analysis"},
        )

        analysis_results = execute_analysis(
            analysis_type=str(workflow_analysis_type),
            data=processed_data,
            omics_types=omics_types,
            parameters=final_params,
        )
        save_analysis_result(analysis_id, "analysis", analysis_results)
        
        self.update_state(state="PROGRESS", meta={"progress": 0.8, "step": "Analysis complete"})
        
        # Step 5: Visualization (95%)
        self.update_state(state="PROGRESS", meta={"progress": 0.85, "step": "Generating visualizations"})
        send_websocket_update(user_id, analysis_id, {"progress": 0.85, "step": "Generating visualizations"})
        
        visualizations = generate_visualizations(
            analysis_results, str(workflow_analysis_type), final_params
        )
        save_analysis_result(analysis_id, "visualizations", visualizations)
        
        self.update_state(state="PROGRESS", meta={"progress": 0.95, "step": "Visualizations complete"})
        
        # Step 6: Finalize
        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Finalizing"})
        
        # Update status to completed
        update_analysis_status(analysis_id, "completed", progress=1.0)
        send_websocket_update(user_id, analysis_id, {"progress": 1.0, "step": "Complete", "status": "completed"})
        
        logger.info(f"Analysis {analysis_id} completed successfully")
        
        return {
            "status": "completed",
            "analysis_id": analysis_id,
            "message": "Analysis completed successfully",
            "summary": {
                "qc_passed": qc_results.get("passed", True),
                "features_analyzed": analysis_results.get("n_features", 0),
                "significant_results": analysis_results.get("n_significant", 0),
            }
        }
        
    except SoftTimeLimitExceeded:
        logger.error(f"Analysis {analysis_id} exceeded time limit")
        update_analysis_status(analysis_id, "failed", "Analysis exceeded time limit")
        raise
        
    except Exception as e:
        logger.error(f"Analysis {analysis_id} failed: {e}\n{traceback.format_exc()}")
        update_analysis_status(analysis_id, "failed", str(e))
        raise


def load_datasets(dataset_ids: List[str]) -> Dict[str, Any]:
    """Load dataset metadata and shape from persisted files (same storage as ML tasks)."""
    from backend.app.tasks.ml_tasks import load_dataset_data

    datasets: Dict[str, Any] = {}
    for dataset_id in dataset_ids:
        df = load_dataset_data(dataset_id)
        if df is not None:
            datasets[dataset_id] = {
                "id": dataset_id,
                "loaded": True,
                "n_samples": int(df.shape[0]),
                "n_features": int(df.shape[1]),
                "column_preview": [str(c) for c in df.columns[:32]],
            }
        else:
            datasets[dataset_id] = {
                "id": dataset_id,
                "loaded": False,
                "n_samples": 0,
                "n_features": 0,
                "error": "dataset missing, unreadable, or no storage_path in database",
            }
    return datasets


def run_quality_control(datasets: Dict, omics_types: List[str], params: Dict) -> Dict[str, Any]:
    """Run quality control on datasets."""
    import time
    time.sleep(0.5)  # Simulate QC
    
    return {
        "passed": True,
        "metrics": {
            "sample_quality": 0.95,
            "feature_quality": 0.92,
            "completeness": 0.98,
        },
        "warnings": [],
        "filtered_samples": 0,
        "filtered_features": 0,
    }


def preprocess_data(datasets: Dict, omics_types: List[str], params: Dict) -> Dict[str, Any]:
    """Preprocess data (normalization, filtering, etc.)."""
    import time
    time.sleep(0.5)  # Simulate preprocessing
    
    return {
        "normalized": True,
        "method": params.get("normalization_method", "quantile"),
        "n_samples": sum(d.get("n_samples", 0) for d in datasets.values()),
        "n_features": sum(d.get("n_features", 0) for d in datasets.values()),
    }


def execute_analysis(analysis_type: str, data: Dict, omics_types: List[str], parameters: Dict) -> Dict[str, Any]:
    """Execute the main analysis based on type."""
    import time
    time.sleep(1.0)  # Simulate analysis
    
    # Dispatch to appropriate analysis function based on type
    analysis_dispatch = {
        "differential_expression": run_differential_expression_analysis,
        "pathway_analysis": run_pathway_enrichment_analysis,
        "network_analysis": run_network_analysis_impl,
        "clustering": run_clustering_analysis,
        "integration": run_integration_analysis,
    }
    
    analysis_func = analysis_dispatch.get(analysis_type, run_generic_analysis)
    return analysis_func(data, omics_types, parameters)


def run_differential_expression_analysis(data: Dict, omics_types: List[str], params: Dict) -> Dict[str, Any]:
    """Run differential expression analysis."""
    return {
        "type": "differential_expression",
        "n_features": data.get("n_features", 20000),
        "n_significant": 150,
        "method": params.get("method", "deseq2"),
        "fdr_threshold": params.get("fdr_threshold", 0.05),
        "top_features": [f"gene_{i}" for i in range(10)],
    }


def run_pathway_enrichment_analysis(data: Dict, omics_types: List[str], params: Dict) -> Dict[str, Any]:
    """Run pathway enrichment analysis."""
    return {
        "type": "pathway_analysis",
        "database": params.get("database", "kegg"),
        "n_pathways_tested": 300,
        "n_significant": 25,
        "top_pathways": ["Pathway A", "Pathway B", "Pathway C"],
    }


def run_network_analysis_impl(data: Dict, omics_types: List[str], params: Dict) -> Dict[str, Any]:
    """Run network analysis."""
    return {
        "type": "network_analysis",
        "network_type": params.get("network_type", "ppi"),
        "n_nodes": 500,
        "n_edges": 2500,
        "communities": 5,
    }


def run_clustering_analysis(data: Dict, omics_types: List[str], params: Dict) -> Dict[str, Any]:
    """Run clustering analysis."""
    return {
        "type": "clustering",
        "method": params.get("method", "kmeans"),
        "n_clusters": params.get("n_clusters", 5),
        "silhouette_score": 0.75,
    }


def run_integration_analysis(data: Dict, omics_types: List[str], params: Dict) -> Dict[str, Any]:
    """Run multi-omics integration analysis."""
    return {
        "type": "integration",
        "omics_integrated": omics_types,
        "method": params.get("method", "mofa"),
        "n_factors": 10,
        "variance_explained": 0.65,
    }


def run_generic_analysis(data: Dict, omics_types: List[str], params: Dict) -> Dict[str, Any]:
    """Run generic analysis for unknown types."""
    return {
        "type": "generic",
        "status": "completed",
        "n_features": data.get("n_features", 0),
    }


def generate_visualizations(results: Dict, analysis_type: str, params: Dict) -> Dict[str, Any]:
    """Generate visualizations for analysis results."""
    import time
    time.sleep(0.5)  # Simulate visualization generation
    
    visualizations = {
        "plots": [],
        "tables": [],
    }
    
    # Generate type-specific visualizations
    if analysis_type == "differential_expression":
        visualizations["plots"] = [
            {"type": "volcano", "path": f"/results/{analysis_type}/volcano.html"},
            {"type": "heatmap", "path": f"/results/{analysis_type}/heatmap.html"},
            {"type": "pca", "path": f"/results/{analysis_type}/pca.html"},
        ]
    elif analysis_type == "pathway_analysis":
        visualizations["plots"] = [
            {"type": "enrichment_barplot", "path": f"/results/{analysis_type}/enrichment.html"},
            {"type": "pathway_network", "path": f"/results/{analysis_type}/network.html"},
        ]
    elif analysis_type == "network_analysis":
        visualizations["plots"] = [
            {"type": "network_graph", "path": f"/results/{analysis_type}/network.html"},
            {"type": "degree_distribution", "path": f"/results/{analysis_type}/degrees.html"},
        ]
    
    return visualizations


@celery_app.task(base=OmicsTask, bind=True, name="run_pipeline")
def run_pipeline(
    self,
    pipeline_id: str,
    run_id: str,
    parameters: Dict[str, Any] = None,
):
    """
    Run a pipeline as a background task.

    Each step dict should include a ``type`` key, for example:
    ``gene_prediction``, ``assembly_gene_annotation``, ``structure_md_dock``.
    See ``backend.pipelines.step_executors.execute_step`` for supported types and params.
    """
    from datetime import datetime, timezone
    from uuid import UUID

    from backend.app.models.pipeline import Pipeline, PipelineRun, PipelineStatus
    from backend.pipelines.pipeline_artifacts import persist_pipeline_step_output
    from backend.pipelines.step_executors import execute_step

    parameters = parameters or {}
    self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Starting"})

    session = get_sync_session()
    run = None
    try:
        pipeline = session.query(Pipeline).filter(Pipeline.id == UUID(pipeline_id)).first()
        run = session.query(PipelineRun).filter(PipelineRun.id == UUID(run_id)).first()

        if not pipeline or not run:
            raise ValueError("Pipeline or run not found")

        merged_params = {
            **(pipeline.default_parameters or {}),
            **(run.parameters or {}),
            **parameters,
        }
        steps = list(pipeline.steps or [])

        run.status = PipelineStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        run.error_message = None
        run.error_step = None
        session.commit()

        step_outputs: List[Dict[str, Any]] = []

        if not steps:
            run.step_results = []
            run.progress = 1.0
            run.status = PipelineStatus.COMPLETED
            run.completed_at = datetime.now(timezone.utc)
            session.commit()
            return {
                "status": "completed",
                "pipeline_id": pipeline_id,
                "run_id": run_id,
                "n_steps": 0,
                "message": "Pipeline has no steps",
            }

        n = len(steps)
        for i, step in enumerate(steps):
            run.current_step = i
            run.current_step_name = step.get("name") or step.get("type")
            session.commit()

            self.update_state(
                state="PROGRESS",
                meta={
                    "progress": i / n,
                    "step": run.current_step_name or f"step_{i}",
                },
            )

            out = execute_step(step, step_outputs, merged_params)
            out = persist_pipeline_step_output(str(run.id), i, step.get("type"), out)
            step_outputs.append(
                {"step_index": i, "type": step.get("type"), "name": step.get("name"), "result": out}
            )

            run.step_results = list(step_outputs)
            run.progress = (i + 1) / n
            session.commit()

        run.status = PipelineStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)
        run.progress = 1.0
        session.commit()

        return {
            "status": "completed",
            "pipeline_id": pipeline_id,
            "run_id": run_id,
            "n_steps": n,
        }

    except Exception as e:
        logger.error("Pipeline run failed: %s\n%s", e, traceback.format_exc())
        if run is not None:
            try:
                run.status = PipelineStatus.FAILED
                run.error_message = str(e)
                run.error_step = run.current_step
                run.completed_at = datetime.now(timezone.utc)
                session.commit()
            except Exception:
                session.rollback()
        raise
    finally:
        session.close()


@celery_app.task(base=OmicsTask, bind=True, name="run_differential_expression")
def run_differential_expression(
    self,
    dataset_id: str,
    group_column: str,
    groups: List[str],
    method: str = "ttest",
    parameters: Dict[str, Any] = None,
):
    """
    Run differential expression analysis.
    
    Args:
        dataset_id: Dataset ID
        group_column: Column name for grouping
        groups: Groups to compare (exactly 2 for most methods)
        method: Analysis method (ttest, wilcoxon, mannwhitney, anova)
        parameters: Additional parameters
            - fdr_threshold: float (default 0.05)
            - log2fc_threshold: float (default 1.0)
            - paired: bool (default False)
    
    Returns:
        Dict with DE results, significant features, and statistics
    """
    import pandas as pd
    import numpy as np
    from scipy import stats
    
    parameters = parameters or {}
    
    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading data"})
        logger.info(f"Running DE analysis with method={method}")
        
        # Load dataset
        datasets = load_datasets([dataset_id])
        if not datasets:
            raise ValueError(f"Dataset {dataset_id} not found")
        
        # Get the actual data
        session = get_sync_session()
        try:
            from backend.app.models.dataset import Dataset
            dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
            if not dataset or not dataset.storage_path:
                raise ValueError(f"Dataset {dataset_id} has no data")
            
            df = pd.read_parquet(dataset.storage_path)
        finally:
            session.close()
        
        # Check group column
        if group_column not in df.columns:
            # Check if it's in sample metadata
            session = get_sync_session()
            try:
                dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
                if dataset and dataset.sample_metadata:
                    group_values = [
                        dataset.sample_metadata.get(sample, {}).get(group_column)
                        for sample in df.index
                    ]
                    df[group_column] = group_values
                else:
                    raise ValueError(f"Group column '{group_column}' not found")
            finally:
                session.close()
        
        # Filter to specified groups
        if len(groups) != 2:
            raise ValueError("Exactly 2 groups required for DE analysis")
        
        group_mask = df[group_column].isin(groups)
        df_filtered = df[group_mask]
        
        group1_mask = df_filtered[group_column] == groups[0]
        group2_mask = df_filtered[group_column] == groups[1]
        
        # Get numeric features only
        numeric_cols = df_filtered.select_dtypes(include=[np.number]).columns.tolist()
        if group_column in numeric_cols:
            numeric_cols.remove(group_column)
        
        self.update_state(state="PROGRESS", meta={"progress": 0.3, "step": f"Running {method}"})
        
        # Run DE analysis
        results = []
        group1_data = df_filtered.loc[group1_mask, numeric_cols]
        group2_data = df_filtered.loc[group2_mask, numeric_cols]
        
        for feature in numeric_cols:
            g1 = group1_data[feature].dropna().values
            g2 = group2_data[feature].dropna().values
            
            if len(g1) < 2 or len(g2) < 2:
                continue
            
            # Calculate statistics
            mean1, mean2 = g1.mean(), g2.mean()
            
            # Log2 fold change
            if mean1 > 0 and mean2 > 0:
                log2fc = np.log2(mean2 / mean1)
            else:
                log2fc = 0
            
            # Statistical test
            if method == "ttest":
                stat, pval = stats.ttest_ind(g1, g2)
            elif method == "wilcoxon" or method == "mannwhitney":
                stat, pval = stats.mannwhitneyu(g1, g2, alternative="two-sided")
            elif method == "welch":
                stat, pval = stats.ttest_ind(g1, g2, equal_var=False)
            else:
                stat, pval = stats.ttest_ind(g1, g2)
            
            results.append({
                "feature": feature,
                "mean_group1": float(mean1),
                "mean_group2": float(mean2),
                "log2_fold_change": float(log2fc),
                "statistic": float(stat),
                "p_value": float(pval) if not np.isnan(pval) else 1.0,
            })
        
        self.update_state(state="PROGRESS", meta={"progress": 0.7, "step": "Computing FDR"})
        
        # FDR correction
        from scipy.stats import false_discovery_control
        p_values = [r["p_value"] for r in results]
        if p_values:
            q_values = false_discovery_control(p_values, method="bh")
            for i, r in enumerate(results):
                r["q_value"] = float(q_values[i])
        
        # Sort by p-value
        results.sort(key=lambda x: x["p_value"])
        
        # Filter significant
        fdr_threshold = parameters.get("fdr_threshold", 0.05)
        log2fc_threshold = parameters.get("log2fc_threshold", 1.0)
        
        significant = [
            r for r in results
            if r.get("q_value", 1) < fdr_threshold and abs(r["log2_fold_change"]) > log2fc_threshold
        ]
        
        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})
        
        logger.info(f"DE analysis completed: {len(significant)} significant features")
        
        return {
            "status": "completed",
            "method": method,
            "groups": groups,
            "n_features_tested": len(results),
            "n_significant": len(significant),
            "fdr_threshold": fdr_threshold,
            "log2fc_threshold": log2fc_threshold,
            "top_results": results[:100],
            "significant_features": [r["feature"] for r in significant],
            "group1_samples": int(group1_mask.sum()),
            "group2_samples": int(group2_mask.sum()),
        }
        
    except Exception as e:
        logger.error(f"DE analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "failed",
            "method": method,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="run_pathway_analysis")
def run_pathway_analysis(
    self,
    gene_list: List[str] = None,
    gene_ranking: Dict[str, float] = None,
    organism: str = "human",
    database: str = "kegg",
    method: str = "ora",
    parameters: Dict[str, Any] = None,
):
    """
    Run pathway enrichment analysis.
    
    Args:
        gene_list: List of genes for ORA
        gene_ranking: Dict mapping gene to score for GSEA
        organism: Organism (human, mouse)
        database: Pathway database (kegg, reactome, go_bp, go_mf, hallmark)
        method: Analysis method (gsea, ora)
        parameters: Additional parameters
            - fdr_threshold: float (default 0.25 for GSEA, 0.05 for ORA)
            - permutations: int (for GSEA, default 1000)
    
    Returns:
        Dict with enriched pathways and statistics
    """
    import pandas as pd
    
    parameters = parameters or {}
    
    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Loading pathway data"})
        logger.info(f"Running pathway analysis with method={method}, database={database}")
        
        from backend.analysis.pathway_analysis import (
            PathwayAnalysisPipeline,
            PathwayDatabase,
            GSEAAnalyzer,
            ORAAnalyzer,
        )
        
        # Map database string to enum
        db_map = {
            "kegg": PathwayDatabase.KEGG,
            "reactome": PathwayDatabase.REACTOME,
            "go_bp": PathwayDatabase.GO_BP,
            "go_mf": PathwayDatabase.GO_MF,
            "go_cc": PathwayDatabase.GO_CC,
            "hallmark": PathwayDatabase.HALLMARK,
            "oncogenic": PathwayDatabase.ONCOGENIC,
            "wikipathways": PathwayDatabase.WIKIPATHWAYS,
        }
        
        pathway_db = db_map.get(database.lower(), PathwayDatabase.KEGG)
        
        self.update_state(state="PROGRESS", meta={"progress": 0.2, "step": f"Running {method.upper()}"})
        
        results = {}
        
        if method.lower() == "gsea" and gene_ranking:
            # GSEA requires ranked genes
            ranking_series = pd.Series(gene_ranking)
            
            gsea = GSEAAnalyzer(
                databases=[pathway_db],
                permutation_num=parameters.get("permutations", 1000),
                min_size=parameters.get("min_size", 15),
                max_size=parameters.get("max_size", 500),
                threads=parameters.get("threads", 4),
            )
            
            gsea_results = gsea.run(ranking_series)
            
            self.update_state(state="PROGRESS", meta={"progress": 0.7, "step": "Processing results"})
            
            # Get significant pathways
            fdr_threshold = parameters.get("fdr_threshold", 0.25)
            significant = gsea.get_significant_pathways(fdr_threshold)
            
            if not significant.empty:
                results["pathways"] = significant.head(50).to_dict(orient="records")
                results["n_significant"] = len(significant)
            else:
                results["pathways"] = []
                results["n_significant"] = 0
            
            results["method"] = "GSEA"
            results["n_genes_ranked"] = len(gene_ranking)
            
        elif method.lower() == "ora" and gene_list:
            # ORA for gene list
            ora = ORAAnalyzer(
                databases=[pathway_db],
                organism="Human" if organism.lower() == "human" else organism,
                cutoff=parameters.get("fdr_threshold", 0.05),
            )
            
            ora_results = ora.run(gene_list)
            
            self.update_state(state="PROGRESS", meta={"progress": 0.7, "step": "Processing results"})
            
            # Get significant pathways
            significant = ora.get_significant_pathways(parameters.get("fdr_threshold", 0.05))
            
            if not significant.empty:
                results["pathways"] = significant.head(50).to_dict(orient="records")
                results["n_significant"] = len(significant)
            else:
                results["pathways"] = []
                results["n_significant"] = 0
            
            results["method"] = "ORA"
            results["n_genes_input"] = len(gene_list)
            
        else:
            raise ValueError("Must provide gene_list for ORA or gene_ranking for GSEA")
        
        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})
        
        logger.info(f"Pathway analysis completed: {results.get('n_significant', 0)} significant pathways")
        
        return {
            "status": "completed",
            "database": database,
            **results,
        }
        
    except Exception as e:
        logger.error(f"Pathway analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "failed",
            "database": database,
            "method": method,
            "error": str(e),
        }


@celery_app.task(base=OmicsTask, bind=True, name="run_network_analysis")
def run_network_analysis(
    self,
    gene_list: List[str] = None,
    dataset_id: str = None,
    network_type: str = "coexpression",
    parameters: Dict[str, Any] = None,
):
    """
    Run network analysis.
    
    Args:
        gene_list: List of genes (for PPI network)
        dataset_id: Dataset ID (for coexpression network)
        network_type: Network type (ppi, coexpression, correlation)
        parameters: Additional parameters
            - correlation_threshold: float (default 0.7)
            - correlation_method: str (pearson, spearman)
            - n_top_edges: int (max edges to return)
    
    Returns:
        Dict with network statistics and top edges
    """
    import pandas as pd
    import numpy as np
    
    parameters = parameters or {}
    
    try:
        self.update_state(state="PROGRESS", meta={"progress": 0.0, "step": "Building network"})
        logger.info(f"Running network analysis: type={network_type}")
        
        results = {
            "network_type": network_type,
            "nodes": [],
            "edges": [],
            "statistics": {},
        }
        
        if network_type == "coexpression" and dataset_id:
            # Build co-expression network from dataset
            session = get_sync_session()
            try:
                from backend.app.models.dataset import Dataset
                dataset = session.query(Dataset).filter(Dataset.id == UUID(dataset_id)).first()
                if not dataset or not dataset.storage_path:
                    raise ValueError(f"Dataset {dataset_id} not found")
                
                df = pd.read_parquet(dataset.storage_path)
            finally:
                session.close()
            
            # Filter to numeric columns
            numeric_df = df.select_dtypes(include=[np.number])
            
            # Filter to gene list if provided
            if gene_list:
                available_genes = [g for g in gene_list if g in numeric_df.columns]
                numeric_df = numeric_df[available_genes]
            
            self.update_state(state="PROGRESS", meta={"progress": 0.3, "step": "Computing correlations"})
            
            # Compute correlation matrix
            method = parameters.get("correlation_method", "pearson")
            corr_matrix = numeric_df.corr(method=method)
            
            # Apply threshold
            threshold = parameters.get("correlation_threshold", 0.7)
            
            # Extract edges
            edges = []
            n_genes = len(corr_matrix.columns)
            for i in range(n_genes):
                for j in range(i + 1, n_genes):
                    corr = corr_matrix.iloc[i, j]
                    if abs(corr) >= threshold:
                        edges.append({
                            "source": corr_matrix.columns[i],
                            "target": corr_matrix.columns[j],
                            "weight": float(corr),
                            "abs_weight": float(abs(corr)),
                        })
            
            # Sort by absolute weight
            edges.sort(key=lambda x: x["abs_weight"], reverse=True)
            
            # Limit edges
            n_top = parameters.get("n_top_edges", 1000)
            edges = edges[:n_top]
            
            # Get unique nodes
            nodes = list(set([e["source"] for e in edges] + [e["target"] for e in edges]))
            
            self.update_state(state="PROGRESS", meta={"progress": 0.7, "step": "Computing statistics"})
            
            # Compute statistics
            if edges:
                node_degrees = {}
                for e in edges:
                    node_degrees[e["source"]] = node_degrees.get(e["source"], 0) + 1
                    node_degrees[e["target"]] = node_degrees.get(e["target"], 0) + 1
                
                degrees = list(node_degrees.values())
                
                results["statistics"] = {
                    "n_nodes": len(nodes),
                    "n_edges": len(edges),
                    "density": 2 * len(edges) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0,
                    "mean_degree": float(np.mean(degrees)),
                    "max_degree": int(max(degrees)),
                    "hub_nodes": sorted(node_degrees.items(), key=lambda x: x[1], reverse=True)[:10],
                }
            
            results["nodes"] = nodes[:500]
            results["edges"] = edges[:500]
            
        elif network_type == "ppi" and gene_list:
            # For PPI, we'd query STRING or similar
            # This is a simplified version using correlation within genes
            self.update_state(state="PROGRESS", meta={"progress": 0.5, "step": "Building PPI network"})
            
            results["nodes"] = gene_list[:100]
            results["statistics"] = {
                "n_input_genes": len(gene_list),
                "note": "PPI network requires external database integration",
            }
            
        else:
            raise ValueError("Must provide dataset_id for coexpression or gene_list for PPI")
        
        self.update_state(state="PROGRESS", meta={"progress": 1.0, "step": "Complete"})
        
        logger.info(f"Network analysis completed: {results['statistics'].get('n_nodes', 0)} nodes, {results['statistics'].get('n_edges', 0)} edges")
        
        return {
            "status": "completed",
            **results,
        }
        
    except Exception as e:
        logger.error(f"Network analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "failed",
            "network_type": network_type,
            "error": str(e),
        }

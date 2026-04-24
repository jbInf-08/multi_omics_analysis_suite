"""
Pathway Analysis Module
=======================

Comprehensive pathway analysis including:
- Gene Set Enrichment Analysis (GSEA)
- Over-Representation Analysis (ORA)
- KEGG, Reactome, GO pathway databases
- Leading edge analysis
- Network-based pathway analysis
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
import gseapy as gp
from gseapy import Biomart
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)


class PathwayDatabase(str, Enum):
    """Available pathway databases."""
    KEGG = "KEGG_2021_Human"
    REACTOME = "Reactome_2022"
    GO_BP = "GO_Biological_Process_2021"
    GO_MF = "GO_Molecular_Function_2021"
    GO_CC = "GO_Cellular_Component_2021"
    WIKIPATHWAYS = "WikiPathways_2019_Human"
    BIOCARTA = "BioCarta_2016"
    HALLMARK = "MSigDB_Hallmark_2020"
    ONCOGENIC = "MSigDB_Oncogenic_Signatures"
    IMMUNESIGDB = "MSigDB_ImmuneSigDB"
    PANTHER = "Panther_2016"
    DRUGBANK = "DrugBank_2020"
    DISEASE = "DisGeNET"


@dataclass
class PathwayResult:
    """Result for a single pathway."""
    pathway_name: str
    database: str
    enrichment_score: float
    normalized_score: Optional[float]
    p_value: float
    adjusted_p_value: float
    fdr: float
    n_genes: int
    n_overlap: int
    genes: List[str]
    leading_edge: Optional[List[str]] = None
    is_significant: bool = False
    direction: Optional[str] = None  # "activated" or "suppressed"


@dataclass
class GSEAResult:
    """Results from GSEA analysis."""
    term: str
    es: float
    nes: float
    p_value: float
    fdr: float
    gene_set_size: int
    matched_size: int
    genes: List[str]
    leading_edge_genes: List[str]
    leading_edge_number: int


@dataclass
class ORAResult:
    """Results from ORA analysis."""
    term: str
    overlap: int
    gene_set_size: int
    p_value: float
    adjusted_p_value: float
    odds_ratio: float
    combined_score: float
    genes: List[str]


@dataclass
class PathwayAnalysisResult:
    """Comprehensive pathway analysis results."""
    gsea_results: Optional[pd.DataFrame]
    ora_results: Optional[pd.DataFrame]
    significant_pathways: List[str]
    top_activated: List[PathwayResult]
    top_suppressed: List[PathwayResult]
    databases_used: List[str]
    n_pathways_tested: int
    n_significant: int
    parameters: Dict[str, Any]


class GSEAAnalyzer:
    """
    Gene Set Enrichment Analysis (GSEA).
    
    Implements the Subramanian et al. GSEA algorithm
    for identifying enriched pathways in ranked gene lists.
    """
    
    def __init__(
        self,
        databases: Optional[List[PathwayDatabase]] = None,
        permutation_num: int = 1000,
        min_size: int = 15,
        max_size: int = 500,
        seed: int = 42,
        threads: int = 4,
        verbose: bool = True,
    ):
        """
        Initialize GSEA analyzer.
        
        Args:
            databases: Pathway databases to use
            permutation_num: Number of permutations
            min_size: Minimum gene set size
            max_size: Maximum gene set size
            seed: Random seed
            threads: Number of threads
            verbose: Verbosity flag
        """
        self.databases = databases or [
            PathwayDatabase.KEGG,
            PathwayDatabase.REACTOME,
            PathwayDatabase.GO_BP,
            PathwayDatabase.HALLMARK,
        ]
        self.permutation_num = permutation_num
        self.min_size = min_size
        self.max_size = max_size
        self.seed = seed
        self.threads = threads
        self.verbose = verbose
        
        self.results_: Optional[Dict[str, pd.DataFrame]] = None
    
    def run(
        self,
        gene_ranking: pd.Series,
        custom_gene_sets: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Run GSEA on ranked gene list.
        
        Args:
            gene_ranking: Series with gene names as index and ranking metric as values
            custom_gene_sets: Optional custom gene sets
            
        Returns:
            Dictionary of results per database
        """
        if self.verbose:
            logger.info(f"Running GSEA on {len(gene_ranking)} genes")
        
        # Prepare ranking
        rnk = gene_ranking.reset_index()
        rnk.columns = ["gene", "score"]
        rnk = rnk.sort_values("score", ascending=False)
        
        self.results_ = {}
        
        for database in self.databases:
            try:
                if self.verbose:
                    logger.info(f"Running GSEA with {database.value}")
                
                result = gp.prerank(
                    rnk=rnk,
                    gene_sets=database.value,
                    threads=self.threads,
                    min_size=self.min_size,
                    max_size=self.max_size,
                    permutation_num=self.permutation_num,
                    seed=self.seed,
                    verbose=False,
                )
                
                self.results_[database.value] = result.res2d
                
            except Exception as e:
                logger.warning(f"GSEA failed for {database.value}: {e}")
        
        # Custom gene sets
        if custom_gene_sets:
            try:
                result = gp.prerank(
                    rnk=rnk,
                    gene_sets=custom_gene_sets,
                    threads=self.threads,
                    min_size=self.min_size,
                    max_size=self.max_size,
                    permutation_num=self.permutation_num,
                    seed=self.seed,
                    verbose=False,
                )
                self.results_["Custom"] = result.res2d
            except Exception as e:
                logger.warning(f"GSEA failed for custom gene sets: {e}")
        
        return self.results_
    
    def run_from_expression(
        self,
        expression_data: pd.DataFrame,
        class_labels: pd.Series,
        gene_sets: Optional[Union[str, Dict[str, List[str]]]] = None,
        method: str = "signal_to_noise",
    ) -> Dict[str, pd.DataFrame]:
        """
        Run GSEA directly from expression data.
        
        Args:
            expression_data: Gene expression matrix (genes x samples)
            class_labels: Class labels for samples
            gene_sets: Gene sets to use
            method: Ranking method
            
        Returns:
            Dictionary of results
        """
        if self.verbose:
            logger.info(f"Running GSEA from expression data")
        
        self.results_ = {}
        
        gene_sets_to_use = gene_sets or self.databases[0].value
        
        try:
            result = gp.gsea(
                data=expression_data,
                gene_sets=gene_sets_to_use if isinstance(gene_sets_to_use, (str, dict)) 
                         else gene_sets_to_use.value,
                cls=class_labels.tolist(),
                method=method,
                threads=self.threads,
                min_size=self.min_size,
                max_size=self.max_size,
                permutation_num=self.permutation_num,
                seed=self.seed,
                verbose=False,
            )
            
            db_name = gene_sets_to_use if isinstance(gene_sets_to_use, str) else "custom"
            self.results_[db_name] = result.res2d
            
        except Exception as e:
            logger.warning(f"GSEA from expression failed: {e}")
        
        return self.results_
    
    def get_significant_pathways(
        self, fdr_threshold: float = 0.25
    ) -> pd.DataFrame:
        """Get significantly enriched pathways."""
        if self.results_ is None:
            raise ValueError("GSEA not run")
        
        all_results = []
        for db_name, results in self.results_.items():
            df = results.copy()
            df["database"] = db_name
            all_results.append(df)
        
        combined = pd.concat(all_results, ignore_index=True)
        significant = combined[combined["FDR q-val"] < fdr_threshold]
        
        return significant.sort_values("NES", ascending=False)
    
    def get_leading_edge_genes(
        self, pathway_name: str, database: Optional[str] = None
    ) -> List[str]:
        """Get leading edge genes for a pathway."""
        if self.results_ is None:
            raise ValueError("GSEA not run")
        
        for db_name, results in self.results_.items():
            if database and db_name != database:
                continue
            
            if pathway_name in results.index:
                row = results.loc[pathway_name]
                genes = row.get("Lead_genes", "")
                if genes:
                    return genes.split(";")
        
        return []


class ORAAnalyzer:
    """
    Over-Representation Analysis (ORA).
    
    Tests for enrichment of gene sets in a gene list
    using hypergeometric test.
    """
    
    def __init__(
        self,
        databases: Optional[List[PathwayDatabase]] = None,
        background: Optional[List[str]] = None,
        organism: str = "Human",
        cutoff: float = 0.05,
        verbose: bool = True,
    ):
        """
        Initialize ORA analyzer.
        
        Args:
            databases: Pathway databases to use
            background: Background gene list (None for all genes)
            organism: Organism name
            cutoff: Significance cutoff
            verbose: Verbosity flag
        """
        self.databases = databases or [
            PathwayDatabase.KEGG,
            PathwayDatabase.REACTOME,
            PathwayDatabase.GO_BP,
        ]
        self.background = background
        self.organism = organism
        self.cutoff = cutoff
        self.verbose = verbose
        
        self.results_: Optional[Dict[str, pd.DataFrame]] = None
    
    def run(
        self,
        gene_list: List[str],
        custom_gene_sets: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        Run ORA on gene list.
        
        Args:
            gene_list: List of genes to test
            custom_gene_sets: Optional custom gene sets
            
        Returns:
            Dictionary of results per database
        """
        if self.verbose:
            logger.info(f"Running ORA on {len(gene_list)} genes")
        
        self.results_ = {}
        
        for database in self.databases:
            try:
                if self.verbose:
                    logger.info(f"Running ORA with {database.value}")
                
                result = gp.enrichr(
                    gene_list=gene_list,
                    gene_sets=database.value,
                    organism=self.organism,
                    background=self.background,
                    cutoff=self.cutoff,
                    verbose=False,
                )
                
                self.results_[database.value] = result.results
                
            except Exception as e:
                logger.warning(f"ORA failed for {database.value}: {e}")
        
        # Custom gene sets
        if custom_gene_sets:
            try:
                result = gp.enrichr(
                    gene_list=gene_list,
                    gene_sets=custom_gene_sets,
                    background=self.background,
                    cutoff=self.cutoff,
                    verbose=False,
                )
                self.results_["Custom"] = result.results
            except Exception as e:
                logger.warning(f"ORA failed for custom gene sets: {e}")
        
        return self.results_
    
    def get_significant_pathways(
        self, p_value_threshold: float = 0.05
    ) -> pd.DataFrame:
        """Get significantly enriched pathways."""
        if self.results_ is None:
            raise ValueError("ORA not run")
        
        all_results = []
        for db_name, results in self.results_.items():
            df = results.copy()
            df["database"] = db_name
            all_results.append(df)
        
        combined = pd.concat(all_results, ignore_index=True)
        significant = combined[combined["Adjusted P-value"] < p_value_threshold]
        
        return significant.sort_values("Combined Score", ascending=False)
    
    def get_genes_in_pathway(self, pathway_name: str) -> List[str]:
        """Get genes overlapping with a pathway."""
        if self.results_ is None:
            raise ValueError("ORA not run")
        
        for db_name, results in self.results_.items():
            if "Term" in results.columns:
                match = results[results["Term"] == pathway_name]
                if not match.empty:
                    genes = match.iloc[0].get("Genes", "")
                    if genes:
                        return genes.split(";")
        
        return []


class PathwayAnalysisPipeline:
    """
    Comprehensive pathway analysis pipeline.
    
    Integrates GSEA and ORA with multiple databases
    for robust pathway identification.
    """
    
    def __init__(
        self,
        # Analysis options
        run_gsea: bool = True,
        run_ora: bool = True,
        
        # Database options
        databases: Optional[List[PathwayDatabase]] = None,
        
        # GSEA parameters
        gsea_permutations: int = 1000,
        gsea_min_size: int = 15,
        gsea_max_size: int = 500,
        
        # Significance thresholds
        gsea_fdr_threshold: float = 0.25,
        ora_pvalue_threshold: float = 0.05,
        
        # Execution
        threads: int = 4,
        verbose: bool = True,
    ):
        """
        Initialize pathway analysis pipeline.
        
        Args:
            run_gsea: Run GSEA analysis
            run_ora: Run ORA analysis
            databases: Pathway databases to use
            gsea_permutations: Number of GSEA permutations
            gsea_min_size: Minimum gene set size
            gsea_max_size: Maximum gene set size
            gsea_fdr_threshold: FDR threshold for GSEA
            ora_pvalue_threshold: P-value threshold for ORA
            threads: Number of threads
            verbose: Verbosity flag
        """
        self.run_gsea = run_gsea
        self.run_ora = run_ora
        self.databases = databases or [
            PathwayDatabase.KEGG,
            PathwayDatabase.REACTOME,
            PathwayDatabase.GO_BP,
            PathwayDatabase.HALLMARK,
        ]
        self.gsea_permutations = gsea_permutations
        self.gsea_min_size = gsea_min_size
        self.gsea_max_size = gsea_max_size
        self.gsea_fdr_threshold = gsea_fdr_threshold
        self.ora_pvalue_threshold = ora_pvalue_threshold
        self.threads = threads
        self.verbose = verbose
        
        self.results_: Optional[PathwayAnalysisResult] = None
    
    def analyze(
        self,
        # For GSEA
        gene_ranking: Optional[pd.Series] = None,
        # For ORA
        gene_list: Optional[List[str]] = None,
        # Background genes for ORA
        background: Optional[List[str]] = None,
        # Custom gene sets
        custom_gene_sets: Optional[Dict[str, List[str]]] = None,
    ) -> PathwayAnalysisResult:
        """
        Run comprehensive pathway analysis.
        
        Args:
            gene_ranking: Ranked gene list for GSEA (Series with gene names as index)
            gene_list: Gene list for ORA
            background: Background genes for ORA
            custom_gene_sets: Custom gene sets
            
        Returns:
            PathwayAnalysisResult
        """
        if self.verbose:
            logger.info("Starting pathway analysis")
        
        gsea_results = None
        ora_results = None
        
        # Run GSEA
        if self.run_gsea and gene_ranking is not None:
            gsea = GSEAAnalyzer(
                databases=self.databases,
                permutation_num=self.gsea_permutations,
                min_size=self.gsea_min_size,
                max_size=self.gsea_max_size,
                threads=self.threads,
                verbose=self.verbose,
            )
            gsea.run(gene_ranking, custom_gene_sets)
            gsea_results = gsea.get_significant_pathways(self.gsea_fdr_threshold)
        
        # Run ORA
        if self.run_ora and gene_list is not None:
            ora = ORAAnalyzer(
                databases=self.databases,
                background=background,
                verbose=self.verbose,
            )
            ora.run(gene_list, custom_gene_sets)
            ora_results = ora.get_significant_pathways(self.ora_pvalue_threshold)
        
        # Compile significant pathways
        significant_pathways = set()
        if gsea_results is not None and not gsea_results.empty:
            significant_pathways.update(gsea_results["Term"].tolist())
        if ora_results is not None and not ora_results.empty:
            significant_pathways.update(ora_results["Term"].tolist())
        
        # Get top activated/suppressed
        top_activated = []
        top_suppressed = []
        
        if gsea_results is not None and not gsea_results.empty:
            for _, row in gsea_results.head(20).iterrows():
                result = PathwayResult(
                    pathway_name=row["Term"],
                    database=row.get("database", "unknown"),
                    enrichment_score=row.get("ES", 0),
                    normalized_score=row.get("NES", 0),
                    p_value=row.get("NOM p-val", 1),
                    adjusted_p_value=row.get("FDR q-val", 1),
                    fdr=row.get("FDR q-val", 1),
                    n_genes=int(row.get("Gene Set Size", 0)),
                    n_overlap=int(row.get("Matched Size", 0)),
                    genes=row.get("Lead_genes", "").split(";") if row.get("Lead_genes") else [],
                    is_significant=row.get("FDR q-val", 1) < self.gsea_fdr_threshold,
                    direction="activated" if row.get("NES", 0) > 0 else "suppressed",
                )
                if result.direction == "activated":
                    top_activated.append(result)
                else:
                    top_suppressed.append(result)
        
        # Count pathways tested
        n_pathways_tested = 0
        if gsea_results is not None:
            n_pathways_tested += len(gsea_results)
        if ora_results is not None:
            n_pathways_tested += len(ora_results)
        
        self.results_ = PathwayAnalysisResult(
            gsea_results=gsea_results,
            ora_results=ora_results,
            significant_pathways=list(significant_pathways),
            top_activated=top_activated[:10],
            top_suppressed=top_suppressed[:10],
            databases_used=[db.value for db in self.databases],
            n_pathways_tested=n_pathways_tested,
            n_significant=len(significant_pathways),
            parameters={
                "gsea_permutations": self.gsea_permutations,
                "gsea_fdr_threshold": self.gsea_fdr_threshold,
                "ora_pvalue_threshold": self.ora_pvalue_threshold,
            }
        )
        
        if self.verbose:
            logger.info(f"Pathway analysis complete: {len(significant_pathways)} significant pathways")
        
        return self.results_
    
    def get_combined_results(self) -> pd.DataFrame:
        """Get combined results from all analyses."""
        if self.results_ is None:
            raise ValueError("Analysis not run")
        
        dfs = []
        
        if self.results_.gsea_results is not None:
            df = self.results_.gsea_results.copy()
            df["method"] = "GSEA"
            dfs.append(df)
        
        if self.results_.ora_results is not None:
            df = self.results_.ora_results.copy()
            df["method"] = "ORA"
            dfs.append(df)
        
        if not dfs:
            return pd.DataFrame()
        
        return pd.concat(dfs, ignore_index=True)


def create_gene_ranking_from_de(
    de_results: pd.DataFrame,
    gene_col: str = "feature",
    stat_col: str = "statistic",
    pvalue_col: str = "p_value",
    logfc_col: str = "log2_fold_change",
    ranking_method: str = "signed_pvalue",
) -> pd.Series:
    """
    Create gene ranking from differential expression results.
    
    Args:
        de_results: Differential expression results DataFrame
        gene_col: Gene column name
        stat_col: Test statistic column name
        pvalue_col: P-value column name
        logfc_col: Log fold change column name
        ranking_method: Method for ranking
            - 'signed_pvalue': sign(logFC) * -log10(p)
            - 'statistic': Use test statistic directly
            - 'logfc': Use log fold change
            
    Returns:
        Series with gene names as index and ranking metric as values
    """
    df = de_results.copy()
    
    if ranking_method == "signed_pvalue":
        df["ranking"] = np.sign(df[logfc_col]) * (-np.log10(df[pvalue_col].clip(lower=1e-300)))
    elif ranking_method == "statistic":
        df["ranking"] = df[stat_col]
    elif ranking_method == "logfc":
        df["ranking"] = df[logfc_col]
    else:
        raise ValueError(f"Unknown ranking method: {ranking_method}")
    
    # Remove NaN values
    df = df.dropna(subset=["ranking"])
    
    # Create series
    ranking = pd.Series(df["ranking"].values, index=df[gene_col].values)
    ranking = ranking.sort_values(ascending=False)
    
    return ranking


def get_pathway_genes(
    pathway_name: str,
    database: PathwayDatabase = PathwayDatabase.KEGG,
) -> List[str]:
    """
    Get genes belonging to a pathway.
    
    Args:
        pathway_name: Name of the pathway
        database: Pathway database
        
    Returns:
        List of gene symbols
    """
    try:
        gene_sets = gp.get_library(database.value)
        if pathway_name in gene_sets:
            return gene_sets[pathway_name]
    except Exception as e:
        logger.warning(f"Could not get pathway genes: {e}")
    
    return []


def pathway_crosstalk_analysis(
    pathway_results: pd.DataFrame,
    gene_col: str = "genes",
    min_overlap: int = 3,
) -> pd.DataFrame:
    """
    Analyze crosstalk between significant pathways.
    
    Args:
        pathway_results: DataFrame with pathway results
        gene_col: Column containing gene lists
        min_overlap: Minimum gene overlap
        
    Returns:
        DataFrame with pathway pairs and overlap statistics
    """
    pathways = pathway_results["Term"].tolist()
    gene_lists = []
    
    for _, row in pathway_results.iterrows():
        genes = row.get(gene_col, "")
        if isinstance(genes, str):
            genes = genes.split(";") if genes else []
        gene_lists.append(set(genes))
    
    crosstalk = []
    for i in range(len(pathways)):
        for j in range(i + 1, len(pathways)):
            overlap = gene_lists[i] & gene_lists[j]
            if len(overlap) >= min_overlap:
                crosstalk.append({
                    "pathway_1": pathways[i],
                    "pathway_2": pathways[j],
                    "overlap_count": len(overlap),
                    "overlap_genes": ";".join(overlap),
                    "jaccard_index": len(overlap) / len(gene_lists[i] | gene_lists[j]),
                })
    
    return pd.DataFrame(crosstalk).sort_values("overlap_count", ascending=False)

"""R Integration Module.
====================

Integration with R statistical packages:
- DESeq2 for differential expression
- edgeR for RNA-seq analysis
- limma for microarray and RNA-seq
- Seurat for single-cell analysis
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Try to import rpy2
try:
    import rpy2.robjects as ro
    from rpy2.robjects import numpy2ri, pandas2ri
    from rpy2.robjects.conversion import localconverter
    from rpy2.robjects.packages import importr

    pandas2ri.activate()
    numpy2ri.activate()
    R_AVAILABLE = True
except ImportError:
    R_AVAILABLE = False
    logger.warning("rpy2 not available. R integration disabled.")


class RPackage(str, Enum):
    """Available R packages."""

    DESEQ2 = "DESeq2"
    EDGER = "edgeR"
    LIMMA = "limma"
    SEURAT = "Seurat"


@dataclass
class DEResult:
    """Differential expression result."""

    gene: str
    base_mean: float
    log2_fold_change: float
    lfc_se: float
    stat: float
    p_value: float
    adjusted_p_value: float
    is_significant: bool


@dataclass
class DEAnalysisResult:
    """Complete differential expression analysis result."""

    results: pd.DataFrame
    significant_genes: list[str]
    upregulated: list[str]
    downregulated: list[str]
    n_tested: int
    n_significant: int
    method: str
    parameters: dict[str, Any]


class RIntegrationManager:
    """Manager for R package integration.

    Handles R environment setup, package loading,
    and data conversion between Python and R.
    """

    def __init__(self):
        """Initialize R integration manager."""
        self.r_available = R_AVAILABLE
        self._loaded_packages: dict[str, Any] = {}

        if self.r_available:
            self._setup_r_environment()

    def _setup_r_environment(self):
        """Setup R environment and load base packages."""
        try:
            self.base = importr("base")
            self.stats = importr("stats")
            self.utils = importr("utils")
            logger.info("R environment initialized successfully")
        except Exception as e:
            logger.error(f"Failed to setup R environment: {e}")
            self.r_available = False

    def load_package(self, package: str | RPackage) -> Any | None:
        """Load an R package.

        Args:
            package: Package name or RPackage enum

        Returns:
            Loaded R package or None

        """
        if not self.r_available:
            logger.warning("R not available")
            return None

        package_name = package.value if isinstance(package, RPackage) else package

        if package_name in self._loaded_packages:
            return self._loaded_packages[package_name]

        try:
            pkg = importr(package_name)
            self._loaded_packages[package_name] = pkg
            logger.info(f"Loaded R package: {package_name}")
            return pkg
        except Exception as e:
            logger.error(f"Failed to load R package {package_name}: {e}")
            return None

    def install_package(self, package: str, bioconductor: bool = False) -> bool:
        """Install an R package.

        Args:
            package: Package name
            bioconductor: Whether to use Bioconductor

        Returns:
            Success status

        """
        if not self.r_available:
            return False

        try:
            if bioconductor:
                ro.r(f"""
                    if (!requireNamespace("BiocManager", quietly = TRUE))
                        install.packages("BiocManager")
                    BiocManager::install("{package}")
                """)
            else:
                self.utils.install_packages(package)
            return True
        except Exception as e:
            logger.error(f"Failed to install {package}: {e}")
            return False

    def check_package(self, package: str) -> bool:
        """Check if an R package is installed."""
        if not self.r_available:
            return False

        try:
            result = ro.r(f'requireNamespace("{package}", quietly = TRUE)')
            return bool(result[0])
        except:
            return False

    def df_to_r(self, df: pd.DataFrame) -> Any:
        """Convert pandas DataFrame to R data.frame."""
        if not self.r_available:
            raise RuntimeError("R not available")

        with localconverter(ro.default_converter + pandas2ri.converter):
            return ro.conversion.py2rpy(df)

    def r_to_df(self, r_obj: Any) -> pd.DataFrame:
        """Convert R data.frame to pandas DataFrame."""
        if not self.r_available:
            raise RuntimeError("R not available")

        with localconverter(ro.default_converter + pandas2ri.converter):
            return ro.conversion.rpy2py(r_obj)


class DESeq2Analyzer:
    """DESeq2 differential expression analysis.

    Implements negative binomial GLM-based differential
    expression analysis for RNA-seq count data.
    """

    def __init__(
        self,
        alpha: float = 0.05,
        lfc_threshold: float = 0.0,
        independent_filtering: bool = True,
        shrinkage: str = "apeglm",
    ):
        """Initialize DESeq2 analyzer.

        Args:
            alpha: Significance level
            lfc_threshold: Log fold change threshold
            independent_filtering: Use independent filtering
            shrinkage: LFC shrinkage method ('apeglm', 'ashr', 'normal', 'none')

        """
        self.alpha = alpha
        self.lfc_threshold = lfc_threshold
        self.independent_filtering = independent_filtering
        self.shrinkage = shrinkage

        self.r_manager = RIntegrationManager()
        self.results_: DEAnalysisResult | None = None

    def run(
        self,
        counts: pd.DataFrame,
        metadata: pd.DataFrame,
        design_formula: str = "~ condition",
        contrast: tuple[str, str, str] | None = None,
        reference_level: str | None = None,
    ) -> DEAnalysisResult:
        """Run DESeq2 differential expression analysis.

        Args:
            counts: Count matrix (genes x samples)
            metadata: Sample metadata DataFrame
            design_formula: R-style design formula
            contrast: Contrast specification (factor, numerator, denominator)
            reference_level: Reference level for the condition factor

        Returns:
            DEAnalysisResult

        """
        if not self.r_manager.r_available:
            return self._run_fallback(counts, metadata)

        deseq2 = self.r_manager.load_package(RPackage.DESEQ2)
        if deseq2 is None:
            return self._run_fallback(counts, metadata)

        try:
            # Convert data to R
            counts_r = self.r_manager.df_to_r(counts)
            metadata_r = self.r_manager.df_to_r(metadata)

            # Create DESeqDataSet
            ro.globalenv["counts_matrix"] = counts_r
            ro.globalenv["col_data"] = metadata_r
            ro.globalenv["design_formula"] = design_formula

            # Set reference level if specified
            if reference_level:
                factor_name = design_formula.replace("~", "").strip().split()[0]
                ro.r(f"""
                    col_data${factor_name} <- relevel(factor(col_data${factor_name}), ref = "{reference_level}")
                """)

            # Run DESeq2
            ro.r("""
                library(DESeq2)
                dds <- DESeqDataSetFromMatrix(
                    countData = as.matrix(counts_matrix),
                    colData = col_data,
                    design = as.formula(design_formula)
                )
                dds <- DESeq(dds)
            """)

            # Get results
            if contrast:
                ro.r(f"""
                    res <- results(dds, contrast = c("{contrast[0]}", "{contrast[1]}", "{contrast[2]}"),
                                   alpha = {self.alpha})
                """)
            else:
                ro.r(f"""
                    res <- results(dds, alpha = {self.alpha})
                """)

            # Apply shrinkage if requested
            if self.shrinkage != "none":
                coef_name = ro.r("resultsNames(dds)")[1]
                ro.r(f"""
                    res <- lfcShrink(dds, coef = "{coef_name}", type = "{self.shrinkage}")
                """)

            # Convert results to DataFrame
            ro.r("""
                res_df <- as.data.frame(res)
                res_df$gene <- rownames(res_df)
            """)

            results_df = self.r_manager.r_to_df(ro.globalenv["res_df"])

            # Process results
            return self._process_results(results_df, "DESeq2")

        except Exception as e:
            logger.error(f"DESeq2 analysis failed: {e}")
            return self._run_fallback(counts, metadata)

    def _run_fallback(self, counts: pd.DataFrame, metadata: pd.DataFrame) -> DEAnalysisResult:
        """Fallback to PyDESeq2 if R is not available."""
        try:
            from pydeseq2.dds import DeseqDataSet
            from pydeseq2.ds import DeseqStats

            logger.info("Using PyDESeq2 fallback")

            # Create dataset
            dds = DeseqDataSet(
                counts=counts.T,  # PyDESeq2 expects samples x genes
                metadata=metadata,
                design_factors="condition",
            )

            # Run analysis
            dds.deseq2()

            # Get statistics
            stat_res = DeseqStats(dds)
            stat_res.summary()

            results_df = stat_res.results_df.reset_index()
            results_df.columns = [
                "gene",
                "baseMean",
                "log2FoldChange",
                "lfcSE",
                "stat",
                "pvalue",
                "padj",
            ]

            return self._process_results(results_df, "PyDESeq2")

        except Exception as e:
            logger.error(f"PyDESeq2 fallback failed: {e}")
            # Return empty results
            return DEAnalysisResult(
                results=pd.DataFrame(),
                significant_genes=[],
                upregulated=[],
                downregulated=[],
                n_tested=0,
                n_significant=0,
                method="failed",
                parameters={},
            )

    def _process_results(self, results_df: pd.DataFrame, method: str) -> DEAnalysisResult:
        """Process and format DESeq2 results."""
        # Standardize column names
        col_map = {
            "baseMean": "base_mean",
            "log2FoldChange": "log2_fold_change",
            "lfcSE": "lfc_se",
            "stat": "stat",
            "pvalue": "p_value",
            "padj": "adjusted_p_value",
        }

        results_df = results_df.rename(columns=col_map)

        # Remove NA values
        results_df = results_df.dropna(subset=["adjusted_p_value"])

        # Identify significant genes
        significant = results_df[
            (results_df["adjusted_p_value"] < self.alpha)
            & (abs(results_df["log2_fold_change"]) > self.lfc_threshold)
        ]

        upregulated = significant[significant["log2_fold_change"] > self.lfc_threshold][
            "gene"
        ].tolist()

        downregulated = significant[significant["log2_fold_change"] < -self.lfc_threshold][
            "gene"
        ].tolist()

        self.results_ = DEAnalysisResult(
            results=results_df,
            significant_genes=significant["gene"].tolist(),
            upregulated=upregulated,
            downregulated=downregulated,
            n_tested=len(results_df),
            n_significant=len(significant),
            method=method,
            parameters={
                "alpha": self.alpha,
                "lfc_threshold": self.lfc_threshold,
                "shrinkage": self.shrinkage,
            },
        )

        return self.results_


class EdgeRAnalyzer:
    """edgeR differential expression analysis.

    Implements negative binomial-based differential
    expression for RNA-seq data using exact test or GLM.
    """

    def __init__(
        self,
        method: str = "glm",  # "exact" or "glm"
        fdr: float = 0.05,
        lfc_threshold: float = 0.0,
    ):
        """Initialize edgeR analyzer.

        Args:
            method: Analysis method ('exact' or 'glm')
            fdr: False discovery rate threshold
            lfc_threshold: Log fold change threshold

        """
        self.method = method
        self.fdr = fdr
        self.lfc_threshold = lfc_threshold

        self.r_manager = RIntegrationManager()
        self.results_: DEAnalysisResult | None = None

    def run(
        self,
        counts: pd.DataFrame,
        groups: pd.Series,
        design_matrix: pd.DataFrame | None = None,
    ) -> DEAnalysisResult:
        """Run edgeR differential expression analysis.

        Args:
            counts: Count matrix (genes x samples)
            groups: Group labels for each sample
            design_matrix: Optional design matrix for GLM

        Returns:
            DEAnalysisResult

        """
        if not self.r_manager.r_available:
            logger.warning("R not available for edgeR")
            return self._create_empty_result()

        edger = self.r_manager.load_package(RPackage.EDGER)
        if edger is None:
            return self._create_empty_result()

        try:
            # Convert data
            counts_r = self.r_manager.df_to_r(counts)
            groups_r = ro.StrVector(groups.values)

            ro.globalenv["counts"] = counts_r
            ro.globalenv["groups"] = groups_r

            if self.method == "exact":
                # Exact test for two groups
                ro.r("""
                    library(edgeR)
                    y <- DGEList(counts = as.matrix(counts), group = groups)
                    y <- calcNormFactors(y)
                    y <- estimateDisp(y)
                    et <- exactTest(y)
                    res <- topTags(et, n = Inf)$table
                    res$gene <- rownames(res)
                """)
            else:
                # GLM approach
                ro.r("""
                    library(edgeR)
                    y <- DGEList(counts = as.matrix(counts), group = groups)
                    y <- calcNormFactors(y)
                    design <- model.matrix(~ groups)
                    y <- estimateDisp(y, design)
                    fit <- glmQLFit(y, design)
                    qlf <- glmQLFTest(fit, coef = 2)
                    res <- topTags(qlf, n = Inf)$table
                    res$gene <- rownames(res)
                """)

            results_df = self.r_manager.r_to_df(ro.globalenv["res"])
            return self._process_results(results_df)

        except Exception as e:
            logger.error(f"edgeR analysis failed: {e}")
            return self._create_empty_result()

    def _process_results(self, results_df: pd.DataFrame) -> DEAnalysisResult:
        """Process edgeR results."""
        # Standardize column names
        col_map = {
            "logFC": "log2_fold_change",
            "logCPM": "log_cpm",
            "F": "f_statistic",
            "PValue": "p_value",
            "FDR": "adjusted_p_value",
        }
        results_df = results_df.rename(columns=col_map)

        # Identify significant genes
        significant = results_df[
            (results_df["adjusted_p_value"] < self.fdr)
            & (abs(results_df["log2_fold_change"]) > self.lfc_threshold)
        ]

        self.results_ = DEAnalysisResult(
            results=results_df,
            significant_genes=significant["gene"].tolist(),
            upregulated=significant[significant["log2_fold_change"] > 0]["gene"].tolist(),
            downregulated=significant[significant["log2_fold_change"] < 0]["gene"].tolist(),
            n_tested=len(results_df),
            n_significant=len(significant),
            method="edgeR",
            parameters={"method": self.method, "fdr": self.fdr},
        )

        return self.results_

    def _create_empty_result(self) -> DEAnalysisResult:
        """Create empty result for failure cases."""
        return DEAnalysisResult(
            results=pd.DataFrame(),
            significant_genes=[],
            upregulated=[],
            downregulated=[],
            n_tested=0,
            n_significant=0,
            method="edgeR_failed",
            parameters={},
        )


class LimmaAnalyzer:
    """limma differential expression analysis.

    Linear modeling for microarray and RNA-seq data
    with empirical Bayes moderation.
    """

    def __init__(
        self,
        fdr: float = 0.05,
        lfc_threshold: float = 0.0,
        voom: bool = True,
        robust: bool = True,
    ):
        """Initialize limma analyzer.

        Args:
            fdr: False discovery rate threshold
            lfc_threshold: Log fold change threshold
            voom: Use voom transformation for RNA-seq
            robust: Use robust eBayes

        """
        self.fdr = fdr
        self.lfc_threshold = lfc_threshold
        self.voom = voom
        self.robust = robust

        self.r_manager = RIntegrationManager()
        self.results_: DEAnalysisResult | None = None

    def run(
        self,
        expression: pd.DataFrame,
        design_matrix: pd.DataFrame,
        contrast_matrix: pd.DataFrame | None = None,
        contrast_name: str | None = None,
    ) -> DEAnalysisResult:
        """Run limma differential expression analysis.

        Args:
            expression: Expression matrix (genes x samples)
            design_matrix: Design matrix
            contrast_matrix: Optional contrast matrix
            contrast_name: Name of contrast to test

        Returns:
            DEAnalysisResult

        """
        if not self.r_manager.r_available:
            logger.warning("R not available for limma")
            return self._create_empty_result()

        limma = self.r_manager.load_package(RPackage.LIMMA)
        if limma is None:
            return self._create_empty_result()

        try:
            # Convert data
            expr_r = self.r_manager.df_to_r(expression)
            design_r = self.r_manager.df_to_r(design_matrix)

            ro.globalenv["expr"] = expr_r
            ro.globalenv["design"] = design_r

            robust_str = "TRUE" if self.robust else "FALSE"

            if self.voom:
                # RNA-seq workflow with voom
                ro.r(f"""
                    library(limma)
                    library(edgeR)
                    dge <- DGEList(counts = as.matrix(expr))
                    dge <- calcNormFactors(dge)
                    v <- voom(dge, as.matrix(design))
                    fit <- lmFit(v, as.matrix(design))
                    fit <- eBayes(fit, robust = {robust_str})
                    res <- topTable(fit, coef = 2, number = Inf, adjust.method = "BH")
                    res$gene <- rownames(res)
                """)
            else:
                # Standard microarray workflow
                ro.r(f"""
                    library(limma)
                    fit <- lmFit(as.matrix(expr), as.matrix(design))
                    fit <- eBayes(fit, robust = {robust_str})
                    res <- topTable(fit, coef = 2, number = Inf, adjust.method = "BH")
                    res$gene <- rownames(res)
                """)

            results_df = self.r_manager.r_to_df(ro.globalenv["res"])
            return self._process_results(results_df)

        except Exception as e:
            logger.error(f"limma analysis failed: {e}")
            return self._create_empty_result()

    def run_from_groups(
        self,
        expression: pd.DataFrame,
        groups: pd.Series,
    ) -> DEAnalysisResult:
        """Run limma with simple two-group comparison.

        Args:
            expression: Expression matrix
            groups: Group labels

        Returns:
            DEAnalysisResult

        """
        # Create design matrix
        unique_groups = groups.unique()
        design = pd.DataFrame(0, index=expression.columns, columns=unique_groups)
        for sample in expression.columns:
            group = (
                groups[sample]
                if sample in groups.index
                else groups.iloc[list(expression.columns).index(sample)]
            )
            design.loc[sample, group] = 1

        return self.run(expression, design)

    def _process_results(self, results_df: pd.DataFrame) -> DEAnalysisResult:
        """Process limma results."""
        col_map = {
            "logFC": "log2_fold_change",
            "AveExpr": "average_expression",
            "t": "t_statistic",
            "P.Value": "p_value",
            "adj.P.Val": "adjusted_p_value",
            "B": "b_statistic",
        }
        results_df = results_df.rename(columns=col_map)

        significant = results_df[
            (results_df["adjusted_p_value"] < self.fdr)
            & (abs(results_df["log2_fold_change"]) > self.lfc_threshold)
        ]

        self.results_ = DEAnalysisResult(
            results=results_df,
            significant_genes=significant["gene"].tolist(),
            upregulated=significant[significant["log2_fold_change"] > 0]["gene"].tolist(),
            downregulated=significant[significant["log2_fold_change"] < 0]["gene"].tolist(),
            n_tested=len(results_df),
            n_significant=len(significant),
            method="limma" + ("_voom" if self.voom else ""),
            parameters={"fdr": self.fdr, "voom": self.voom, "robust": self.robust},
        )

        return self.results_

    def _create_empty_result(self) -> DEAnalysisResult:
        """Create empty result for failure cases."""
        return DEAnalysisResult(
            results=pd.DataFrame(),
            significant_genes=[],
            upregulated=[],
            downregulated=[],
            n_tested=0,
            n_significant=0,
            method="limma_failed",
            parameters={},
        )


def compare_de_methods(
    counts: pd.DataFrame,
    metadata: pd.DataFrame,
    condition_col: str = "condition",
    methods: list[str] | None = None,
) -> pd.DataFrame:
    """Compare results from multiple DE methods.

    Args:
        counts: Count matrix
        metadata: Sample metadata
        condition_col: Condition column name
        methods: Methods to compare (default: all available)

    Returns:
        DataFrame comparing results across methods

    """
    methods = methods or ["deseq2", "edger", "limma"]
    results = {}

    groups = metadata[condition_col]

    if "deseq2" in methods:
        deseq2 = DESeq2Analyzer()
        deseq2_result = deseq2.run(counts, metadata)
        results["deseq2"] = set(deseq2_result.significant_genes)

    if "edger" in methods:
        edger = EdgeRAnalyzer()
        edger_result = edger.run(counts, groups)
        results["edger"] = set(edger_result.significant_genes)

    if "limma" in methods:
        limma = LimmaAnalyzer()
        limma_result = limma.run_from_groups(counts, groups)
        results["limma"] = set(limma_result.significant_genes)

    # Find overlaps
    all_genes = set()
    for genes in results.values():
        all_genes.update(genes)

    comparison_data = []
    for gene in all_genes:
        row = {"gene": gene}
        for method, genes in results.items():
            row[method] = gene in genes
        row["n_methods"] = sum(1 for m in results if gene in results[m])
        comparison_data.append(row)

    comparison_df = pd.DataFrame(comparison_data)
    comparison_df = comparison_df.sort_values("n_methods", ascending=False)

    return comparison_df

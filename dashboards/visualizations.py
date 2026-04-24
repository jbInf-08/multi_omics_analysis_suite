"""
Visualization components for Multi-Omics Analysis Suite Dashboards
==================================================================

Reusable visualization functions for various omics data types.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, List, Dict, Any


def create_volcano_plot(
    data: pd.DataFrame,
    log2fc_col: str = "log2FoldChange",
    pvalue_col: str = "pvalue",
    gene_col: str = "gene",
    fc_threshold: float = 1.0,
    pvalue_threshold: float = 0.05,
    title: str = "Volcano Plot",
) -> go.Figure:
    """Create a volcano plot for differential expression analysis."""
    df = data.copy()
    df["-log10(pvalue)"] = -np.log10(df[pvalue_col] + 1e-300)
    
    # Categorize points
    conditions = [
        (df[log2fc_col] >= fc_threshold) & (df[pvalue_col] < pvalue_threshold),
        (df[log2fc_col] <= -fc_threshold) & (df[pvalue_col] < pvalue_threshold),
    ]
    choices = ["Upregulated", "Downregulated"]
    df["regulation"] = np.select(conditions, choices, default="Not Significant")
    
    color_map = {
        "Upregulated": "#e74c3c",
        "Downregulated": "#3498db",
        "Not Significant": "#95a5a6",
    }
    
    fig = px.scatter(
        df,
        x=log2fc_col,
        y="-log10(pvalue)",
        color="regulation",
        color_discrete_map=color_map,
        hover_data=[gene_col],
        title=title,
    )
    
    # Add threshold lines
    fig.add_hline(y=-np.log10(pvalue_threshold), line_dash="dash", line_color="gray")
    fig.add_vline(x=fc_threshold, line_dash="dash", line_color="gray")
    fig.add_vline(x=-fc_threshold, line_dash="dash", line_color="gray")
    
    fig.update_layout(
        xaxis_title="log2(Fold Change)",
        yaxis_title="-log10(p-value)",
        legend_title="Regulation",
    )
    
    return fig


def create_pca_plot(
    data: pd.DataFrame,
    pc1_col: str = "PC1",
    pc2_col: str = "PC2",
    color_col: Optional[str] = None,
    sample_col: str = "sample",
    var_explained: Optional[List[float]] = None,
    title: str = "PCA Plot",
) -> go.Figure:
    """Create a PCA scatter plot."""
    fig = px.scatter(
        data,
        x=pc1_col,
        y=pc2_col,
        color=color_col,
        hover_data=[sample_col] if sample_col in data.columns else None,
        title=title,
    )
    
    x_title = f"PC1 ({var_explained[0]:.1f}%)" if var_explained else "PC1"
    y_title = f"PC2 ({var_explained[1]:.1f}%)" if var_explained else "PC2"
    
    fig.update_layout(
        xaxis_title=x_title,
        yaxis_title=y_title,
    )
    
    return fig


def create_heatmap(
    data: pd.DataFrame,
    title: str = "Heatmap",
    x_label: str = "Samples",
    y_label: str = "Features",
    colorscale: str = "RdBu_r",
    cluster_rows: bool = True,
    cluster_cols: bool = True,
) -> go.Figure:
    """Create a heatmap visualization."""
    fig = go.Figure(data=go.Heatmap(
        z=data.values,
        x=data.columns.tolist(),
        y=data.index.tolist(),
        colorscale=colorscale,
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title=x_label,
        yaxis_title=y_label,
    )
    
    return fig


def create_correlation_heatmap(
    data: pd.DataFrame,
    method: str = "pearson",
    title: str = "Sample Correlation",
) -> go.Figure:
    """Create a correlation heatmap."""
    corr_matrix = data.corr(method=method)
    
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns.tolist(),
        y=corr_matrix.index.tolist(),
        colorscale="RdBu_r",
        zmin=-1,
        zmax=1,
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Samples",
        yaxis_title="Samples",
    )
    
    return fig


def create_ma_plot(
    data: pd.DataFrame,
    mean_col: str = "baseMean",
    log2fc_col: str = "log2FoldChange",
    pvalue_col: str = "pvalue",
    pvalue_threshold: float = 0.05,
    title: str = "MA Plot",
) -> go.Figure:
    """Create an MA plot."""
    df = data.copy()
    df["log10_mean"] = np.log10(df[mean_col] + 1)
    df["significant"] = df[pvalue_col] < pvalue_threshold
    
    fig = px.scatter(
        df,
        x="log10_mean",
        y=log2fc_col,
        color="significant",
        color_discrete_map={True: "#e74c3c", False: "#95a5a6"},
        title=title,
    )
    
    fig.add_hline(y=0, line_dash="dash", line_color="black")
    
    fig.update_layout(
        xaxis_title="log10(Mean Expression)",
        yaxis_title="log2(Fold Change)",
        showlegend=False,
    )
    
    return fig


def create_pathway_enrichment_bar(
    data: pd.DataFrame,
    pathway_col: str = "pathway",
    pvalue_col: str = "pvalue",
    nes_col: str = "NES",
    top_n: int = 20,
    title: str = "Pathway Enrichment",
) -> go.Figure:
    """Create a pathway enrichment bar plot."""
    df = data.nsmallest(top_n, pvalue_col).copy()
    df["-log10(pvalue)"] = -np.log10(df[pvalue_col])
    
    colors = ["#e74c3c" if x > 0 else "#3498db" for x in df[nes_col]]
    
    fig = go.Figure(data=go.Bar(
        x=df["-log10(pvalue)"],
        y=df[pathway_col],
        orientation="h",
        marker_color=colors,
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="-log10(p-value)",
        yaxis_title="Pathway",
        height=max(400, top_n * 25),
    )
    
    return fig


def create_roc_curve(
    fpr: np.ndarray,
    tpr: np.ndarray,
    auc_score: float,
    title: str = "ROC Curve",
) -> go.Figure:
    """Create an ROC curve."""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=fpr,
        y=tpr,
        mode="lines",
        name=f"ROC (AUC = {auc_score:.3f})",
        line=dict(color="#3498db", width=2),
    ))
    
    fig.add_trace(go.Scatter(
        x=[0, 1],
        y=[0, 1],
        mode="lines",
        name="Random",
        line=dict(color="gray", dash="dash"),
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate",
        xaxis=dict(range=[0, 1]),
        yaxis=dict(range=[0, 1]),
    )
    
    return fig


def create_confusion_matrix_plot(
    confusion_matrix: np.ndarray,
    labels: List[str],
    title: str = "Confusion Matrix",
) -> go.Figure:
    """Create a confusion matrix heatmap."""
    fig = go.Figure(data=go.Heatmap(
        z=confusion_matrix,
        x=labels,
        y=labels,
        colorscale="Blues",
        text=confusion_matrix,
        texttemplate="%{text}",
        textfont={"size": 14},
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Predicted",
        yaxis_title="Actual",
    )
    
    return fig


def create_feature_importance_bar(
    features: List[str],
    importances: np.ndarray,
    top_n: int = 20,
    title: str = "Feature Importance",
) -> go.Figure:
    """Create a feature importance bar plot."""
    df = pd.DataFrame({
        "feature": features,
        "importance": importances,
    }).nlargest(top_n, "importance")
    
    fig = go.Figure(data=go.Bar(
        x=df["importance"],
        y=df["feature"],
        orientation="h",
        marker_color="#3498db",
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Importance",
        yaxis_title="Feature",
        height=max(400, top_n * 25),
    )
    
    return fig


def create_shap_summary_plot(
    shap_values: np.ndarray,
    features: pd.DataFrame,
    top_n: int = 20,
    title: str = "SHAP Feature Importance",
) -> go.Figure:
    """Create a SHAP summary plot."""
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    feature_names = features.columns.tolist()
    
    df = pd.DataFrame({
        "feature": feature_names,
        "importance": mean_abs_shap,
    }).nlargest(top_n, "importance")
    
    fig = go.Figure(data=go.Bar(
        x=df["importance"],
        y=df["feature"],
        orientation="h",
        marker_color="#9b59b6",
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="mean(|SHAP value|)",
        yaxis_title="Feature",
        height=max(400, top_n * 25),
    )
    
    return fig


def create_variant_distribution_plot(
    data: pd.DataFrame,
    variant_type_col: str = "variant_type",
    title: str = "Variant Type Distribution",
) -> go.Figure:
    """Create a variant distribution pie/bar chart."""
    counts = data[variant_type_col].value_counts()
    
    fig = go.Figure(data=go.Pie(
        labels=counts.index.tolist(),
        values=counts.values,
        hole=0.3,
    ))
    
    fig.update_layout(title=title)
    
    return fig


def create_mutation_spectrum_plot(
    data: pd.DataFrame,
    substitution_col: str = "substitution",
    title: str = "Mutation Spectrum",
) -> go.Figure:
    """Create a mutation spectrum (96-trinucleotide context or 6-class) plot."""
    counts = data[substitution_col].value_counts()
    
    # Standard mutation classes
    mutation_colors = {
        "C>A": "#3498db",
        "C>G": "#2ecc71",
        "C>T": "#e74c3c",
        "T>A": "#9b59b6",
        "T>C": "#f39c12",
        "T>G": "#1abc9c",
    }
    
    fig = go.Figure(data=go.Bar(
        x=counts.index.tolist(),
        y=counts.values,
        marker_color=[mutation_colors.get(x, "#95a5a6") for x in counts.index],
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Substitution Type",
        yaxis_title="Count",
    )
    
    return fig


def create_cnv_genome_plot(
    data: pd.DataFrame,
    chrom_col: str = "chromosome",
    start_col: str = "start",
    end_col: str = "end",
    log2_col: str = "log2ratio",
    title: str = "Copy Number Variation",
) -> go.Figure:
    """Create a genome-wide CNV plot."""
    # Create genomic positions
    fig = go.Figure()
    
    for chrom in data[chrom_col].unique():
        chrom_data = data[data[chrom_col] == chrom]
        fig.add_trace(go.Scatter(
            x=(chrom_data[start_col] + chrom_data[end_col]) / 2,
            y=chrom_data[log2_col],
            mode="markers",
            name=str(chrom),
            marker=dict(size=4),
        ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="black")
    fig.add_hline(y=0.5, line_dash="dash", line_color="red")
    fig.add_hline(y=-0.5, line_dash="dash", line_color="blue")
    
    fig.update_layout(
        title=title,
        xaxis_title="Genomic Position",
        yaxis_title="log2(Copy Number Ratio)",
    )
    
    return fig


def create_alpha_diversity_boxplot(
    data: pd.DataFrame,
    diversity_col: str = "shannon",
    group_col: str = "group",
    title: str = "Alpha Diversity",
) -> go.Figure:
    """Create an alpha diversity boxplot."""
    fig = px.box(
        data,
        x=group_col,
        y=diversity_col,
        color=group_col,
        title=title,
    )
    
    fig.update_layout(
        xaxis_title="Group",
        yaxis_title="Shannon Diversity Index",
        showlegend=False,
    )
    
    return fig


def create_beta_diversity_pcoa(
    data: pd.DataFrame,
    pc1_col: str = "PC1",
    pc2_col: str = "PC2",
    group_col: str = "group",
    var_explained: Optional[List[float]] = None,
    title: str = "Beta Diversity PCoA",
) -> go.Figure:
    """Create a beta diversity PCoA plot."""
    fig = px.scatter(
        data,
        x=pc1_col,
        y=pc2_col,
        color=group_col,
        title=title,
    )
    
    x_title = f"PCoA1 ({var_explained[0]:.1f}%)" if var_explained else "PCoA1"
    y_title = f"PCoA2 ({var_explained[1]:.1f}%)" if var_explained else "PCoA2"
    
    fig.update_layout(
        xaxis_title=x_title,
        yaxis_title=y_title,
    )
    
    return fig


def create_taxa_barplot(
    data: pd.DataFrame,
    sample_col: str = "sample",
    top_n: int = 10,
    title: str = "Taxonomic Composition",
) -> go.Figure:
    """Create a stacked bar plot of taxonomic composition."""
    # Assume data has samples as rows and taxa as columns
    data_subset = data.iloc[:, :top_n]
    
    fig = go.Figure()
    
    for col in data_subset.columns:
        if col != sample_col:
            fig.add_trace(go.Bar(
                name=col,
                x=data_subset[sample_col] if sample_col in data_subset.columns else data_subset.index,
                y=data_subset[col],
            ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Sample",
        yaxis_title="Relative Abundance",
        barmode="stack",
    )
    
    return fig


def create_survival_curve(
    times: List[np.ndarray],
    survival_probs: List[np.ndarray],
    labels: List[str],
    pvalue: Optional[float] = None,
    title: str = "Kaplan-Meier Survival Curve",
) -> go.Figure:
    """Create a Kaplan-Meier survival curve."""
    colors = px.colors.qualitative.Set1
    
    fig = go.Figure()
    
    for i, (t, s, label) in enumerate(zip(times, survival_probs, labels)):
        fig.add_trace(go.Scatter(
            x=t,
            y=s,
            mode="lines",
            name=label,
            line=dict(color=colors[i % len(colors)], shape="hv"),
        ))
    
    fig.update_layout(
        title=title + (f" (p = {pvalue:.4f})" if pvalue else ""),
        xaxis_title="Time",
        yaxis_title="Survival Probability",
        yaxis=dict(range=[0, 1.05]),
    )
    
    return fig


def create_network_graph(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    node_id_col: str = "id",
    node_size_col: Optional[str] = None,
    node_color_col: Optional[str] = None,
    edge_source_col: str = "source",
    edge_target_col: str = "target",
    edge_weight_col: Optional[str] = None,
    title: str = "Network Visualization",
) -> go.Figure:
    """Create a network visualization."""
    # Simple force-directed layout approximation
    n_nodes = len(nodes)
    np.random.seed(42)
    pos_x = np.random.randn(n_nodes)
    pos_y = np.random.randn(n_nodes)
    
    # Create node trace
    node_sizes = nodes[node_size_col].values * 10 if node_size_col else [20] * n_nodes
    
    node_trace = go.Scatter(
        x=pos_x,
        y=pos_y,
        mode="markers+text",
        marker=dict(
            size=node_sizes,
            color=nodes[node_color_col] if node_color_col else "#3498db",
            colorscale="Viridis" if node_color_col else None,
        ),
        text=nodes[node_id_col],
        textposition="top center",
        hoverinfo="text",
    )
    
    # Create edge traces
    edge_traces = []
    node_id_to_idx = {nid: i for i, nid in enumerate(nodes[node_id_col])}
    
    for _, edge in edges.iterrows():
        src_idx = node_id_to_idx.get(edge[edge_source_col])
        tgt_idx = node_id_to_idx.get(edge[edge_target_col])
        if src_idx is not None and tgt_idx is not None:
            edge_traces.append(go.Scatter(
                x=[pos_x[src_idx], pos_x[tgt_idx], None],
                y=[pos_y[src_idx], pos_y[tgt_idx], None],
                mode="lines",
                line=dict(width=1, color="#cccccc"),
                hoverinfo="none",
            ))
    
    fig = go.Figure(data=edge_traces + [node_trace])
    
    fig.update_layout(
        title=title,
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    
    return fig


def create_umap_plot(
    data: pd.DataFrame,
    umap1_col: str = "UMAP1",
    umap2_col: str = "UMAP2",
    color_col: Optional[str] = None,
    title: str = "UMAP Visualization",
) -> go.Figure:
    """Create a UMAP plot."""
    fig = px.scatter(
        data,
        x=umap1_col,
        y=umap2_col,
        color=color_col,
        title=title,
    )
    
    fig.update_layout(
        xaxis_title="UMAP 1",
        yaxis_title="UMAP 2",
    )
    
    return fig


def create_lipid_class_pie(
    data: pd.DataFrame,
    lipid_class_col: str = "lipid_class",
    abundance_col: str = "abundance",
    title: str = "Lipid Class Distribution",
) -> go.Figure:
    """Create a lipid class distribution pie chart."""
    class_totals = data.groupby(lipid_class_col)[abundance_col].sum()
    
    fig = go.Figure(data=go.Pie(
        labels=class_totals.index.tolist(),
        values=class_totals.values,
        hole=0.4,
    ))
    
    fig.update_layout(title=title)
    
    return fig


def create_methylation_density_plot(
    data: pd.DataFrame,
    beta_col: str = "beta_value",
    group_col: Optional[str] = None,
    title: str = "Methylation Beta Value Distribution",
) -> go.Figure:
    """Create a methylation beta value density plot."""
    if group_col:
        fig = px.histogram(
            data,
            x=beta_col,
            color=group_col,
            nbins=50,
            histnorm="probability density",
            barmode="overlay",
            opacity=0.7,
            title=title,
        )
    else:
        fig = px.histogram(
            data,
            x=beta_col,
            nbins=50,
            histnorm="probability density",
            title=title,
        )
    
    fig.update_layout(
        xaxis_title="Beta Value",
        yaxis_title="Density",
    )
    
    return fig


# =============================================================================
# Demo Data Generators
# =============================================================================

def generate_demo_de_data(n_genes: int = 1000) -> pd.DataFrame:
    """Generate demo differential expression data."""
    np.random.seed(42)
    
    log2fc = np.random.normal(0, 1.5, n_genes)
    pvalue = np.random.exponential(0.1, n_genes)
    pvalue = np.clip(pvalue, 1e-300, 1)
    
    # Make some genes significant
    significant_idx = np.random.choice(n_genes, int(n_genes * 0.1), replace=False)
    log2fc[significant_idx] = np.random.choice([-1, 1], len(significant_idx)) * np.random.uniform(2, 5, len(significant_idx))
    pvalue[significant_idx] = np.random.uniform(1e-10, 0.001, len(significant_idx))
    
    return pd.DataFrame({
        "gene": [f"Gene_{i}" for i in range(n_genes)],
        "log2FoldChange": log2fc,
        "pvalue": pvalue,
        "baseMean": np.random.lognormal(5, 2, n_genes),
    })


def generate_demo_pca_data(n_samples: int = 100) -> pd.DataFrame:
    """Generate demo PCA data."""
    np.random.seed(42)
    
    groups = np.random.choice(["Control", "Treatment A", "Treatment B"], n_samples)
    
    # Create cluster structure
    pc1 = np.random.randn(n_samples) * 10
    pc2 = np.random.randn(n_samples) * 8
    
    for i, g in enumerate(groups):
        if g == "Treatment A":
            pc1[i] += 15
        elif g == "Treatment B":
            pc2[i] += 12
    
    return pd.DataFrame({
        "sample": [f"Sample_{i}" for i in range(n_samples)],
        "PC1": pc1,
        "PC2": pc2,
        "group": groups,
    })


def generate_demo_pathway_data(n_pathways: int = 30) -> pd.DataFrame:
    """Generate demo pathway enrichment data."""
    np.random.seed(42)
    
    pathway_names = [
        "Cell Cycle", "Apoptosis", "DNA Repair", "Immune Response",
        "Metabolism", "Signal Transduction", "Gene Expression",
        "Cell Migration", "Angiogenesis", "Inflammation",
        "Oxidative Stress", "Autophagy", "Cell Adhesion",
        "Protein Folding", "Lipid Metabolism", "Amino Acid Metabolism",
        "Carbohydrate Metabolism", "Nucleotide Metabolism",
        "Energy Metabolism", "Drug Metabolism", "Xenobiotic Metabolism",
        "Hormone Signaling", "Neurotransmitter Signaling",
        "Growth Factor Signaling", "Cytokine Signaling",
        "Wnt Signaling", "Notch Signaling", "Hedgehog Signaling",
        "TGF-beta Signaling", "MAPK Signaling",
    ][:n_pathways]
    
    return pd.DataFrame({
        "pathway": pathway_names,
        "pvalue": np.random.exponential(0.01, n_pathways),
        "NES": np.random.uniform(-2.5, 2.5, n_pathways),
        "size": np.random.randint(10, 200, n_pathways),
    })


def generate_demo_variant_data(n_variants: int = 500) -> pd.DataFrame:
    """Generate demo variant data."""
    np.random.seed(42)
    
    variant_types = np.random.choice(
        ["SNV", "Insertion", "Deletion", "MNV"],
        n_variants,
        p=[0.7, 0.15, 0.12, 0.03],
    )
    
    substitutions = np.random.choice(
        ["C>A", "C>G", "C>T", "T>A", "T>C", "T>G"],
        n_variants,
        p=[0.1, 0.05, 0.35, 0.1, 0.25, 0.15],
    )
    
    return pd.DataFrame({
        "variant_type": variant_types,
        "substitution": substitutions,
        "chromosome": np.random.choice([f"chr{i}" for i in range(1, 23)], n_variants),
        "position": np.random.randint(1, 250_000_000, n_variants),
    })

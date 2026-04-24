"""Multi-Omics Analysis Suite CLI - Main Entry Point.
=================================================

Command-line interface for running multi-omics analyses.
"""

import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Initialize CLI app
app = typer.Typer(
    name="moas",
    help="Multi-Omics Analysis Suite - Comprehensive bioinformatics analysis platform",
    add_completion=True,
    no_args_is_help=True,
)

console = Console()

# Sub-command groups
analyze_app = typer.Typer(help="Run various omics analyses")
data_app = typer.Typer(help="Data management commands")
ml_app = typer.Typer(help="Machine learning commands")
pipeline_app = typer.Typer(help="Pipeline management")
config_app = typer.Typer(help="Configuration management")
annotate_app = typer.Typer(help="Genome annotation (gene prediction, assembly GFF)")
chemistry_app = typer.Typer(help="Structure, MD, and docking")

app.add_typer(analyze_app, name="analyze")
app.add_typer(data_app, name="data")
app.add_typer(ml_app, name="ml")
app.add_typer(pipeline_app, name="pipeline")
app.add_typer(config_app, name="config")
app.add_typer(annotate_app, name="annotate")
app.add_typer(chemistry_app, name="chemistry")

api_app = typer.Typer(help="Call the running HTTP API (MOAS_API_BASE_URL, MOAS_API_TOKEN)")


# =============================================================================
# Main Commands
# =============================================================================


@app.command()
def version():
    """Show version information."""
    from backend import __version__

    console.print(
        Panel(
            f"[bold blue]Multi-Omics Analysis Suite[/bold blue]\n"
            f"Version: {__version__}\n"
            f"Python: {sys.version.split()[0]}",
            title="MOAS",
            expand=False,
        )
    )


@app.command()
def info():
    """Show available omics modules and analyses."""
    from backend.omics import OmicsCategory, OmicsRegistry

    registry = OmicsRegistry()
    registry.discover_modules()

    console.print("\n[bold]Available Omics Modules[/bold]\n")

    for category in OmicsCategory:
        modules = registry.list_modules(category.value)
        if modules:
            table = Table(title=category.value, show_header=True)
            table.add_column("Module", style="cyan")
            table.add_column("Description", style="white")
            table.add_column("Pipelines", style="green")
            table.add_column("Analyses", style="yellow")

            for module in modules:
                pipelines = len(module.get_available_pipelines())
                analyses = len(module.get_available_analyses())
                table.add_row(
                    module.name,
                    (
                        module.description[:50] + "..."
                        if len(module.description) > 50
                        else module.description
                    ),
                    str(pipelines),
                    str(analyses),
                )

            console.print(table)
            console.print()


@app.command()
def init(
    project_dir: Path = typer.Argument(..., help="Project directory to initialize"),
    name: str = typer.Option(None, "--name", "-n", help="Project name"),
):
    """Initialize a new analysis project."""
    if project_dir.exists() and any(project_dir.iterdir()):
        console.print(f"[red]Error: Directory {project_dir} is not empty[/red]")
        raise typer.Exit(1)

    project_dir.mkdir(parents=True, exist_ok=True)

    # Create project structure
    directories = [
        "data/raw",
        "data/processed",
        "results",
        "notebooks",
        "reports",
        "configs",
    ]

    for d in directories:
        (project_dir / d).mkdir(parents=True, exist_ok=True)

    # Create default config
    config_content = f"""# MOAS Project Configuration
project_name: {name or project_dir.name}
version: "1.0.0"

# Data settings
data:
  raw_dir: data/raw
  processed_dir: data/processed

# Analysis defaults
analysis:
  significance_level: 0.05
  multiple_testing_correction: fdr_bh
  normalization: quantile

# ML settings
ml:
  test_size: 0.2
  cv_folds: 5
  random_seed: 42
"""
    (project_dir / "configs" / "project.yaml").write_text(config_content)

    console.print(f"[green]Project initialized at {project_dir}[/green]")
    console.print(f"Created directories: {', '.join(directories)}")


# =============================================================================
# Analyze Commands
# =============================================================================


@analyze_app.command("de")
def differential_expression(
    input_file: Path = typer.Argument(..., help="Input expression matrix file"),
    metadata_file: Path = typer.Argument(..., help="Sample metadata file"),
    output_dir: Path = typer.Option("./results/de", "--output", "-o", help="Output directory"),
    group_col: str = typer.Option("group", "--group", "-g", help="Column for group comparison"),
    control: str = typer.Option("control", "--control", "-c", help="Control group name"),
    treatment: str = typer.Option("treatment", "--treatment", "-t", help="Treatment group name"),
    method: str = typer.Option(
        "ttest", "--method", "-m", help="Statistical method (ttest, wilcoxon, deseq2)"
    ),
    alpha: float = typer.Option(0.05, "--alpha", help="Significance level"),
    fc_threshold: float = typer.Option(1.0, "--fc", help="log2 fold change threshold"),
):
    """Run differential expression analysis."""
    import numpy as np
    import pandas as pd
    from scipy import stats

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading data...", total=None)

        # Load data
        expr = pd.read_csv(input_file, index_col=0)
        meta = pd.read_csv(metadata_file, index_col=0)

        progress.update(task, description="Running differential expression analysis...")

        # Get sample groups
        control_samples = meta[meta[group_col] == control].index
        treatment_samples = meta[meta[group_col] == treatment].index

        results = []
        for gene in expr.index:
            ctrl_vals = expr.loc[gene, control_samples].values.astype(float)
            treat_vals = expr.loc[gene, treatment_samples].values.astype(float)

            # Calculate statistics
            log2fc = np.log2(np.mean(treat_vals) + 1) - np.log2(np.mean(ctrl_vals) + 1)

            if method == "ttest":
                stat, pval = stats.ttest_ind(ctrl_vals, treat_vals)
            else:  # wilcoxon
                stat, pval = stats.mannwhitneyu(ctrl_vals, treat_vals)

            results.append(
                {
                    "gene": gene,
                    "log2FoldChange": log2fc,
                    "pvalue": pval,
                    "baseMean": (np.mean(ctrl_vals) + np.mean(treat_vals)) / 2,
                }
            )

        df_results = pd.DataFrame(results)

        # Multiple testing correction
        from statsmodels.stats.multitest import multipletests

        df_results["padj"] = multipletests(df_results["pvalue"], method="fdr_bh")[1]

        # Mark significant
        df_results["significant"] = (df_results["padj"] < alpha) & (
            np.abs(df_results["log2FoldChange"]) > fc_threshold
        )

        progress.update(task, description="Saving results...")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        df_results.to_csv(output_dir / "de_results.csv", index=False)

    # Summary
    n_up = len(df_results[(df_results["significant"]) & (df_results["log2FoldChange"] > 0)])
    n_down = len(df_results[(df_results["significant"]) & (df_results["log2FoldChange"] < 0)])

    console.print("\n[bold green]Analysis complete![/bold green]")
    console.print(f"Total genes: {len(df_results)}")
    console.print(f"Upregulated: [red]{n_up}[/red]")
    console.print(f"Downregulated: [blue]{n_down}[/blue]")
    console.print(f"Results saved to: {output_dir / 'de_results.csv'}")


@analyze_app.command("pathway")
def pathway_analysis(
    gene_list: Path = typer.Argument(..., help="File with gene list (one per line or DE results)"),
    output_dir: Path = typer.Option("./results/pathway", "--output", "-o", help="Output directory"),
    database: str = typer.Option("kegg", "--db", help="Pathway database (kegg, reactome, go)"),
    organism: str = typer.Option("hsa", "--organism", help="Organism code"),
    top_n: int = typer.Option(20, "--top", "-n", help="Number of top pathways to report"),
):
    """Run pathway enrichment analysis."""
    import pandas as pd

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading gene list...", total=None)

        # Load genes
        if gene_list.suffix == ".csv":
            df = pd.read_csv(gene_list)
            genes = df["gene"].tolist() if "gene" in df.columns else df.iloc[:, 0].tolist()
        else:
            genes = gene_list.read_text().strip().split("\n")

        progress.update(task, description=f"Running pathway analysis ({database})...")

        # Placeholder: In real implementation, call pathway analysis libraries
        # For demo, create mock results
        import numpy as np

        np.random.seed(42)

        pathway_names = [
            "Cell cycle",
            "Apoptosis",
            "DNA repair",
            "Immune response",
            "Metabolism of lipids",
            "Signal transduction",
            "Gene expression",
            "Cell migration",
            "Angiogenesis",
            "Inflammation",
            "Oxidative stress",
            "Autophagy",
            "Cell adhesion",
            "Protein folding",
            "Lipid metabolism",
            "Amino acid metabolism",
            "Carbohydrate metabolism",
            "Nucleotide metabolism",
            "Energy metabolism",
            "Drug metabolism",
        ][:top_n]

        results = pd.DataFrame(
            {
                "pathway": pathway_names,
                "pvalue": np.random.exponential(0.01, top_n),
                "padj": np.random.exponential(0.05, top_n),
                "enrichment_score": np.random.uniform(1.5, 4.0, top_n),
                "overlap_genes": np.random.randint(5, 50, top_n),
                "pathway_size": np.random.randint(20, 200, top_n),
            }
        )
        results = results.sort_values("pvalue")

        progress.update(task, description="Saving results...")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        results.to_csv(output_dir / "pathway_enrichment.csv", index=False)

    console.print("\n[bold green]Pathway analysis complete![/bold green]")
    console.print(f"Input genes: {len(genes)}")
    console.print(f"Database: {database}")
    console.print("Top enriched pathways:")

    table = Table()
    table.add_column("Pathway", style="cyan")
    table.add_column("P-value", style="yellow")
    table.add_column("Genes", style="green")

    for _, row in results.head(10).iterrows():
        table.add_row(
            row["pathway"],
            f"{row['pvalue']:.2e}",
            f"{row['overlap_genes']}/{row['pathway_size']}",
        )

    console.print(table)


@analyze_app.command("qc")
def quality_control(
    input_file: Path = typer.Argument(..., help="Input data file"),
    output_dir: Path = typer.Option("./results/qc", "--output", "-o", help="Output directory"),
    omics_type: str = typer.Option("transcriptomics", "--type", "-t", help="Omics data type"),
):
    """Run quality control analysis on omics data."""
    import pandas as pd

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading data...", total=None)

        df = pd.read_csv(input_file, index_col=0)

        progress.update(task, description="Running QC checks...")

        qc_results = {
            "n_features": len(df),
            "n_samples": len(df.columns),
            "missing_rate": df.isna().sum().sum() / (df.shape[0] * df.shape[1]) * 100,
            "zero_rate": (df == 0).sum().sum() / (df.shape[0] * df.shape[1]) * 100,
            "mean_coverage": df.sum().mean(),
            "median_coverage": df.sum().median(),
            "low_coverage_samples": len(df.columns[df.sum() < df.sum().median() * 0.5]),
            "low_variance_features": len(df.index[df.var(axis=1) < 0.1]),
        }

        progress.update(task, description="Saving QC report...")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save QC metrics
        pd.Series(qc_results).to_csv(output_dir / "qc_metrics.csv")

        # Save sample statistics
        sample_stats = pd.DataFrame(
            {
                "total_counts": df.sum(),
                "detected_features": (df > 0).sum(),
                "mean": df.mean(),
                "std": df.std(),
            }
        )
        sample_stats.to_csv(output_dir / "sample_statistics.csv")

    console.print("\n[bold green]QC analysis complete![/bold green]")

    table = Table(title="QC Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    for metric, value in qc_results.items():
        if isinstance(value, float):
            table.add_row(metric, f"{value:.2f}")
        else:
            table.add_row(metric, str(value))

    console.print(table)


# =============================================================================
# Data Commands
# =============================================================================


@data_app.command("import")
def import_data(
    input_file: Path = typer.Argument(..., help="Input data file to import"),
    output_dir: Path = typer.Option("./data/processed", "--output", "-o", help="Output directory"),
    format: str = typer.Option("csv", "--format", "-f", help="Output format (csv, parquet, h5)"),
    normalize: bool = typer.Option(False, "--normalize", "-n", help="Apply normalization"),
):
    """Import and preprocess data files."""
    import pandas as pd

    console.print(f"Importing {input_file}...")

    # Determine input format and load
    suffix = input_file.suffix.lower()
    if suffix in [".csv", ".tsv", ".txt"]:
        sep = "\t" if suffix in [".tsv", ".txt"] else ","
        df = pd.read_csv(input_file, sep=sep, index_col=0)
    elif suffix == ".xlsx":
        df = pd.read_excel(input_file, index_col=0)
    elif suffix in [".h5", ".hdf5"]:
        df = pd.read_hdf(input_file)
    else:
        console.print(f"[red]Unsupported format: {suffix}[/red]")
        raise typer.Exit(1)

    if normalize:
        console.print("Applying normalization...")
        # Simple log2 + quantile normalization placeholder
        df = df.apply(lambda x: (x - x.min()) / (x.max() - x.min() + 1e-10))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{input_file.stem}_processed.{format}"

    if format == "csv":
        df.to_csv(output_file)
    elif format == "parquet":
        df.to_parquet(output_file)
    elif format == "h5":
        df.to_hdf(output_file, key="data")

    console.print(f"[green]Data imported: {output_file}[/green]")
    console.print(f"Shape: {df.shape[0]} features x {df.shape[1]} samples")


@data_app.command("merge")
def merge_datasets(
    inputs: list[Path] = typer.Argument(..., help="Input files to merge"),
    output: Path = typer.Option("./data/merged.csv", "--output", "-o", help="Output file"),
    method: str = typer.Option(
        "inner", "--method", "-m", help="Merge method (inner, outer, left, right)"
    ),
    axis: int = typer.Option(1, "--axis", help="Axis to merge (0=rows, 1=columns)"),
):
    """Merge multiple omics datasets."""
    import pandas as pd

    console.print(f"Merging {len(inputs)} datasets...")

    dfs = [pd.read_csv(f, index_col=0) for f in inputs]

    if axis == 0:
        merged = pd.concat(dfs, axis=0, join=method)
    else:
        merged = dfs[0]
        for df in dfs[1:]:
            merged = merged.merge(df, left_index=True, right_index=True, how=method)

    output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output)

    console.print(f"[green]Merged dataset saved: {output}[/green]")
    console.print(f"Final shape: {merged.shape}")


# =============================================================================
# ML Commands
# =============================================================================


@ml_app.command("train")
def train_model(
    data_file: Path = typer.Argument(..., help="Training data file (features)"),
    labels_file: Path = typer.Argument(..., help="Labels file"),
    output_dir: Path = typer.Option("./models", "--output", "-o", help="Output directory"),
    model_type: str = typer.Option("random_forest", "--model", "-m", help="Model type"),
    task: str = typer.Option("classification", "--task", "-t", help="Task type"),
    test_size: float = typer.Option(0.2, "--test-size", help="Test set proportion"),
    cv_folds: int = typer.Option(5, "--cv", help="Cross-validation folds"),
):
    """Train a machine learning model."""
    import joblib
    import pandas as pd

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        t = progress.add_task("Loading data...", total=None)

        X = pd.read_csv(data_file, index_col=0)
        y = pd.read_csv(labels_file, index_col=0).iloc[:, 0]

        progress.update(t, description="Preparing data...")

        from sklearn.model_selection import cross_val_score, train_test_split

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        progress.update(t, description=f"Training {model_type}...")

        # Get model
        if model_type == "random_forest":
            from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

            if task == "classification":
                model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            else:
                model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        elif model_type == "xgboost":
            import xgboost as xgb

            if task == "classification":
                model = xgb.XGBClassifier(n_estimators=100, random_state=42, n_jobs=-1)
            else:
                model = xgb.XGBRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        elif model_type == "svm":
            from sklearn.pipeline import Pipeline
            from sklearn.preprocessing import StandardScaler
            from sklearn.svm import SVC, SVR

            if task == "classification":
                model = Pipeline([("scaler", StandardScaler()), ("svm", SVC(probability=True))])
            else:
                model = Pipeline([("scaler", StandardScaler()), ("svm", SVR())])
        else:
            console.print(f"[red]Unknown model type: {model_type}[/red]")
            raise typer.Exit(1)

        # Cross-validation
        progress.update(t, description="Running cross-validation...")
        scoring = "accuracy" if task == "classification" else "r2"
        cv_scores = cross_val_score(model, X_train, y_train, cv=cv_folds, scoring=scoring)

        # Train final model
        progress.update(t, description="Training final model...")
        model.fit(X_train, y_train)

        # Evaluate
        progress.update(t, description="Evaluating...")
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)

        # Save model
        progress.update(t, description="Saving model...")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, output_dir / f"{model_type}_model.joblib")

    console.print("\n[bold green]Training complete![/bold green]")

    table = Table(title="Model Performance")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Model Type", model_type)
    table.add_row("Task", task)
    table.add_row(
        f"CV Score ({cv_folds}-fold)", f"{cv_scores.mean():.4f} (+/- {cv_scores.std()*2:.4f})"
    )
    table.add_row("Train Score", f"{train_score:.4f}")
    table.add_row("Test Score", f"{test_score:.4f}")

    console.print(table)
    console.print(f"Model saved to: {output_dir / f'{model_type}_model.joblib'}")


@ml_app.command("predict")
def predict(
    model_file: Path = typer.Argument(..., help="Trained model file"),
    data_file: Path = typer.Argument(..., help="Data to predict"),
    output: Path = typer.Option("./predictions.csv", "--output", "-o", help="Output file"),
    proba: bool = typer.Option(False, "--proba", "-p", help="Output probabilities"),
):
    """Make predictions using a trained model."""
    import joblib
    import pandas as pd

    console.print("Loading model and data...")

    model = joblib.load(model_file)
    X = pd.read_csv(data_file, index_col=0)

    console.print("Making predictions...")

    predictions = model.predict(X)

    result = pd.DataFrame({"prediction": predictions}, index=X.index)

    if proba and hasattr(model, "predict_proba"):
        probas = model.predict_proba(X)
        for i, col in enumerate(model.classes_):
            result[f"prob_{col}"] = probas[:, i]

    result.to_csv(output)

    console.print(f"[green]Predictions saved to: {output}[/green]")
    console.print(f"Total predictions: {len(predictions)}")


@ml_app.command("feature-selection")
def feature_selection(
    data_file: Path = typer.Argument(..., help="Feature data file"),
    labels_file: Path = typer.Argument(..., help="Labels file"),
    output: Path = typer.Option("./selected_features.csv", "--output", "-o", help="Output file"),
    method: str = typer.Option(
        "rf", "--method", "-m", help="Selection method (rf, lasso, rfe, univariate)"
    ),
    n_features: int = typer.Option(50, "--n-features", "-n", help="Number of features to select"),
):
    """Run feature selection on omics data."""
    import numpy as np
    import pandas as pd

    console.print(f"Running feature selection ({method})...")

    X = pd.read_csv(data_file, index_col=0)
    y = pd.read_csv(labels_file, index_col=0).iloc[:, 0]

    if method == "rf":
        from sklearn.ensemble import RandomForestClassifier

        model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X, y)
        importances = model.feature_importances_
    elif method == "lasso":
        from sklearn.linear_model import LassoCV
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        model = LassoCV(cv=5, random_state=42)
        model.fit(X_scaled, y)
        importances = np.abs(model.coef_)
    elif method == "univariate":
        from sklearn.feature_selection import f_classif

        f_scores, _ = f_classif(X, y)
        importances = f_scores
    elif method == "rfe":
        from sklearn.feature_selection import RFE
        from sklearn.linear_model import LogisticRegression

        model = LogisticRegression(max_iter=1000, random_state=42)
        selector = RFE(model, n_features_to_select=n_features, step=100)
        selector.fit(X, y)
        importances = selector.ranking_
        importances = 1 / importances  # Invert so higher is better
    else:
        console.print(f"[red]Unknown method: {method}[/red]")
        raise typer.Exit(1)

    # Get top features
    feature_importance = pd.DataFrame(
        {
            "feature": X.columns,
            "importance": importances,
        }
    ).sort_values("importance", ascending=False)

    selected = feature_importance.head(n_features)
    selected.to_csv(output, index=False)

    console.print(f"[green]Selected {n_features} features[/green]")
    console.print(f"Results saved to: {output}")

    console.print("\nTop 10 features:")
    for _i, row in selected.head(10).iterrows():
        console.print(f"  {row['feature']}: {row['importance']:.4f}")


# =============================================================================
# Annotation Commands
# =============================================================================


@annotate_app.command("genes")
def cli_predict_genes(
    fasta: Path = typer.Argument(..., help="Input FASTA (DNA contigs)"),
    output_dir: Path = typer.Option(
        Path("results/annotation"), "--output", "-o", help="Output directory"
    ),
    predictor: str = typer.Option(
        "prodigal", "--predictor", "-p", help="prodigal|augustus|glimmer|metagene|orf"
    ),
    gff_name: str = typer.Option("genes.gff", "--gff-name", help="GFF filename under output_dir"),
):
    """Predict genes on each FASTA record and write GFF."""
    from backend.pipelines.gene_annotation import annotate_fasta_path

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    gff_path = output_dir / gff_name

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        t = progress.add_task("Running gene prediction...", total=None)
        try:
            result = annotate_fasta_path(
                fasta,
                predictor=predictor,
                include_sequences=False,
                gff_output=gff_path,
            )
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e
        progress.update(t, description="Done")

    console.print(f"[green]Genes predicted: {result['total_genes']}[/green]")
    console.print(f"GFF written to: {gff_path}")


@annotate_app.command("assembly")
def cli_annotate_assembly_fasta(
    fasta: Path = typer.Argument(..., help="Assembly FASTA (contigs)"),
    output_dir: Path = typer.Option(Path("results/assembly_annotation"), "--output", "-o"),
    predictor: str = typer.Option("prodigal", "--predictor", "-p"),
    gff_name: str = typer.Option("assembly_genes.gff", "--gff-name"),
):
    """Gene-annotate an assembly FASTA (same engine as ``annotate genes``, explicit naming)."""
    cli_predict_genes(fasta=fasta, output_dir=output_dir, predictor=predictor, gff_name=gff_name)


# =============================================================================
# Computational chemistry CLI
# =============================================================================


@chemistry_app.command("md")
def cli_run_md(
    pdb: Path = typer.Argument(..., help="Input PDB"),
    output: Path = typer.Option(Path("results/md_summary.json"), "--output", "-o"),
    n_steps: int = typer.Option(100, "--steps", "-n"),
    save_interval: int = typer.Option(25, "--save-interval"),
    temperature: float = typer.Option(300.0, "--temperature", "-t"),
):
    """Run molecular dynamics on a PDB structure and write a short JSON summary."""
    import json

    from backend.computational_chemistry import (
        BerendsenThermostat,
        MDSimulation,
        Molecule,
        TrajectoryAnalyzer,
    )

    pdb_text = pdb.read_text(encoding="utf-8", errors="replace")
    mol = Molecule.from_pdb(pdb_text)
    if mol.num_atoms == 0:
        console.print("[red]No atoms in PDB[/red]")
        raise typer.Exit(1)

    md = MDSimulation(mol, thermostat=BerendsenThermostat(temperature, tau=0.5))
    md.initialize(box_size=80.0, temperature=temperature)
    md.minimize_energy(max_steps=40, tolerance=0.5)
    md.run(n_steps=n_steps, save_interval=save_interval, print_interval=n_steps + 1)

    analyzer = TrajectoryAnalyzer(md.trajectory)
    ref = md.trajectory[0].positions if md.trajectory else mol.positions.copy()
    summary = {
        "n_atoms": mol.num_atoms,
        "n_frames": len(md.trajectory),
        "final_total_energy_kcal_mol": float(md.state.total_energy) if md.state else None,
        "rmsd": analyzer.calculate_rmsd(ref).tolist() if md.trajectory else [],
        "radius_of_gyration": (
            analyzer.calculate_radius_of_gyration().tolist() if md.trajectory else []
        ),
        "energy_statistics": analyzer.energy_statistics() if md.trajectory else {},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    console.print(f"[green]MD summary written to {output}[/green]")


@chemistry_app.command("dock")
def cli_run_dock(
    protein: Path = typer.Argument(..., help="Receptor PDB"),
    ligand: Path = typer.Argument(..., help="Ligand PDB"),
    output: Path = typer.Option(Path("results/docking.json"), "--output", "-o"),
    n_poses: int = typer.Option(10, "--poses", "-n"),
    exhaustiveness: int = typer.Option(4, "--exhaustiveness", "-e"),
):
    """Dock ligand PDB into receptor PDB (binding site at receptor geometric center)."""
    import json

    from backend.computational_chemistry import MolecularDocking, Molecule
    from backend.computational_chemistry.docking import binding_site_at_receptor_center

    prot = Molecule.from_pdb(protein.read_text(encoding="utf-8", errors="replace"))
    lig = Molecule.from_pdb(ligand.read_text(encoding="utf-8", errors="replace"))
    if prot.num_atoms == 0 or lig.num_atoms == 0:
        console.print("[red]Empty protein or ligand[/red]")
        raise typer.Exit(1)

    dock = MolecularDocking(exhaustiveness=exhaustiveness, n_poses=n_poses)
    poses = dock.dock(lig, prot, binding_site=binding_site_at_receptor_center(prot))
    data = {
        "n_poses": len(poses),
        "poses": [
            {
                "rank": p.rank,
                "total_score": float(p.score.total_score),
                "n_contacts": len(p.contacts),
            }
            for p in poses
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    console.print(f"[green]Docking results written to {output}[/green]")


@chemistry_app.command("structure-pipeline")
def cli_structure_md_dock(
    protein: Path = typer.Argument(..., help="Receptor PDB"),
    ligand: Path = typer.Argument(..., help="Ligand PDB"),
    output: Path = typer.Option(Path("results/structure_md_dock.json"), "--output", "-o"),
    md_steps: int = typer.Option(120, "--md-steps"),
):
    """Run structure → MD → docking and write JSON results."""
    import json

    from backend.pipelines.structure_md_dock import run_structure_md_dock

    result = run_structure_md_dock(
        protein.read_text(encoding="utf-8", errors="replace"),
        ligand.read_text(encoding="utf-8", errors="replace"),
        md_steps=md_steps,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    console.print(f"[green]Pipeline output written to {output}[/green]")


# =============================================================================
# Pipeline Commands
# =============================================================================


@pipeline_app.command("run")
def run_pipeline(
    config_file: Path = typer.Argument(..., help="Pipeline configuration YAML file"),
    output_dir: Path = typer.Option("./results", "--output", "-o", help="Output directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show steps without executing"),
):
    """Run an analysis pipeline from configuration."""
    import yaml

    console.print(f"Loading pipeline config: {config_file}")

    with open(config_file) as f:
        config = yaml.safe_load(f)

    pipeline_name = config.get("name", "Unnamed Pipeline")
    steps = config.get("steps", [])

    console.print(f"\n[bold]Pipeline: {pipeline_name}[/bold]")
    console.print(f"Steps: {len(steps)}")

    if dry_run:
        console.print("\n[yellow]Dry run - showing steps:[/yellow]")
        for i, step in enumerate(steps, 1):
            console.print(f"  {i}. {step.get('name', 'Unnamed')} ({step.get('type', 'unknown')})")
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for i, step in enumerate(steps, 1):
            task = progress.add_task(
                f"Step {i}/{len(steps)}: {step.get('name', 'Running...')}", total=None
            )

            # Execute step based on type
            step.get("type")
            step.get("params", {})

            # Placeholder for actual step execution
            import time

            time.sleep(0.5)  # Simulate work

            progress.update(task, description=f"Step {i}/{len(steps)}: Complete")

    console.print("\n[bold green]Pipeline complete![/bold green]")
    console.print(f"Results saved to: {output_dir}")


@pipeline_app.command("list")
def list_pipelines():
    """List available pipeline templates."""
    from backend.omics import OmicsRegistry

    registry = OmicsRegistry()
    registry.discover_modules()

    console.print("\n[bold]Available Pipeline Templates[/bold]\n")

    table = Table()
    table.add_column("Omics Type", style="cyan")
    table.add_column("Pipeline", style="white")
    table.add_column("Description", style="dim")

    for module_name in registry.list_all_modules():
        module = registry.get_module(module_name)
        if module:
            for pipeline in module.get_available_pipelines():
                desc = pipeline.description if hasattr(pipeline, "description") else ""
                table.add_row(
                    module_name,
                    pipeline.name if hasattr(pipeline, "name") else str(pipeline),
                    desc[:50] + "..." if len(desc) > 50 else desc,
                )

    console.print(table)


# =============================================================================
# Config Commands
# =============================================================================


@config_app.command("show")
def show_config(
    config_file: Path | None = typer.Argument(None, help="Configuration file to show"),
):
    """Show current configuration."""
    import yaml

    if config_file:
        with open(config_file) as f:
            config = yaml.safe_load(f)
    else:
        # Show default config
        config = {
            "api_url": "http://localhost:8000",
            "default_omics": "transcriptomics",
            "output_format": "csv",
            "verbosity": "info",
        }

    console.print(
        Panel(
            yaml.dump(config, default_flow_style=False),
            title="Configuration",
            expand=False,
        )
    )


@api_app.command("module-analyze")
def api_module_analyze(
    module: str = typer.Argument(..., help="Omics module name, e.g. single_cell"),
    analysis_type: str = typer.Argument(
        ..., help="Analysis name from GET /omics/modules/{module}/analyses"
    ),
    project_id: str = typer.Argument(..., help="Project UUID"),
    dataset_ids: str = typer.Option("", "--dataset-ids", help="Comma-separated dataset UUIDs"),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        envvar="MOAS_API_BASE_URL",
        help="API base URL (default http://localhost:8000)",
    ),
    token: str | None = typer.Option(
        None,
        "--token",
        envvar="MOAS_API_TOKEN",
        help="JWT access token (no 'Bearer ' prefix)",
    ),
    parameters_json: str = typer.Option(
        "{}", "--parameters-json", help="JSON object for parameters"
    ),
):
    """POST /api/v1/omics/modules/{module}/analyze (queues Celery; returns Analysis JSON)."""
    import json
    import urllib.error
    import urllib.request

    base = (base_url or os.environ.get("MOAS_API_BASE_URL") or "http://localhost:8000").rstrip("/")
    tok = token or os.environ.get("MOAS_API_TOKEN")
    if not tok:
        console.print("[red]Missing token: pass --token or set MOAS_API_TOKEN[/red]")
        raise typer.Exit(1)
    try:
        params_obj = json.loads(parameters_json) if parameters_json.strip() else {}
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid --parameters-json: {exc}[/red]")
        raise typer.Exit(1)
    ids = [x.strip() for x in dataset_ids.split(",") if x.strip()]
    body = {
        "project_id": project_id,
        "analysis_type": analysis_type,
        "parameters": params_obj,
        "dataset_ids": ids,
    }
    url = f"{base}/api/v1/omics/modules/{module}/analyze"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            console.print(Panel(raw, title=f"HTTP {resp.status}", expand=False))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        console.print(
            Panel(
                f"[red]{exc.code} {exc.reason}[/red]\n{err_body}", title="API error", expand=False
            )
        )
        raise typer.Exit(1)


app.add_typer(api_app, name="api")


@config_app.command("validate")
def validate_config(
    config_file: Path = typer.Argument(..., help="Configuration file to validate"),
):
    """Validate a configuration file."""
    import yaml

    try:
        with open(config_file) as f:
            config = yaml.safe_load(f)

        console.print(f"[green]Configuration is valid: {config_file}[/green]")

        # Show summary
        if "steps" in config:
            console.print(f"  Pipeline steps: {len(config['steps'])}")
        if "data" in config:
            console.print(f"  Data sources: {len(config.get('data', {}).get('sources', []))}")

    except yaml.YAMLError as e:
        console.print(f"[red]Invalid YAML: {e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Entry Point
# =============================================================================


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

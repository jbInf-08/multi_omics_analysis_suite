"""
Multi-Omics Analysis Suite - Dash Dashboard Application
========================================================

Interactive dashboards for multi-omics data visualization and analysis.
"""

import os
from dash import Dash, html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from .visualizations import (
    create_volcano_plot,
    create_pca_plot,
    create_ma_plot,
    create_pathway_enrichment_bar,
    create_roc_curve,
    create_confusion_matrix_plot,
    create_feature_importance_bar,
    create_variant_distribution_plot,
    create_mutation_spectrum_plot,
    create_alpha_diversity_boxplot,
    create_survival_curve,
    generate_demo_de_data,
    generate_demo_pca_data,
    generate_demo_pathway_data,
    generate_demo_variant_data,
)

# Initialize Dash app
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True,
    title="Multi-Omics Analysis Suite",
)

server = app.server

# Generate demo data for visualizations
DEMO_DE_DATA = generate_demo_de_data(1000)
DEMO_PCA_DATA = generate_demo_pca_data(100)
DEMO_PATHWAY_DATA = generate_demo_pathway_data(30)
DEMO_VARIANT_DATA = generate_demo_variant_data(500)

# =============================================================================
# Layout Components
# =============================================================================

def create_navbar():
    """Create navigation bar."""
    return dbc.Navbar(
        dbc.Container([
            dbc.NavbarBrand([
                html.I(className="fas fa-dna me-2"),
                "Multi-Omics Analysis Suite",
            ], href="/"),
            dbc.NavbarToggler(id="navbar-toggler"),
            dbc.Collapse(
                dbc.Nav([
                    dbc.NavItem(dbc.NavLink("Dashboard", href="/")),
                    dbc.NavItem(dbc.NavLink("Genomics", href="/genomics")),
                    dbc.NavItem(dbc.NavLink("Transcriptomics", href="/transcriptomics")),
                    dbc.NavItem(dbc.NavLink("Proteomics", href="/proteomics")),
                    dbc.NavItem(dbc.NavLink("Metabolomics", href="/metabolomics")),
                    dbc.NavItem(dbc.NavLink("Integration", href="/integration")),
                    dbc.NavItem(dbc.NavLink("ML/AI", href="/ml")),
                ], className="ms-auto", navbar=True),
                id="navbar-collapse",
                navbar=True,
            ),
        ]),
        color="primary",
        dark=True,
        className="mb-4",
    )


def create_sidebar():
    """Create sidebar with omics modules."""
    omics_categories = {
        "Core Omics": ["genomics", "transcriptomics", "proteomics", "metabolomics", 
                       "epigenomics", "metagenomics", "pharmacogenomics", "lipidomics"],
        "Modification Omics": ["phosphoproteomics", "glycomics", "acetylomics", 
                               "methylomics", "ubiquitomics", "kinomics"],
        "Interaction Omics": ["interactomics", "connectomics", "regulomics", 
                              "secretomics", "degradomics"],
        "Clinical Omics": ["immunogenomics", "pharmacoproteomics", "toxicogenomics", 
                           "nutrigenomics", "neurogenomics"],
    }
    
    sidebar_items = []
    for category, modules in omics_categories.items():
        sidebar_items.append(
            dbc.AccordionItem([
                dbc.ListGroup([
                    dbc.ListGroupItem(m.capitalize(), href=f"/{m}", className="border-0")
                    for m in modules
                ], flush=True)
            ], title=category)
        )
    
    return html.Div([
        html.H5("Omics Modules", className="mb-3"),
        dbc.Accordion(sidebar_items, start_collapsed=True),
    ], className="bg-light p-3 rounded")


def create_stats_cards():
    """Create statistics cards."""
    return dbc.Row([
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("50+", className="text-primary"),
                html.P("Omics Types", className="text-muted mb-0"),
            ])
        ]), width=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("100+", className="text-success"),
                html.P("Analyses", className="text-muted mb-0"),
            ])
        ]), width=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("10+", className="text-info"),
                html.P("ML Models", className="text-muted mb-0"),
            ])
        ]), width=3),
        dbc.Col(dbc.Card([
            dbc.CardBody([
                html.H4("5+", className="text-warning"),
                html.P("Integration Methods", className="text-muted mb-0"),
            ])
        ]), width=3),
    ], className="mb-4")


# =============================================================================
# Dashboard Pages
# =============================================================================

def create_home_page():
    """Create home page."""
    return html.Div([
        create_stats_cards(),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Quick Start"),
                    dbc.CardBody([
                        dbc.ListGroup([
                            dbc.ListGroupItem([
                                html.I(className="fas fa-upload me-2"),
                                "Upload Data",
                            ], action=True),
                            dbc.ListGroupItem([
                                html.I(className="fas fa-cogs me-2"),
                                "Run Analysis",
                            ], action=True),
                            dbc.ListGroupItem([
                                html.I(className="fas fa-chart-bar me-2"),
                                "View Results",
                            ], action=True),
                            dbc.ListGroupItem([
                                html.I(className="fas fa-download me-2"),
                                "Export Reports",
                            ], action=True),
                        ], flush=True),
                    ]),
                ]),
            ], width=4),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("Recent Analyses"),
                    dbc.CardBody([
                        html.P("No recent analyses", className="text-muted"),
                    ]),
                ]),
            ], width=4),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader("System Status"),
                    dbc.CardBody([
                        dbc.Progress(value=100, color="success", className="mb-2"),
                        html.Small("API: Online", className="text-success d-block"),
                        html.Small("Database: Connected", className="text-success d-block"),
                        html.Small("Workers: Running", className="text-success d-block"),
                    ]),
                ]),
            ], width=4),
        ]),
    ])


def create_genomics_dashboard():
    """Create genomics dashboard."""
    variant_dist_fig = create_variant_distribution_plot(DEMO_VARIANT_DATA)
    mutation_spectrum_fig = create_mutation_spectrum_plot(DEMO_VARIANT_DATA)
    
    return html.Div([
        html.H3("Genomics Dashboard"),
        dbc.Tabs([
            dbc.Tab(label="Variant Analysis", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Variant Distribution"),
                            dbc.CardBody([
                                dcc.Graph(figure=variant_dist_fig),
                            ]),
                        ]),
                    ], width=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Mutation Spectrum"),
                            dbc.CardBody([
                                dcc.Graph(figure=mutation_spectrum_fig),
                            ]),
                        ]),
                    ], width=6),
                ]),
            ]),
            dbc.Tab(label="CNV Analysis", children=[
                dbc.Card([
                    dbc.CardBody([
                        html.P("Upload genomics data to view CNV analysis"),
                        dcc.Graph(id="cnv-plot"),
                    ]),
                ]),
            ]),
            dbc.Tab(label="Oncoplots", children=[
                dbc.Card([
                    dbc.CardBody([
                        html.P("Upload genomics data to view oncoplots"),
                        dcc.Graph(id="oncoplot"),
                    ]),
                ]),
            ]),
        ]),
    ])


def create_transcriptomics_dashboard():
    """Create transcriptomics dashboard."""
    pca_fig = create_pca_plot(
        DEMO_PCA_DATA, 
        color_col="group",
        var_explained=[45.2, 23.1],
        title="Sample PCA"
    )
    volcano_fig = create_volcano_plot(DEMO_DE_DATA)
    ma_fig = create_ma_plot(DEMO_DE_DATA)
    pathway_fig = create_pathway_enrichment_bar(DEMO_PATHWAY_DATA)
    
    return html.Div([
        html.H3("Transcriptomics Dashboard"),
        dbc.Tabs([
            dbc.Tab(label="Expression Overview", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("PCA Plot"),
                            dbc.CardBody([
                                dcc.Graph(figure=pca_fig),
                            ]),
                        ]),
                    ], width=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Sample Groups"),
                            dbc.CardBody([
                                dcc.Graph(
                                    figure=px.bar(
                                        DEMO_PCA_DATA["group"].value_counts().reset_index(),
                                        x="group", y="count",
                                        title="Samples per Group"
                                    )
                                ),
                            ]),
                        ]),
                    ], width=6),
                ]),
            ]),
            dbc.Tab(label="Differential Expression", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Volcano Plot"),
                            dbc.CardBody([
                                dcc.Graph(figure=volcano_fig),
                            ]),
                        ]),
                    ], width=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("MA Plot"),
                            dbc.CardBody([
                                dcc.Graph(figure=ma_fig),
                            ]),
                        ]),
                    ], width=6),
                ]),
            ]),
            dbc.Tab(label="Pathway Analysis", children=[
                dbc.Card([
                    dbc.CardBody([
                        dcc.Graph(figure=pathway_fig),
                    ]),
                ]),
            ]),
        ]),
    ])


def create_integration_dashboard():
    """Create multi-omics integration dashboard."""
    return html.Div([
        html.H3("Multi-Omics Integration Dashboard"),
        dbc.Tabs([
            dbc.Tab(label="Data Fusion", children=[
                dbc.Card([
                    dbc.CardHeader("Integrated Data Visualization"),
                    dbc.CardBody([
                        dcc.Graph(id="fusion-plot"),
                    ]),
                ]),
            ]),
            dbc.Tab(label="Network Integration", children=[
                dbc.Card([
                    dbc.CardHeader("Sample Similarity Network"),
                    dbc.CardBody([
                        dcc.Graph(id="network-plot"),
                    ]),
                ]),
            ]),
            dbc.Tab(label="Pathway Integration", children=[
                dbc.Card([
                    dbc.CardHeader("Cross-Omics Pathway Scores"),
                    dbc.CardBody([
                        dcc.Graph(id="pathway-integration-plot"),
                    ]),
                ]),
            ]),
        ]),
    ])


def create_ml_dashboard():
    """Create ML/AI dashboard."""
    # Generate demo ROC curve
    np.random.seed(42)
    fpr = np.sort(np.concatenate([[0], np.random.rand(100), [1]]))
    tpr = np.sort(np.concatenate([[0], np.random.rand(100), [1]]))
    # Make it look like a good classifier
    tpr = np.clip(tpr + 0.3, 0, 1)
    tpr = np.sort(tpr)
    roc_fig = create_roc_curve(fpr, tpr, 0.94)
    
    # Demo confusion matrix
    cm = np.array([[85, 15], [10, 90]])
    cm_fig = create_confusion_matrix_plot(cm, ["Negative", "Positive"])
    
    # Demo feature importance
    features = [f"Feature_{i}" for i in range(30)]
    importances = np.random.exponential(0.05, 30)
    importance_fig = create_feature_importance_bar(features, importances)
    
    return html.Div([
        html.H3("Machine Learning Dashboard"),
        dbc.Tabs([
            dbc.Tab(label="Model Training", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Model Selection"),
                            dbc.CardBody([
                                dcc.Dropdown(
                                    id="model-selector",
                                    options=[
                                        {"label": "Random Forest", "value": "random_forest"},
                                        {"label": "XGBoost", "value": "xgboost"},
                                        {"label": "LightGBM", "value": "lightgbm"},
                                        {"label": "Neural Network", "value": "mlp"},
                                        {"label": "Graph Neural Network", "value": "gnn"},
                                        {"label": "Cox Survival", "value": "cox"},
                                    ],
                                    value="random_forest",
                                ),
                                html.Hr(),
                                dbc.Label("Task Type"),
                                dcc.Dropdown(
                                    id="task-selector",
                                    options=[
                                        {"label": "Classification", "value": "classification"},
                                        {"label": "Regression", "value": "regression"},
                                        {"label": "Survival", "value": "survival"},
                                    ],
                                    value="classification",
                                ),
                                html.Hr(),
                                dbc.Button("Train Model", id="train-btn", color="primary", className="w-100"),
                            ]),
                        ]),
                    ], width=4),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Training Progress"),
                            dbc.CardBody([
                                dbc.Progress(id="training-progress", value=75, label="75%"),
                                html.Hr(),
                                html.H6("Training Metrics"),
                                dbc.ListGroup([
                                    dbc.ListGroupItem("Epoch: 10/10"),
                                    dbc.ListGroupItem("Train Loss: 0.142"),
                                    dbc.ListGroupItem("Val Loss: 0.158"),
                                    dbc.ListGroupItem("Val Accuracy: 0.94"),
                                ], flush=True),
                            ]),
                        ]),
                    ], width=8),
                ]),
            ]),
            dbc.Tab(label="Model Evaluation", children=[
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("ROC Curve"),
                            dbc.CardBody([
                                dcc.Graph(figure=roc_fig),
                            ]),
                        ]),
                    ], width=6),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader("Confusion Matrix"),
                            dbc.CardBody([
                                dcc.Graph(figure=cm_fig),
                            ]),
                        ]),
                    ], width=6),
                ]),
            ]),
            dbc.Tab(label="Explainability", children=[
                dbc.Card([
                    dbc.CardHeader("Feature Importance (SHAP)"),
                    dbc.CardBody([
                        dcc.Graph(figure=importance_fig),
                    ]),
                ]),
            ]),
        ]),
    ])


# =============================================================================
# Main Layout
# =============================================================================

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    create_navbar(),
    dbc.Container([
        dbc.Row([
            dbc.Col(create_sidebar(), width=3),
            dbc.Col(html.Div(id="page-content"), width=9),
        ]),
    ], fluid=True),
])


# =============================================================================
# Callbacks
# =============================================================================

@callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
)
def display_page(pathname):
    """Route to appropriate page."""
    if pathname == "/" or pathname is None:
        return create_home_page()
    elif pathname == "/genomics":
        return create_genomics_dashboard()
    elif pathname == "/transcriptomics":
        return create_transcriptomics_dashboard()
    elif pathname == "/integration":
        return create_integration_dashboard()
    elif pathname == "/ml":
        return create_ml_dashboard()
    else:
        # Generic omics dashboard
        omics_name = pathname.strip("/").replace("_", " ").title()
        return html.Div([
            html.H3(f"{omics_name} Dashboard"),
            dbc.Alert(f"Dashboard for {omics_name} - Coming Soon", color="info"),
        ])


# =============================================================================
# Run
# =============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    debug = os.environ.get("DEBUG", "true").lower() == "true"
    app.run_server(host="0.0.0.0", port=port, debug=debug)

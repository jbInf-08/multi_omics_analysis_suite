# Multi-Omics Analysis Suite

A comprehensive, production-ready multi-omics analysis platform covering 50+ omics disciplines with advanced ML/AI capabilities, interactive visualizations, scalable infrastructure, and complete bioinformatics pipelines.

## Features

### Core Bioinformatics Foundation

#### Sequence Analysis
- **Sequence Classes** - DNA, RNA, and protein sequence manipulation with rich methods
- **Alignment Algorithms** - Needleman-Wunsch, Smith-Waterman, multiple sequence alignment
- **File Format Support** - FASTA, FASTQ, GFF/GTF, BED, SAM/BAM, VCF, GenBank parsers
- **Motif Analysis** - PWM scoring, consensus finding, k-mer counting
- **Index Structures** - FM-index, suffix arrays, Burrows-Wheeler Transform

#### Genome Assembly
- **De Novo Assembly** - De Bruijn graph and OLC-based assemblers
- **Reference-Guided Assembly** - Template-based assembly with gap filling
- **Hybrid Assembly** - Combining short and long reads
- **Scaffolding** - Paired-end, mate-pair, long-read, and Hi-C scaffolding
- **Polishing** - Consensus polishing, error correction, homopolymer correction
- **Quality Assessment** - QUAST-like metrics, BUSCO analysis, k-mer completeness

#### Genome Annotation
- **Gene Prediction** - Prodigal-like, Augustus-like, Glimmer-like, MetaGene predictors
- **Functional Annotation** - BLAST, HMM profiles, InterPro, GO, KEGG, COG assignment
- **Structural Annotation** - tRNA, rRNA, ncRNA, CRISPR, promoter, terminator detection
- **Repeat Finding** - Tandem, inverted, and interspersed repeat detection
- **Comparative Genomics** - Synteny, ortholog finding, gene clustering

#### Read Alignment
- **Short Read Mapping** - BWA-like FM-index based alignment
- **Long Read Mapping** - Minimap2-like minimizer-based alignment
- **Spliced Alignment** - RNA-seq aware alignment with splice junction detection
- **BAM Processing** - Pileup generation, coverage analysis, duplicate marking
- **Quality Control** - Mapping statistics, insert size analysis, coverage analysis

### Long Read Sequencing (ONT & PacBio)
- **Quality Analysis** - Read length distribution, quality profiles, N50/Nx calculation
- **Error Profiling** - Substitution, insertion, deletion analysis
- **Adapter Detection** - Automatic adapter identification and trimming
- **Methylation Calling** - Base modification detection
- **Structural Variants** - Breakpoint detection, insertion/deletion/inversion calling
- **Haplotype Phasing** - Read partitioning and haplotype assembly
- **Isoform Detection** - Full-length transcript identification

### Computational Chemistry
- **Molecular Structure** - Atom, bond, residue, and molecule representation
- **Molecular Dynamics** - Force fields, integrators, thermostats, barostats
- **Trajectory Analysis** - RMSD, RMSF, radius of gyration, distance analysis
- **Molecular Docking** - Binding site prediction, pose generation, scoring functions
- **QSAR** - Molecular descriptors, fingerprints, activity prediction
- **Geometry Optimization** - Energy minimization, conformer generation

### Systems Biology
- **Biological Networks** - PPI, gene regulatory, metabolic, signaling networks
- **Network Analysis** - Centrality, clustering, community detection
- **ODE Modeling** - Kinetic models, steady-state analysis, parameter estimation
- **Sensitivity Analysis** - Local and global parameter sensitivity
- **Bifurcation Analysis** - One-parameter bifurcation diagrams
- **Boolean Networks** - Discrete dynamics and attractor analysis

### Omics Coverage (50+ Types)

#### Core Omics (Fully Implemented)
- **Genomics** - DNA sequence analysis, variant calling, CNV detection
- **Transcriptomics** - RNA-seq, differential expression, splicing analysis
- **Proteomics** - Mass spectrometry, protein quantification, PTM analysis
- **Metabolomics** - LC-MS/NMR analysis, metabolite identification, pathway mapping
- **Epigenomics** - DNA methylation, histone modifications, chromatin accessibility
- **Metagenomics** - Taxonomic profiling, functional analysis, community composition
- **Pharmacogenomics** - Drug-gene interactions, PGx variant analysis
- **Lipidomics** - Lipid profiling, lipid pathway analysis

#### Single-Cell Analysis
- **scRNA-seq** - Clustering, trajectory analysis, cell type annotation
- **scATAC-seq** - Chromatin accessibility at single-cell level
- **Multimodal** - CITE-seq, Multiome integration
- **Spatial** - Spatial transcriptomics with squidpy
- **RNA Velocity** - Future state prediction with scVelo
- **Cell Communication** - Ligand-receptor interaction inference

#### Epigenetic Analysis
- **ChIP-seq** - Peak calling, differential binding, motif analysis
- **ATAC-seq** - Chromatin accessibility profiling
- **Hi-C** - 3D genome organization, TAD calling, loop detection
- **Bisulfite-seq** - DNA methylation at single-base resolution
- **CUT&Tag** - Efficient chromatin profiling

#### Modification Omics
- Phosphoproteomics, Glycomics, Acetylomics, Methylomics, Ubiquitomics, Kinomics, Chromatomics

#### Interaction Omics
- Interactomics, Connectomics, Synaptomics, Regulomics, Secretomics, Degradomics, Membranomics

#### Clinical/Applied Omics
- Immunogenomics, Pharmacoproteomics, Toxicogenomics, Nutrigenomics, Neurogenomics, Allergomics

#### Specialized Omics (20+ more)
- Exposomics, Microbiomics, Fluxomics, Phenomics, Radiomics, Spatialomics, and many more...

### Technology Stack

- **Backend**: FastAPI, GraphQL (Strawberry), Celery, WebSocket
- **Databases**: PostgreSQL, Redis, Neo4j
- **ML/AI**: PyTorch, PyTorch Geometric, scikit-learn, XGBoost, SHAP
- **Frontend**: React 18, TypeScript, Tailwind CSS
- **Dashboards**: Dash, Plotly
- **Infrastructure**: Docker, Kubernetes, Terraform, Prometheus/Grafana

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- Node.js 18+ (for frontend)

### Installation

```bash
# Clone the repository
git clone https://github.com/jbInf-08/multi_omics_analysis_suite.git
cd multi_omics_analysis_suite

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev,notebooks,dash]"

# Start services with Docker Compose
docker-compose up -d

# Run database migrations (creates/updates schemas and tables)
alembic upgrade head

# Start the API server
uvicorn backend.app.main:app --reload
```

### Using the CLI

```bash
# List available omics modules
omics list-modules

# Run a genomics analysis
omics analyze genomics --input data/samples.vcf --output results/

# Run multi-omics integration
omics integrate --omics genomics,proteomics,metabolomics --input data/ --output integrated/
```

The commands above run **local** analyses through the Typer CLI. To **queue a server-side** analysis on a registered omics module (same Celery pipeline as `POST /api/v1/analyses/`), call the REST API or use:

```bash
# Requires a running API and JWT from POST /api/v1/auth/login
export MOAS_API_BASE_URL=http://localhost:8000
export MOAS_API_TOKEN=<your_access_token>

omics api module-analyze single_cell clustering <project-uuid> \
  --dataset-ids "" \
  --parameters-json '{"k": 10}'
```

`POST /api/v1/omics/modules/{module_name}/analyze` accepts JSON with:

- **`project_id`** (UUID): project that owns the run (you must be the project owner).
- **`analysis_type`** (string): one of the names from `GET /api/v1/omics/modules/{module}/analyses`.
- **`parameters`** (object): forwarded to the Celery task (merged with module metadata such as `omics_execute_analysis_type`).
- **`dataset_ids`** (array of UUID strings): optional input datasets.

The response is **201** with the same **Analysis** shape as `POST /api/v1/analyses/` (`id`, `status`, `celery_task_id`, etc.).

### API Documentation

Once running, access the interactive API documentation:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **GraphQL**: http://localhost:8000/graphql

GraphQL **subscriptions** (`analysisProgress`) require a **Bearer JWT**. Over WebSocket (graphql-transport-ws), send `connection_init` with `connection_params` containing `Authorization: "Bearer <token>"`. In production (`DEBUG=false`), connections without a valid token are rejected at connect time.

### Bioinformatics tools API (`/api/v1/tools`)

Gene prediction, molecular dynamics, docking, and the structure→MD→dock pipeline are exposed under `/api/v1/tools`. Authenticate with a normal **Bearer JWT** (same as other v1 routes), or set `TOOLS_API_KEY` in the environment and send `X-API-Key: <same value>`. For local automation only, you can set `TOOLS_ALLOW_ANONYMOUS=true` (not recommended in production).

Chemistry endpoints (`/tools/chemistry/...`) apply per-IP rate limits (`TOOLS_CHEMISTRY_RATE_LIMIT` per `TOOLS_CHEMISTRY_RATE_PERIOD_SECONDS`, default 30/minute; set limit to `0` to disable). With `TOOLS_CHEMISTRY_RATE_LIMIT_BACKEND=auto` (default), limits are enforced in **Redis** when `REDIS_URL` is reachable so multiple API replicas share one counter; otherwise an in-process limiter is used.

#### How to use quickly (tools)

1. **Env** — Set `TOOLS_API_KEY` and send header `X-API-Key: <same value>`, **or** use a normal Bearer JWT from `/api/v1/auth/login`. For local scripts only, you may set `TOOLS_ALLOW_ANONYMOUS=true` (do not use in production).
2. **UI** — Start the API (`uvicorn …`) and the frontend (`npm run dev` in `frontend/`). Open **http://localhost:3000/tools** (Vite proxies `/api` to **http://localhost:8000** by default).
3. **CI** — On every push or PR to **`main`** or **`develop`**, the GitHub Actions **Test** job runs `pytest tests/integration/test_bioinformatics_tools_api.py` and `tests/integration/test_omics_analyze_api.py` (plus the rest of the test matrix). See `.github/workflows/ci.yml`.

**Examples (curl)**

List predictors (requires auth as above):

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/tools/annotation/genes/predictors
```

Predict genes on one contig (Python predictor):

```bash
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"sequence":"ATGAAACCCAAATAA","contig_id":"c1","predictor":"orf"}' \
  http://localhost:8000/api/v1/tools/annotation/genes/predict
```

Optional **Prodigal binary** (must be on `PATH`): add `"use_prodigal_binary": true` and `"predictor": "prodigal"` to the JSON body for predict / predict-fasta / assembly routes.

Short MD: `POST /api/v1/tools/chemistry/md/run` with JSON `{"pdb": "<entire PDB as a string>", "n_steps": 50, ...}`.

Structure → MD → docking: `POST /api/v1/tools/chemistry/pipelines/structure-md-dock` with `protein_pdb` and `ligand_pdb` strings (see Swagger **Bioinformatics Tools** schemas for all fields).

The React app includes a **Tools** page (`/tools`) that calls these endpoints using the stored login token.

### Configuration and API Keys

External data sources (COSMIC, OncoKB, DrugBank, DepMap/CCLE, etc.) can be enabled via environment variables. Copy `.env.example` to `.env` and set the keys you need. See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for the full list and registration links.

### Testing

```bash
# Unit tests
pytest tests/unit -v

# Integration tests (requires DB and Redis or mocks)
pytest tests/integration -v

# With coverage
pytest tests/unit tests/integration -v --cov=backend --cov-report=term-missing
```

Frontend tests:
```bash
cd frontend && npm test
```

## Project Structure

```
multi_omics_analysis_suite/
├── backend/                 # FastAPI backend
│   ├── app/                # Application core
│   ├── omics/              # 50+ omics modules
│   ├── ml/                 # ML/AI engine
│   ├── pipelines/          # Analysis pipelines
│   └── data_collection/    # Data collectors
├── frontend/               # React frontend
├── dashboards/             # Dash dashboards
├── cli/                    # CLI tools
├── notebooks/              # Jupyter notebooks
├── k8s/                    # Kubernetes configs
├── terraform/              # Infrastructure as Code
├── tests/                  # Test suite
└── docs/                   # Documentation
```

## Architecture

The suite uses a modular, plugin-based architecture where each omics type is a self-contained module that implements a standardized interface:

```python
class OmicsModuleBase(ABC):
    def load_data(self, source) -> OmicsData
    def preprocess(self, data) -> OmicsData
    def quality_control(self, data) -> QCReport
    def normalize(self, data) -> OmicsData
    def analyze(self, data, params) -> AnalysisResult
    def visualize(self, result) -> List[Visualization]
```

## Data Sources

The suite includes collectors for 50+ public databases:
- **Genomics**: TCGA, GEO, ICGC, gnomAD, ClinVar, Ensembl, NCBI
- **Proteomics**: PRIDE, ProteomicsDB, UniProt, PDB
- **Metabolomics**: MetaboLights, HMDB, KEGG, Reactome
- **Interactions**: STRING, BioGRID, IntAct, MINT
- **Pathways**: KEGG, Reactome, WikiPathways, GO
- **Structures**: PDB, AlphaFold DB, ChEMBL
- **Single Cell**: CellxGene, HCA, scRNA-seq Atlas
- And many more...

## New Module Details

### Bioinformatics Foundation
```python
from backend.bioinformatics import DNASequence, GlobalAligner, FastaParser

# Sequence manipulation
seq = DNASequence("ATGCGATCGATCG")
print(seq.gc_content())  # 0.538
print(seq.reverse_complement())  # CGATCGATCGCAT

# Alignment
aligner = GlobalAligner()
result = aligner.align("ATGCG", "ATGCGATCG")
print(result.identity)  # 0.8
```

### Genome Assembly
```python
from backend.assembly import DeBruijnAssembler, AssemblyQC

# Assemble reads
assembler = DeBruijnAssembler(k=31)
result = assembler.assemble(reads)
print(f"N50: {result.n50}, Contigs: {result.num_contigs}")

# Quality assessment
qc = AssemblyQC()
stats = qc.evaluate(result.contigs)
```

### Computational Chemistry
```python
from backend.computational_chemistry import Molecule, MolecularDocking

# Load protein and ligand
protein = Molecule.from_pdb("protein.pdb")
ligand = Molecule.from_pdb("ligand.pdb")

# Dock ligand
docking = MolecularDocking()
poses = docking.dock(ligand, protein)
print(f"Best score: {poses[0].score.total_score}")
```

### Systems Biology
```python
from backend.systems_biology import ODEModel, SteadyStateAnalysis

# Build model
model = ODEModel("gene_regulation")
model.add_species(Species("mRNA", initial_value=0))
model.add_reaction(Reaction("transcription", ...))

# Find steady state
ss_analyzer = SteadyStateAnalysis(model)
steady_state, converged = ss_analyzer.find_steady_state()
```

## ML/AI Capabilities

- **Deep Learning**: Neural networks, CNNs, RNNs, Transformers
- **Graph Neural Networks**: GCN, GAT, GraphSAGE for biological networks
- **Traditional ML**: Random Forest, XGBoost, SVM, Elastic Net
- **AutoML**: Automated model selection and hyperparameter tuning
- **Explainability**: SHAP, LIME for model interpretation

## Multi-Omics Integration

- **Data Fusion**: Early, intermediate, and late fusion strategies
- **Network Integration**: Pathway-based and network-based integration
- **Dimensionality Reduction**: PCA, UMAP, t-SNE for integrated data
- **Biomarker Discovery**: Cross-omics biomarker identification

## Deployment

### Local Development
```bash
docker-compose up -d
```

### Production (Kubernetes)
```bash
kubectl apply -k k8s/overlays/production
# or with Helm
helm install multi-omics k8s/helm/multi-omics
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-omics-module`)
3. Commit changes (`git commit -am 'Add new omics module'`)
4. Push to branch (`git push origin feature/new-omics-module`)
5. Create a Pull Request

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Citation

If you use this software in your research, please cite:

```bibtex
@software{multi_omics_suite,
  title={Multi-Omics Analysis Suite},
  author={Boyer, Juan Valentin},
  year={2025},
  url={https://github.com/jbInf-08/multi_omics_analysis_suite}
}
```

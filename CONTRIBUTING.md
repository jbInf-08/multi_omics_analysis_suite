# Contributing to Multi-Omics Analysis Suite

Thank you for your interest in contributing to the Multi-Omics Analysis Suite! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose
- Git

### Setting Up Development Environment

1. **Fork and clone the repository:**

```bash
git clone https://github.com/YOUR_USERNAME/multi-omics-analysis-suite.git
cd multi-omics-analysis-suite
```

2. **Create a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

3. **Install dependencies:**

```bash
pip install -e ".[dev,notebooks,dash]"
```

4. **Install pre-commit hooks:**

```bash
pip install pre-commit
pre-commit install
```

5. **Start development services:**

```bash
docker-compose up -d postgres redis neo4j
```

6. **Run database migrations:**

```bash
alembic upgrade head
```

7. **Start the development server:**

```bash
uvicorn backend.app.main:app --reload
```

## Development Workflow

### Branch Naming Convention

- `feature/` - New features (e.g., `feature/add-scrnaseq-clustering`)
- `fix/` - Bug fixes (e.g., `fix/alignment-memory-leak`)
- `docs/` - Documentation updates
- `refactor/` - Code refactoring
- `test/` - Test additions or updates
- `chore/` - Maintenance tasks

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Code style (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Maintenance

**Examples:**

```
feat(genomics): add variant annotation pipeline

- Implement VEP integration
- Add ANNOVAR support
- Create annotation result schema

Closes #123
```

```
fix(alignment): resolve memory leak in BWA wrapper

The issue was caused by not closing file handles properly.
```

### Pull Request Process

1. Create a feature branch from `develop`:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/your-feature
   ```

2. Make your changes and commit following the commit message format.

3. Run tests locally:
   ```bash
   pytest tests/
   ```

4. Push your branch and create a Pull Request.

5. Ensure CI checks pass.

6. Request review from maintainers.

7. Address review feedback.

8. Once approved, your PR will be merged.

## Code Standards

### Python

- Follow [PEP 8](https://pep8.org/) style guide
- Use type hints for all functions
- Maximum line length: 100 characters
- Use docstrings for all public functions and classes

```python
def align_sequences(
    seq1: str,
    seq2: str,
    algorithm: str = "global",
) -> AlignmentResult:
    """
    Align two sequences using the specified algorithm.
    
    Args:
        seq1: First sequence to align.
        seq2: Second sequence to align.
        algorithm: Alignment algorithm ('global' or 'local').
        
    Returns:
        AlignmentResult containing aligned sequences and score.
        
    Raises:
        ValueError: If algorithm is not supported.
    """
    ...
```

### TypeScript/React

- Use TypeScript for all new code
- Follow React best practices
- Use functional components with hooks
- Use Tailwind CSS for styling

### Testing

- Write tests for all new features
- Maintain test coverage above 80%
- Use pytest fixtures for setup
- Write property-based tests for algorithms

```python
def test_gc_content_bounds():
    """GC content should always be between 0 and 1."""
    seq = DNASequence("ATGCGATCG")
    gc = seq.gc_content()
    assert 0.0 <= gc <= 1.0
```

## Adding New Omics Modules

### Module Structure

Create a new module in `backend/omics/`:

```
backend/omics/your_omics/
├── __init__.py
├── module.py       # Main module class
├── pipeline.py     # Analysis pipelines
├── analysis.py     # Analysis functions
├── utils.py        # Utility functions
└── tests/
    ├── __init__.py
    └── test_module.py
```

### Module Interface

Implement the `OmicsModuleBase` interface:

```python
from backend.omics.base.omics_base import OmicsModuleBase, OmicsData

class YourOmicsModule(OmicsModuleBase):
    """Your omics module description."""
    
    name = "your_omics"
    display_name = "Your Omics"
    category = "core"  # or specialized, clinical, etc.
    
    def load_data(self, source: str) -> OmicsData:
        """Load data from source."""
        ...
    
    def preprocess(self, data: OmicsData) -> OmicsData:
        """Preprocess the data."""
        ...
    
    def quality_control(self, data: OmicsData) -> QCReport:
        """Run quality control."""
        ...
    
    def analyze(self, data: OmicsData, params: dict) -> AnalysisResult:
        """Run analysis."""
        ...
```

### Register the Module

Add to the registry in `backend/omics/base/registry.py`:

```python
OMICS_MODULES = {
    ...
    "your_omics": "backend.omics.your_omics.module.YourOmicsModule",
}
```

## Documentation

### Writing Documentation

- Use Markdown for documentation
- Include code examples
- Document all public APIs
- Add docstrings to all functions

### API Documentation

FastAPI auto-generates OpenAPI documentation. Enhance it with:

```python
@router.post(
    "/",
    response_model=AnalysisResponse,
    summary="Create new analysis",
    description="Create and queue a new analysis job.",
    responses={
        201: {"description": "Analysis created successfully"},
        400: {"description": "Invalid parameters"},
        404: {"description": "Project not found"},
    },
)
async def create_analysis(...):
    ...
```

## Reporting Issues

### Bug Reports

Include:
- Clear description
- Steps to reproduce
- Expected vs actual behavior
- Environment details
- Relevant logs/screenshots

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternative solutions considered
- Additional context

## Getting Help

- Open an issue for questions
- Join our Slack/Discord community
- Check existing documentation

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing!

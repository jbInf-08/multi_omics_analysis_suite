"""
Pytest Configuration and Fixtures
=================================

Shared fixtures and configuration for all tests.
"""

import os
import sys
import pytest
import asyncio
import numpy as np
import pandas as pd
from typing import Generator, AsyncGenerator, Dict, Any, List
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from uuid import UUID

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Test data directory
TEST_DATA_DIR = Path(__file__).parent / "data"
SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

# JWT ``sub`` must parse as UUID in several API routes (UUID(current_user.sub)).
TEST_AUTH_USER_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")


# ============================================================================
# Event Loop Configuration
# ============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Get test database URL."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@localhost:5432/test_omics"
    )


@pytest.fixture
async def db_session(test_database_url) -> AsyncGenerator:
    """Create a test database session."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    engine = create_async_engine(test_database_url, echo=False)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()
    
    await engine.dispose()


@pytest.fixture
def mock_db_session():
    """Mock database session for unit tests."""
    session = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    exec_result.scalar.return_value = 0
    exec_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=exec_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


# ============================================================================
# Sequence Fixtures
# ============================================================================

@pytest.fixture
def sample_dna_sequences() -> Dict[str, str]:
    """Sample DNA sequences for testing."""
    return {
        "short": "ATGCGATCGATCG",
        "medium": "ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG",
        "with_start_stop": "ATGAAAGGGCCCTTTTAG",
        "gc_rich": "GCGCGCGCGCGCGCGCGCGCGCGC",
        "at_rich": "ATATATATATATATATATATAT",
        "with_n": "ATGCNNNGATCG",
        "palindrome": "GAATTC",  # EcoRI site
        "promoter_like": "TATAATGCGATCGATCGATCG",
    }


@pytest.fixture
def sample_protein_sequences() -> Dict[str, str]:
    """Sample protein sequences for testing."""
    return {
        "short": "MVLSPADKTNVK",
        "medium": "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSH",
        "hydrophobic": "AVILMFYW" * 5,
        "charged": "KRKRKRKRKDEDED",
        "with_signal": "MKLLFAIPLVVLSCFSGATK",  # Signal peptide-like
    }


@pytest.fixture
def sample_rna_sequence() -> str:
    """Sample RNA sequence."""
    return "AUGCGAUCGAUCGAUCGAUCGAUCGAUCGAUCGAUCGAUCGAU"


@pytest.fixture
def aligned_sequences() -> List[str]:
    """Pre-aligned sequences for consensus testing."""
    return [
        "ATGCGATCGATCG",
        "ATGCGATCGATCG",
        "ATGCGATCGATTG",
        "ATGCGATTGATCG",
    ]


@pytest.fixture
def fastq_reads() -> List[str]:
    """Simulated FASTQ reads for assembly testing."""
    # Generate overlapping reads from a reference
    reference = "ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"
    read_length = 20
    coverage = 10
    reads = []
    
    for _ in range(coverage):
        for i in range(0, len(reference) - read_length + 1, 5):
            reads.append(reference[i:i + read_length])
    
    return reads


# ============================================================================
# API Test Fixtures
# ============================================================================

@pytest.fixture
def test_client():
    """Create test client for API tests."""
    from fastapi.testclient import TestClient
    from backend.app.main import app
    
    with TestClient(app) as client:
        yield client


@pytest.fixture
async def async_test_client():
    """Create async test client for API tests."""
    from httpx import AsyncClient, ASGITransport
    from backend.app.main import app
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def auth_user_id() -> UUID:
    """Stable user id matching :func:`auth_headers` JWT ``sub``."""
    return TEST_AUTH_USER_ID


@pytest.fixture
def auth_headers() -> Dict[str, str]:
    """Generate authentication headers for API tests."""
    # Create a test JWT token
    from backend.app.core.security import create_access_token

    token = create_access_token(
        data={"sub": str(TEST_AUTH_USER_ID), "email": "test@example.com"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_current_user():
    """Mock current user for API tests."""
    from datetime import datetime, timedelta, timezone

    from backend.app.core.security import TokenPayload

    now = datetime.now(timezone.utc)
    return TokenPayload(
        sub=str(TEST_AUTH_USER_ID),
        exp=now + timedelta(hours=1),
        iat=now,
        type="access",
    )


# ============================================================================
# Analysis Fixtures
# ============================================================================

@pytest.fixture
def expression_matrix() -> pd.DataFrame:
    """Sample expression matrix for statistical testing."""
    np.random.seed(42)
    n_genes = 100
    n_samples = 20
    
    # Create expression data with some differentially expressed genes
    data = np.random.randn(n_genes, n_samples) * 2 + 10
    
    # Add differential expression to first 10 genes
    data[:10, :10] += 3  # Group 1 higher
    data[:10, 10:] -= 1  # Group 2 lower
    
    genes = [f"gene_{i}" for i in range(n_genes)]
    samples = [f"sample_{i}" for i in range(n_samples)]
    
    return pd.DataFrame(data, index=genes, columns=samples)


@pytest.fixture
def sample_groups() -> pd.Series:
    """Sample group labels for statistical testing."""
    groups = ["control"] * 10 + ["treatment"] * 10
    return pd.Series(groups, index=[f"sample_{i}" for i in range(20)])


@pytest.fixture
def vcf_variant_data() -> Dict[str, Any]:
    """Sample VCF variant data for testing."""
    return {
        "chrom": "chr1",
        "pos": 12345,
        "id": "rs123456",
        "ref": "A",
        "alt": ["G"],
        "qual": 100.0,
        "filter": "PASS",
        "info": {"DP": 50, "AF": 0.5},
        "format": ["GT", "DP", "GQ"],
        "samples": {
            "sample1": {"GT": "0/1", "DP": 30, "GQ": 99},
            "sample2": {"GT": "1/1", "DP": 25, "GQ": 95},
        }
    }


# ============================================================================
# ML Fixtures
# ============================================================================

@pytest.fixture
def classification_dataset():
    """Sample dataset for ML classification testing."""
    np.random.seed(42)
    n_samples = 200
    n_features = 50
    
    X = np.random.randn(n_samples, n_features)
    y = (X[:, 0] + X[:, 1] > 0).astype(int)
    
    feature_names = [f"feature_{i}" for i in range(n_features)]
    
    return X, y, feature_names


@pytest.fixture
def regression_dataset():
    """Sample dataset for ML regression testing."""
    np.random.seed(42)
    n_samples = 200
    n_features = 50
    
    X = np.random.randn(n_samples, n_features)
    y = X[:, 0] * 2 + X[:, 1] * 3 + np.random.randn(n_samples) * 0.1
    
    return X, y


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def temp_data_dir(tmp_path) -> Path:
    """Create temporary data directory for tests."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def sample_fasta_file(temp_data_dir) -> Path:
    """Create a sample FASTA file."""
    fasta_content = """>seq1 Test sequence 1
ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG
>seq2 Test sequence 2
GCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAGCTAG
>seq3 Test sequence 3
TTTTAAAACCCCGGGGTTTTAAAACCCCGGGGTTTTAAAACCCCGGGG
"""
    fasta_path = temp_data_dir / "test.fasta"
    fasta_path.write_text(fasta_content)
    return fasta_path


@pytest.fixture
def sample_fastq_file(temp_data_dir) -> Path:
    """Create a sample FASTQ file."""
    fastq_content = """@read1
ATGCGATCGATCGATCGATCG
+
IIIIIIIIIIIIIIIIIIIII
@read2
GCTAGCTAGCTAGCTAGCTAG
+
IIIIIIIIIIIIIIIIIIIII
@read3
TTTTAAAACCCCGGGGTTTT
+
IIIIIIIIIIIIIIIIIIII
"""
    fastq_path = temp_data_dir / "test.fastq"
    fastq_path.write_text(fastq_content)
    return fastq_path


# ============================================================================
# Snapshot Configuration
# ============================================================================

@pytest.fixture
def snapshot_dir() -> Path:
    """Get snapshot directory path."""
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    return SNAPSHOT_DIR


# ============================================================================
# Celery Fixtures
# ============================================================================

@pytest.fixture
def celery_config():
    """Celery configuration for testing."""
    return {
        "broker_url": "memory://",
        "result_backend": "cache+memory://",
        "task_always_eager": True,
        "task_eager_propagates": True,
    }


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for unit tests."""
    task = MagicMock()
    task.delay = MagicMock(return_value=MagicMock(id="test-task-id"))
    task.apply_async = MagicMock(return_value=MagicMock(id="test-task-id"))
    return task


# ============================================================================
# Utility Functions
# ============================================================================

def generate_random_dna(length: int, gc_content: float = 0.5) -> str:
    """Generate random DNA sequence with specified GC content."""
    np.random.seed(None)
    gc_count = int(length * gc_content)
    at_count = length - gc_count
    
    bases = (
        ["G"] * (gc_count // 2) +
        ["C"] * (gc_count - gc_count // 2) +
        ["A"] * (at_count // 2) +
        ["T"] * (at_count - at_count // 2)
    )
    np.random.shuffle(bases)
    return "".join(bases)


def generate_random_protein(length: int) -> str:
    """Generate random protein sequence."""
    amino_acids = "ACDEFGHIKLMNPQRSTVWY"
    return "".join(np.random.choice(list(amino_acids), length))


# Make utility functions available as fixtures
@pytest.fixture
def random_dna_generator():
    """Fixture providing random DNA generator function."""
    return generate_random_dna


@pytest.fixture
def random_protein_generator():
    """Fixture providing random protein generator function."""
    return generate_random_protein

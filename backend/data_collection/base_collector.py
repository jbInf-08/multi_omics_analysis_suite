"""
Base Collector Module
=====================

Base classes and utilities for data collection with API authentication support.
"""

import asyncio
import aiohttp
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pandas as pd
import json
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


def get_api_key(source_name: str, key_suffix: str = "API_KEY") -> Optional[str]:
    """
    Get API key from environment variables.
    
    Args:
        source_name: Data source name (e.g., "COSMIC", "ONCOKB")
        key_suffix: Key suffix (default "API_KEY", could be "API_TOKEN", etc.)
    
    Returns:
        API key string or None if not set
    """
    # Try different naming conventions
    env_names = [
        f"{source_name.upper()}_{key_suffix}",
        f"{source_name.upper()}_TOKEN",
        f"{source_name.upper()}_KEY",
    ]
    
    for env_name in env_names:
        key = os.environ.get(env_name)
        if key:
            return key
    
    return None


# Mapping of data sources to their environment variable names
API_KEY_MAPPING = {
    "cosmic": "COSMIC_API_KEY",
    "oncokb": "ONCOKB_API_TOKEN",
    "drugbank": "DRUGBANK_API_KEY",
    "depmap": "DEPMAP_API_KEY",
    "ccle": "DEPMAP_API_KEY",
    "cbioportal": "CBIOPORTAL_API_KEY",
    "civic": "CIVIC_API_KEY",
    "pharmgkb": "PHARMGKB_API_KEY",
    "string": "STRING_API_KEY",
    "tcia": "TCIA_API_KEY",
    "ncbi": "NCBI_API_KEY",
}


logger = logging.getLogger(__name__)


class DataSource(str, Enum):
    """Available data sources."""
    # Genomic & Expression
    TCGA = "tcga"
    GEO = "geo"
    ICGC = "icgc"
    GDC = "gdc"
    EGA = "ega"
    ENCODE = "encode"
    GTEX = "gtex"
    CCLE = "ccle"
    DEPMAP = "depmap"
    CPTAC = "cptac"
    TARGET = "target"
    
    # Mutation & Variant
    COSMIC = "cosmic"
    CLINVAR = "clinvar"
    GNOMAD = "gnomad"
    DBSNP = "dbsnp"
    ONCOKB = "oncokb"
    CIVIC = "civic"
    
    # Protein & Interaction
    UNIPROT = "uniprot"
    STRING = "string"
    BIOGRID = "biogrid"
    INTACT = "intact"
    PDB = "pdb"
    ALPHAFOLD = "alphafold"
    
    # Pathway & Ontology
    KEGG = "kegg"
    REACTOME = "reactome"
    GO = "gene_ontology"
    MSIGDB = "msigdb"
    WIKIPATHWAYS = "wikipathways"
    
    # Drug & Pharmacology
    DRUGBANK = "drugbank"
    CHEMBL = "chembl"
    PHARMGKB = "pharmgkb"
    DGI = "dgi"
    GDSC = "gdsc"
    PRISM = "prism"
    
    # Clinical & Registry
    SEER = "seer"
    NCDB = "ncdb"
    CDC = "cdc"
    WHO = "who"
    
    # Imaging
    TCIA = "tcia"
    MICCAI = "miccai"
    BRATS = "brats"
    CAMELYON = "camelyon"
    LIDC_IDRI = "lidc_idri"
    
    # Literature
    PUBMED = "pubmed"
    PMC = "pmc"
    EUROPEPMC = "europepmc"
    SCOPUS = "scopus"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    
    # Other
    CBIOPORTAL = "cbioportal"
    UCSC = "ucsc"
    ENSEMBL = "ensembl"
    NCBI = "ncbi"
    MYGENE = "mygene"
    BIOMART = "biomart"


@dataclass
class CollectorConfig:
    """Configuration for a data collector."""
    source: DataSource
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    rate_limit: int = 10  # requests per second
    timeout: int = 60  # seconds
    max_retries: int = 3
    retry_delay: float = 1.0
    cache_enabled: bool = True
    cache_ttl: int = 86400  # 24 hours
    output_dir: Optional[Path] = None
    parallel_downloads: int = 5
    verify_ssl: bool = True
    proxy: Optional[str] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class CollectionResult:
    """Result from a data collection operation."""
    source: DataSource
    success: bool
    data: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    records_collected: int = 0
    bytes_downloaded: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0


class BaseCollector(ABC):
    """
    Abstract base class for all data collectors.
    
    Provides common functionality for API access, rate limiting,
    error handling, and data validation.
    """
    
    # Override in subclass to specify the authentication header name
    auth_header_name: str = "Authorization"
    auth_header_prefix: str = "Bearer"  # e.g., "Bearer", "Token", "Basic", or ""
    
    def __init__(self, config: Optional[CollectorConfig] = None):
        """
        Initialize base collector.
        
        Args:
            config: Collector configuration
        """
        self.config = config or CollectorConfig(source=self.source)
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = asyncio.Semaphore(self.config.rate_limit)
        self._request_times: List[float] = []
        
        # Auto-load API key from environment if not provided
        if not self.config.api_key:
            self.config.api_key = self._load_api_key()
    
    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment variables."""
        source_name = self.source.value.lower()
        
        # Check mapping first
        if source_name in API_KEY_MAPPING:
            env_var = API_KEY_MAPPING[source_name]
            key = os.environ.get(env_var)
            if key:
                logger.debug(f"Loaded API key for {source_name} from {env_var}")
                return key
        
        # Fall back to generic pattern
        return get_api_key(source_name)
    
    @property
    def has_api_key(self) -> bool:
        """Check if API key is configured."""
        return bool(self.config.api_key)
    
    @property
    def requires_auth(self) -> bool:
        """
        Override in subclass to indicate if authentication is required.
        Default is False (public API).
        """
        return False
    
    @property
    @abstractmethod
    def source(self) -> DataSource:
        """Return the data source for this collector."""
        pass
    
    @property
    @abstractmethod
    def base_url(self) -> str:
        """Return the base API URL."""
        pass
    
    @abstractmethod
    async def collect(self, **kwargs) -> CollectionResult:
        """
        Collect data from the source.
        
        Args:
            **kwargs: Collection parameters
            
        Returns:
            CollectionResult
        """
        pass
    
    def _get_auth_header(self) -> Dict[str, str]:
        """Get authentication header based on configuration."""
        if not self.config.api_key:
            return {}
        
        if self.auth_header_prefix:
            return {self.auth_header_name: f"{self.auth_header_prefix} {self.config.api_key}"}
        else:
            return {self.auth_header_name: self.config.api_key}
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {
                "User-Agent": "MultiOmicsAnalysisSuite/1.0",
                "Accept": "application/json",
                **self.config.custom_headers,
                **self._get_auth_header(),
            }
            
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            connector = aiohttp.TCPConnector(
                ssl=self.config.verify_ssl,
                limit=self.config.parallel_downloads,
            )
            
            self._session = aiohttp.ClientSession(
                headers=headers,
                timeout=timeout,
                connector=connector,
            )
        
        return self._session
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make an HTTP request with rate limiting and retries.
        
        Args:
            method: HTTP method
            url: Request URL
            params: Query parameters
            data: Form data
            json_data: JSON body
            
        Returns:
            Response data
        """
        async with self._rate_limiter:
            session = await self._get_session()
            
            async with session.request(
                method, url, params=params, data=data, json=json_data
            ) as response:
                response.raise_for_status()
                
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    return await response.json()
                else:
                    return {"content": await response.text()}
    
    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make GET request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        return await self._request("GET", url, params=params)
    
    async def _post(
        self, endpoint: str, data: Optional[Dict] = None, json_data: Optional[Dict] = None
    ) -> Dict:
        """Make POST request."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        return await self._request("POST", url, data=data, json_data=json_data)
    
    async def close(self):
        """Close the collector session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def _create_result(
        self,
        success: bool,
        data: Any = None,
        errors: List[str] = None,
        records: int = 0,
        start_time: datetime = None,
    ) -> CollectionResult:
        """Create a standardized collection result."""
        end_time = utc_now()
        duration = (end_time - start_time).total_seconds() if start_time else 0
        
        return CollectionResult(
            source=self.source,
            success=success,
            data=data,
            errors=errors or [],
            records_collected=records,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
        )
    
    def validate_data(self, data: Any) -> bool:
        """Validate collected data."""
        if data is None:
            return False
        if isinstance(data, pd.DataFrame):
            return not data.empty
        if isinstance(data, (list, dict)):
            return len(data) > 0
        return True


class CollectorRegistry:
    """Registry for data collectors."""
    
    _collectors: Dict[DataSource, type] = {}
    
    @classmethod
    def register(cls, source: DataSource):
        """Decorator to register a collector."""
        def decorator(collector_class: type):
            cls._collectors[source] = collector_class
            return collector_class
        return decorator
    
    @classmethod
    def get(cls, source: DataSource) -> Optional[type]:
        """Get collector class for a source."""
        return cls._collectors.get(source)
    
    @classmethod
    def list_sources(cls) -> List[DataSource]:
        """List all registered sources."""
        return list(cls._collectors.keys())
    
    @classmethod
    def create(
        cls, source: DataSource, config: Optional[CollectorConfig] = None
    ) -> Optional[BaseCollector]:
        """Create a collector instance."""
        collector_class = cls.get(source)
        if collector_class:
            return collector_class(config)
        return None

"""
Literature & Publication Collectors
====================================

Collectors for literature databases: PubMed, PMC, Europe PMC, Semantic Scholar.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)

from backend.data_collection.base_collector import (
    BaseCollector,
    CollectionResult,
    DataSource,
    CollectorRegistry,
)

logger = logging.getLogger(__name__)


@CollectorRegistry.register(DataSource.PUBMED)
class PubMedCollector(BaseCollector):
    """PubMed literature database collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.PUBMED
    
    @property
    def base_url(self) -> str:
        return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def collect(
        self,
        query: Optional[str] = None,
        pmids: Optional[List[str]] = None,
        max_results: int = 100,
        **kwargs
    ) -> CollectionResult:
        """Collect PubMed articles."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if query:
                # Search PubMed
                search_result = await self._get("esearch.fcgi", params={
                    "db": "pubmed",
                    "term": query,
                    "retmax": max_results,
                    "retmode": "json",
                })
                
                pmid_list = search_result.get("esearchresult", {}).get("idlist", [])
                collected_data["search_pmids"] = pmid_list
                collected_data["total_count"] = search_result.get("esearchresult", {}).get("count", 0)
                
                # Fetch abstracts
                if pmid_list:
                    abstracts = await self._fetch_abstracts(pmid_list[:50])
                    collected_data["abstracts"] = abstracts
            
            if pmids:
                abstracts = await self._fetch_abstracts(pmids[:100])
                collected_data["requested_abstracts"] = abstracts
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data.get("search_pmids", pmids or [])),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )
    
    async def _fetch_abstracts(self, pmids: List[str]) -> Dict:
        """Fetch abstracts for PMIDs."""
        result = await self._get("efetch.fcgi", params={
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        })
        return result


@CollectorRegistry.register(DataSource.PMC)
class PMCCollector(BaseCollector):
    """PubMed Central full-text collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.PMC
    
    @property
    def base_url(self) -> str:
        return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def collect(
        self,
        query: Optional[str] = None,
        pmc_ids: Optional[List[str]] = None,
        max_results: int = 50,
        **kwargs
    ) -> CollectionResult:
        """Collect PMC full-text articles."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if query:
                search_result = await self._get("esearch.fcgi", params={
                    "db": "pmc",
                    "term": query,
                    "retmax": max_results,
                    "retmode": "json",
                })
                
                ids = search_result.get("esearchresult", {}).get("idlist", [])
                collected_data["pmc_ids"] = ids
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data.get("pmc_ids", [])),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.EUROPEPMC)
class EuropePMCCollector(BaseCollector):
    """Europe PMC literature collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.EUROPEPMC
    
    @property
    def base_url(self) -> str:
        return "https://www.ebi.ac.uk/europepmc/webservices/rest"
    
    async def collect(
        self,
        query: Optional[str] = None,
        max_results: int = 100,
        **kwargs
    ) -> CollectionResult:
        """Collect Europe PMC articles."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if query:
                result = await self._get("search", params={
                    "query": query,
                    "resultType": "core",
                    "pageSize": max_results,
                    "format": "json",
                })
                collected_data["results"] = result.get("resultList", {}).get("result", [])
                collected_data["hit_count"] = result.get("hitCount", 0)
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data.get("results", [])),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.SEMANTIC_SCHOLAR)
class SemanticScholarCollector(BaseCollector):
    """Semantic Scholar academic search collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.SEMANTIC_SCHOLAR
    
    @property
    def base_url(self) -> str:
        return "https://api.semanticscholar.org/graph/v1"
    
    async def collect(
        self,
        query: Optional[str] = None,
        paper_ids: Optional[List[str]] = None,
        max_results: int = 100,
        **kwargs
    ) -> CollectionResult:
        """Collect Semantic Scholar papers."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if query:
                result = await self._get("paper/search", params={
                    "query": query,
                    "limit": min(max_results, 100),
                    "fields": "paperId,title,abstract,authors,year,citationCount",
                })
                collected_data["papers"] = result.get("data", [])
                collected_data["total"] = result.get("total", 0)
            
            if paper_ids:
                for pid in paper_ids[:20]:
                    paper = await self._get(f"paper/{pid}", params={
                        "fields": "paperId,title,abstract,authors,year,citationCount,references",
                    })
                    collected_data[pid] = paper
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data.get("papers", [])),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.CBIOPORTAL)
class CBioPortalCollector(BaseCollector):
    """cBioPortal cancer genomics collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.CBIOPORTAL
    
    @property
    def base_url(self) -> str:
        return "https://www.cbioportal.org/api"
    
    async def collect(
        self,
        study: Optional[str] = None,
        genes: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect cBioPortal cancer genomics data."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            # Get all studies
            studies = await self._get("studies")
            collected_data["studies"] = studies
            
            if study:
                # Get study details
                study_data = await self._get(f"studies/{study}")
                collected_data["study_details"] = study_data
                
                # Get clinical data
                clinical = await self._get(f"studies/{study}/clinical-data")
                collected_data["clinical_data"] = clinical
            
            if genes and study:
                # Get mutation data for genes
                genes_str = ",".join(genes)
                mutations = await self._get(
                    f"studies/{study}/genes/{genes_str}/mutations"
                )
                collected_data["mutations"] = mutations
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data.get("studies", [])),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )

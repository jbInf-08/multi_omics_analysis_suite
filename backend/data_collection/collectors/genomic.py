"""
Genomic Data Collectors
=======================

Collectors for genomic databases: TCGA, GEO, GDC, ICGC, ENCODE, GTEx, etc.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd
import logging


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)

from backend.data_collection.base_collector import (
    BaseCollector,
    CollectorConfig,
    CollectionResult,
    DataSource,
    CollectorRegistry,
)

logger = logging.getLogger(__name__)


@CollectorRegistry.register(DataSource.TCGA)
class TCGACollector(BaseCollector):
    """TCGA (The Cancer Genome Atlas) data collector via GDC API."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.TCGA
    
    @property
    def base_url(self) -> str:
        return "https://api.gdc.cancer.gov"
    
    async def collect(
        self,
        cancer_type: Optional[str] = None,
        data_types: Optional[List[str]] = None,
        genes: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """
        Collect TCGA data.
        
        Args:
            cancer_type: Cancer type code (e.g., 'BRCA', 'LUAD')
            data_types: Data types to collect
            genes: Specific genes to query
        """
        start_time = utc_now()
        collected_data = {}
        errors = []
        
        try:
            # Build filters
            filters = {"op": "and", "content": []}
            
            if cancer_type:
                filters["content"].append({
                    "op": "=",
                    "content": {
                        "field": "cases.project.project_id",
                        "value": f"TCGA-{cancer_type}"
                    }
                })
            
            # Query cases
            cases_data = await self._get("cases", params={
                "filters": filters,
                "size": 1000,
                "fields": "case_id,submitter_id,project.project_id,demographic.gender,demographic.vital_status",
            })
            collected_data["cases"] = cases_data.get("data", {}).get("hits", [])
            
            # Query files if data types specified
            if data_types:
                for dtype in data_types:
                    files_data = await self._query_files(cancer_type, dtype)
                    collected_data[f"files_{dtype}"] = files_data
            
            # Query gene expression if genes specified
            if genes:
                expr_data = await self._query_gene_expression(genes, cancer_type)
                collected_data["gene_expression"] = expr_data
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data.get("cases", [])),
                start_time=start_time,
            )
            
        except Exception as e:
            logger.error(f"TCGA collection failed: {e}")
            return self._create_result(
                success=False,
                errors=[str(e)],
                start_time=start_time,
            )
    
    async def _query_files(self, cancer_type: str, data_type: str) -> List[Dict]:
        """Query files of a specific type."""
        filters = {
            "op": "and",
            "content": [
                {"op": "=", "content": {"field": "data_type", "value": data_type}},
            ]
        }
        if cancer_type:
            filters["content"].append({
                "op": "=",
                "content": {"field": "cases.project.project_id", "value": f"TCGA-{cancer_type}"}
            })
        
        result = await self._get("files", params={
            "filters": filters,
            "size": 1000,
        })
        return result.get("data", {}).get("hits", [])
    
    async def _query_gene_expression(
        self, genes: List[str], cancer_type: Optional[str]
    ) -> Dict:
        """Query gene expression data."""
        # Gene expression requires special handling via analysis endpoint
        return {"genes": genes, "note": "Expression data requires file download"}


@CollectorRegistry.register(DataSource.GEO)
class GEOCollector(BaseCollector):
    """GEO (Gene Expression Omnibus) data collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.GEO
    
    @property
    def base_url(self) -> str:
        return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def collect(
        self,
        accessions: Optional[List[str]] = None,
        query: Optional[str] = None,
        max_results: int = 100,
        **kwargs
    ) -> CollectionResult:
        """
        Collect GEO data.
        
        Args:
            accessions: Specific GEO accession numbers
            query: Search query
            max_results: Maximum results to return
        """
        start_time = utc_now()
        collected_data = {}
        
        try:
            if accessions:
                # Fetch specific datasets
                for acc in accessions:
                    data = await self._fetch_dataset(acc)
                    if data:
                        collected_data[acc] = data
            
            if query:
                # Search GEO
                search_results = await self._search(query, max_results)
                collected_data["search_results"] = search_results
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )
            
        except Exception as e:
            logger.error(f"GEO collection failed: {e}")
            return self._create_result(
                success=False,
                errors=[str(e)],
                start_time=start_time,
            )
    
    async def _search(self, query: str, max_results: int) -> List[Dict]:
        """Search GEO database."""
        result = await self._get("esearch.fcgi", params={
            "db": "gds",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
        })
        return result.get("esearchresult", {}).get("idlist", [])
    
    async def _fetch_dataset(self, accession: str) -> Dict:
        """Fetch a specific GEO dataset."""
        result = await self._get("esummary.fcgi", params={
            "db": "gds",
            "id": accession,
            "retmode": "json",
        })
        return result.get("result", {})


@CollectorRegistry.register(DataSource.GDC)
class GDCCollector(BaseCollector):
    """GDC (Genomic Data Commons) collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.GDC
    
    @property
    def base_url(self) -> str:
        return "https://api.gdc.cancer.gov"
    
    async def collect(
        self,
        project: Optional[str] = None,
        data_category: Optional[str] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect GDC data."""
        start_time = utc_now()
        
        try:
            # Query projects
            projects = await self._get("projects", params={"size": 100})
            
            # Query cases
            filters = {}
            if project:
                filters = {
                    "op": "=",
                    "content": {"field": "project.project_id", "value": project}
                }
            
            cases = await self._get("cases", params={
                "filters": filters,
                "size": 1000,
            })
            
            return self._create_result(
                success=True,
                data={
                    "projects": projects.get("data", {}).get("hits", []),
                    "cases": cases.get("data", {}).get("hits", []),
                },
                records=len(cases.get("data", {}).get("hits", [])),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.ICGC)
class ICGCCollector(BaseCollector):
    """ICGC (International Cancer Genome Consortium) collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.ICGC
    
    @property
    def base_url(self) -> str:
        return "https://dcc.icgc.org/api/v1"
    
    async def collect(
        self,
        cancer_type: Optional[str] = None,
        donor_ids: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect ICGC data."""
        start_time = utc_now()
        
        try:
            # Get projects
            projects = await self._get("projects")
            
            # Get donors
            params = {"size": 1000}
            if cancer_type:
                params["filters"] = {"project": {"primarySite": {"is": cancer_type}}}
            
            donors = await self._get("donors", params=params)
            
            return self._create_result(
                success=True,
                data={"projects": projects, "donors": donors},
                records=len(donors.get("hits", [])),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.ENCODE)
class ENCODECollector(BaseCollector):
    """ENCODE project data collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.ENCODE
    
    @property
    def base_url(self) -> str:
        return "https://www.encodeproject.org"
    
    async def collect(
        self,
        assay_type: Optional[str] = None,
        biosample: Optional[str] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect ENCODE data."""
        start_time = utc_now()
        
        try:
            params = {
                "type": "Experiment",
                "format": "json",
                "limit": 1000,
            }
            if assay_type:
                params["assay_term_name"] = assay_type
            if biosample:
                params["biosample_ontology.term_name"] = biosample
            
            result = await self._get("search/", params=params)
            
            return self._create_result(
                success=True,
                data=result.get("@graph", []),
                records=result.get("total", 0),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.GTEX)
class GTExCollector(BaseCollector):
    """GTEx (Genotype-Tissue Expression) collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.GTEX
    
    @property
    def base_url(self) -> str:
        return "https://gtexportal.org/api/v2"
    
    async def collect(
        self,
        genes: Optional[List[str]] = None,
        tissues: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect GTEx expression data."""
        start_time = utc_now()
        
        try:
            collected_data = {}
            
            # Get tissues
            tissues_data = await self._get("dataset/tissueInfo")
            collected_data["tissues"] = tissues_data
            
            # Get expression if genes specified
            if genes:
                for gene in genes[:10]:  # Limit to avoid rate limiting
                    expr = await self._get(f"expression/medianGeneExpression", params={
                        "geneId": gene,
                    })
                    collected_data[f"expression_{gene}"] = expr
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.CCLE)
class CCLECollector(BaseCollector):
    """
    CCLE (Cancer Cell Line Encyclopedia) collector via DepMap.
    
    Requires API key from https://depmap.org/portal/
    Set DEPMAP_API_KEY environment variable.
    
    Note: Many DepMap endpoints are public, but some require authentication.
    """
    
    auth_header_name = "Authorization"
    auth_header_prefix = "Bearer"
    
    @property
    def source(self) -> DataSource:
        return DataSource.CCLE
    
    @property
    def base_url(self) -> str:
        return "https://depmap.org/portal/api"
    
    @property
    def requires_auth(self) -> bool:
        return False  # Many endpoints are public
    
    async def collect(
        self,
        cell_lines: Optional[List[str]] = None,
        genes: Optional[List[str]] = None,
        data_type: str = "expression",
        **kwargs
    ) -> CollectionResult:
        """
        Collect CCLE cell line data.
        
        Args:
            cell_lines: Cell line names or DepMap IDs
            genes: Gene symbols to filter
            data_type: Type of data (expression, mutations, cn)
        """
        start_time = utc_now()
        collected_data = {}
        errors = []
        
        try:
            # Get available cell lines
            try:
                cell_line_info = await self._get("cell_line")
                collected_data["cell_lines"] = cell_line_info
            except Exception as e:
                errors.append(f"Failed to fetch cell lines: {str(e)}")
            
            # Get datasets info
            try:
                datasets = await self._get("datasets")
                collected_data["datasets"] = datasets
            except Exception as e:
                errors.append(f"Failed to fetch datasets: {str(e)}")
            
            # Query specific data if authenticated
            if self.has_api_key and genes:
                for gene in genes[:10]:
                    try:
                        if data_type == "expression":
                            result = await self._get(f"expression/gene/{gene}")
                        elif data_type == "mutations":
                            result = await self._get(f"mutations/gene/{gene}")
                        elif data_type == "cn":
                            result = await self._get(f"copy_number/gene/{gene}")
                        else:
                            result = await self._get(f"data/gene/{gene}")
                        collected_data[f"{data_type}_{gene}"] = result
                    except Exception as e:
                        errors.append(f"Failed to fetch {gene} {data_type}: {str(e)}")
            
            # Query specific cell lines
            if cell_lines:
                for cl in cell_lines[:10]:
                    try:
                        result = await self._get(f"cell_line/{cl}")
                        collected_data[f"cell_line_{cl}"] = result
                    except Exception as e:
                        errors.append(f"Failed to fetch cell line {cl}: {str(e)}")
            
            if not collected_data and not self.has_api_key:
                collected_data["note"] = "Set DEPMAP_API_KEY for full access"
            
            return self._create_result(
                success=len(collected_data) > 0,
                data=collected_data,
                errors=errors,
                records=len(collected_data),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )
    
    async def get_dependency_scores(self, gene: str) -> Dict:
        """Get CRISPR dependency scores for a gene."""
        return await self._get(f"dependency/gene/{gene}")
    
    async def get_drug_sensitivity(self, drug: str) -> Dict:
        """Get drug sensitivity data."""
        return await self._get(f"compound/{drug}/sensitivity")


@CollectorRegistry.register(DataSource.ENSEMBL)
class EnsemblCollector(BaseCollector):
    """Ensembl genome browser collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.ENSEMBL
    
    @property
    def base_url(self) -> str:
        return "https://rest.ensembl.org"
    
    async def collect(
        self,
        genes: Optional[List[str]] = None,
        species: str = "human",
        **kwargs
    ) -> CollectionResult:
        """Collect Ensembl gene annotations."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if genes:
                for gene in genes[:20]:
                    gene_data = await self._get(
                        f"lookup/symbol/{species}/{gene}",
                        params={"expand": 1}
                    )
                    collected_data[gene] = gene_data
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.CPTAC)
class CPTACCollector(BaseCollector):
    """
    CPTAC (Clinical Proteomic Tumor Analysis Consortium) collector.
    
    Uses the Proteomic Data Commons (PDC) API for data access.
    Most endpoints are public, but some may require dbGaP authorization.
    """
    
    @property
    def source(self) -> DataSource:
        return DataSource.CPTAC
    
    @property
    def base_url(self) -> str:
        return "https://pdc.cancer.gov/graphql"
    
    @property
    def requires_auth(self) -> bool:
        return False  # Public API
    
    async def collect(
        self,
        cancer_type: Optional[str] = None,
        genes: Optional[List[str]] = None,
        study_id: Optional[str] = None,
        **kwargs
    ) -> CollectionResult:
        """
        Collect CPTAC proteomics data via PDC API.
        
        Args:
            cancer_type: Cancer type (e.g., "Breast", "Lung")
            genes: Gene symbols to query
            study_id: Specific study ID
        """
        start_time = utc_now()
        collected_data = {}
        errors = []
        
        try:
            # Get available studies
            studies_query = """
            query {
                allStudies {
                    study_id
                    study_name
                    program_name
                    disease_type
                    primary_site
                    cases_count
                    analytical_fraction
                }
            }
            """
            
            try:
                result = await self._post("", json_data={"query": studies_query})
                studies = result.get("data", {}).get("allStudies", [])
                
                # Filter by cancer type if specified
                if cancer_type:
                    studies = [
                        s for s in studies 
                        if cancer_type.lower() in str(s.get("disease_type", "")).lower()
                        or cancer_type.lower() in str(s.get("primary_site", "")).lower()
                    ]
                
                collected_data["studies"] = studies
            except Exception as e:
                errors.append(f"Failed to fetch studies: {str(e)}")
            
            # Get gene-level data if genes specified
            if genes:
                for gene in genes[:10]:
                    gene_query = f"""
                    query {{
                        geneSpectralCount(gene_name: "{gene}") {{
                            gene_name
                            ncbi_gene_id
                            spectral_counts {{
                                study_id
                                aliquot_id
                                spectral_count
                            }}
                        }}
                    }}
                    """
                    try:
                        result = await self._post("", json_data={"query": gene_query})
                        collected_data[f"gene_{gene}"] = result.get("data", {})
                    except Exception as e:
                        errors.append(f"Failed to fetch gene {gene}: {str(e)}")
            
            # Get specific study data
            if study_id:
                study_query = f"""
                query {{
                    study(study_id: "{study_id}") {{
                        study_id
                        study_name
                        program_name
                        cases {{
                            case_id
                            demographics {{
                                gender
                                race
                                ethnicity
                            }}
                            diagnoses {{
                                tissue_or_organ_of_origin
                                primary_diagnosis
                                tumor_stage
                                tumor_grade
                            }}
                        }}
                    }}
                }}
                """
                try:
                    result = await self._post("", json_data={"query": study_query})
                    collected_data["study_details"] = result.get("data", {})
                except Exception as e:
                    errors.append(f"Failed to fetch study {study_id}: {str(e)}")
            
            return self._create_result(
                success=len(collected_data) > 0,
                data=collected_data,
                errors=errors,
                records=len(collected_data.get("studies", [])),
                start_time=start_time,
            )
            
        except Exception as e:
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )
    
    async def get_protein_abundance(self, study_id: str, gene: str) -> Dict:
        """Get protein abundance data for a gene in a study."""
        query = f"""
        query {{
            proteinAbundance(study_id: "{study_id}", gene_name: "{gene}") {{
                gene_name
                protein_abundance
                aliquot_id
            }}
        }}
        """
        result = await self._post("", json_data={"query": query})
        return result.get("data", {})

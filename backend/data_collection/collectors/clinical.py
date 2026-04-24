"""
Clinical Data Collectors
========================

Collectors for clinical databases: COSMIC, ClinVar, OncoKB, CIViC, etc.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
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


@CollectorRegistry.register(DataSource.COSMIC)
class COSMICCollector(BaseCollector):
    """
    COSMIC (Catalogue of Somatic Mutations in Cancer) collector.
    
    Requires API key from https://cancer.sanger.ac.uk/cosmic/register
    Set COSMIC_API_KEY environment variable.
    """
    
    auth_header_name = "Authorization"
    auth_header_prefix = "Basic"  # COSMIC uses Basic auth
    
    @property
    def source(self) -> DataSource:
        return DataSource.COSMIC
    
    @property
    def base_url(self) -> str:
        return "https://cancer.sanger.ac.uk/cosmic/api/v3.5"
    
    @property
    def requires_auth(self) -> bool:
        return True
    
    def _get_auth_header(self) -> Dict[str, str]:
        """COSMIC uses email:key encoded in base64 for Basic auth."""
        if not self.config.api_key:
            return {}
        
        import base64
        email = os.environ.get("COSMIC_EMAIL", "")
        credentials = f"{email}:{self.config.api_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    
    async def collect(
        self,
        genes: Optional[List[str]] = None,
        cancer_type: Optional[str] = None,
        mutation_type: Optional[str] = None,
        **kwargs
    ) -> CollectionResult:
        """
        Collect COSMIC mutation data.
        
        Args:
            genes: List of gene symbols to query
            cancer_type: Cancer/tissue type
            mutation_type: Type of mutation
        """
        start_time = utc_now()
        collected_data = {}
        errors = []
        
        if not self.has_api_key:
            return self._create_result(
                success=False,
                errors=["COSMIC API key not configured. Set COSMIC_API_KEY and COSMIC_EMAIL environment variables."],
                start_time=start_time,
            )
        
        try:
            if genes:
                for gene in genes[:20]:
                    try:
                        mutations = await self._get_gene_mutations(gene)
                        collected_data[gene] = mutations
                    except Exception as e:
                        errors.append(f"Failed to fetch {gene}: {str(e)}")
            
            if cancer_type:
                try:
                    tissue_data = await self._get_tissue_mutations(cancer_type)
                    collected_data["tissue_mutations"] = tissue_data
                except Exception as e:
                    errors.append(f"Failed to fetch tissue {cancer_type}: {str(e)}")
            
            return self._create_result(
                success=len(collected_data) > 0,
                data=collected_data,
                errors=errors,
                records=len(collected_data),
                start_time=start_time,
            )
            
        except Exception as e:
            logger.error(f"COSMIC collection failed: {e}")
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )
    
    async def _get_gene_mutations(self, gene: str) -> Dict:
        """Get mutations for a specific gene."""
        # COSMIC API v3.5 endpoints
        result = await self._get(f"mutations/gene/{gene}")
        return result
    
    async def _get_tissue_mutations(self, tissue: str) -> Dict:
        """Get mutations for a tissue type."""
        result = await self._get(f"mutations/tissue/{tissue}")
        return result
    
    async def get_mutation_details(self, mutation_id: str) -> Dict:
        """Get detailed information about a specific mutation."""
        if not self.has_api_key:
            return {"error": "API key required"}
        return await self._get(f"mutations/{mutation_id}")


@CollectorRegistry.register(DataSource.CLINVAR)
class ClinVarCollector(BaseCollector):
    """ClinVar clinical variant collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.CLINVAR
    
    @property
    def base_url(self) -> str:
        return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def collect(
        self,
        genes: Optional[List[str]] = None,
        variants: Optional[List[str]] = None,
        conditions: Optional[List[str]] = None,
        clinical_significance: Optional[str] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect ClinVar variant data."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            # Build search query
            query_parts = []
            if genes:
                query_parts.append(" OR ".join(f"{g}[gene]" for g in genes))
            if conditions:
                query_parts.append(" OR ".join(f'"{c}"[disease]' for c in conditions))
            if clinical_significance:
                query_parts.append(f'{clinical_significance}[clinical_significance]')
            
            query = " AND ".join(f"({p})" for p in query_parts) if query_parts else "*"
            
            # Search ClinVar
            search_result = await self._get("esearch.fcgi", params={
                "db": "clinvar",
                "term": query,
                "retmax": 500,
                "retmode": "json",
            })
            
            ids = search_result.get("esearchresult", {}).get("idlist", [])
            collected_data["variant_ids"] = ids
            collected_data["total_found"] = search_result.get("esearchresult", {}).get("count", 0)
            
            # Fetch summaries for found variants
            if ids:
                summaries = await self._get("esummary.fcgi", params={
                    "db": "clinvar",
                    "id": ",".join(ids[:100]),
                    "retmode": "json",
                })
                collected_data["summaries"] = summaries.get("result", {})
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(ids),
                start_time=start_time,
            )
            
        except Exception as e:
            logger.error(f"ClinVar collection failed: {e}")
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.ONCOKB)
class OncoKBCollector(BaseCollector):
    """
    OncoKB (Precision Oncology Knowledge Base) collector.
    
    Requires API token from https://www.oncokb.org/apiAccess
    Set ONCOKB_API_TOKEN environment variable.
    """
    
    auth_header_name = "Authorization"
    auth_header_prefix = "Bearer"
    
    @property
    def source(self) -> DataSource:
        return DataSource.ONCOKB
    
    @property
    def base_url(self) -> str:
        return "https://www.oncokb.org/api/v1"
    
    @property
    def requires_auth(self) -> bool:
        return True  # Full functionality requires auth
    
    async def collect(
        self,
        genes: Optional[List[str]] = None,
        variants: Optional[List[str]] = None,
        tumor_type: Optional[str] = None,
        **kwargs
    ) -> CollectionResult:
        """
        Collect OncoKB annotation data.
        
        Args:
            genes: List of gene symbols
            variants: List of variants (e.g., "BRAF V600E")
            tumor_type: Tumor type for treatment recommendations
        """
        start_time = utc_now()
        collected_data = {}
        errors = []
        
        if not self.has_api_key:
            logger.warning("OncoKB API token not configured. Some endpoints may be restricted.")
        
        try:
            # Get all cancer genes (public endpoint)
            try:
                cancer_genes = await self._get("utils/allCuratedGenes")
                collected_data["cancer_genes"] = cancer_genes
            except Exception as e:
                errors.append(f"Failed to fetch cancer genes: {str(e)}")
            
            # Get annotations for specific genes
            if genes:
                for gene in genes[:20]:
                    try:
                        gene_info = await self._get(f"genes/{gene}")
                        collected_data[f"gene_{gene}"] = gene_info
                        
                        # Get variants for gene
                        variants_data = await self._get(f"variants/lookup", params={"hugoSymbol": gene})
                        collected_data[f"variants_{gene}"] = variants_data
                    except Exception as e:
                        errors.append(f"Failed to fetch {gene}: {str(e)}")
            
            # Annotate specific variants
            if variants:
                for variant in variants[:20]:
                    try:
                        # Parse "GENE VARIANT" format
                        parts = variant.split()
                        if len(parts) >= 2:
                            gene_symbol = parts[0]
                            alteration = " ".join(parts[1:])
                            
                            annotation = await self._get("annotate/mutations/byProteinChange", params={
                                "hugoSymbol": gene_symbol,
                                "alteration": alteration,
                                "tumorType": tumor_type or "",
                            })
                            collected_data[f"annotation_{variant}"] = annotation
                    except Exception as e:
                        errors.append(f"Failed to annotate {variant}: {str(e)}")
            
            # Get tumor type specific info
            if tumor_type:
                try:
                    tumor_info = await self._get("tumorTypes")
                    # Filter to matching tumor type
                    if isinstance(tumor_info, list):
                        matching = [t for t in tumor_info if tumor_type.lower() in str(t).lower()]
                        collected_data["tumor_types"] = matching or tumor_info[:10]
                except Exception as e:
                    errors.append(f"Failed to fetch tumor types: {str(e)}")
            
            return self._create_result(
                success=len(collected_data) > 0,
                data=collected_data,
                errors=errors,
                records=len(collected_data.get("cancer_genes", [])),
                start_time=start_time,
            )
            
        except Exception as e:
            logger.error(f"OncoKB collection failed: {e}")
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )
    
    async def annotate_variant(
        self,
        gene: str,
        variant: str,
        tumor_type: Optional[str] = None,
    ) -> Dict:
        """
        Get oncogenic annotation for a specific variant.
        
        Args:
            gene: Gene symbol (e.g., "BRAF")
            variant: Variant (e.g., "V600E")
            tumor_type: Tumor type for treatment recommendations
        
        Returns:
            Annotation data including oncogenicity and treatments
        """
        params = {
            "hugoSymbol": gene,
            "alteration": variant,
        }
        if tumor_type:
            params["tumorType"] = tumor_type
        
        return await self._get("annotate/mutations/byProteinChange", params=params)


@CollectorRegistry.register(DataSource.CIVIC)
class CIViCCollector(BaseCollector):
    """CIViC (Clinical Interpretation of Variants in Cancer) collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.CIVIC
    
    @property
    def base_url(self) -> str:
        return "https://civicdb.org/api"
    
    async def collect(
        self,
        genes: Optional[List[str]] = None,
        diseases: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect CIViC evidence data."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            # Get genes
            if genes:
                for gene in genes[:20]:
                    gene_data = await self._get(f"genes/{gene}")
                    collected_data[f"gene_{gene}"] = gene_data
            
            # Get all evidence items
            evidence = await self._get("evidence_items", params={"count": 100})
            collected_data["evidence"] = evidence
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )
            
        except Exception as e:
            logger.error(f"CIViC collection failed: {e}")
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.GNOMAD)
class GnomADCollector(BaseCollector):
    """gnomAD population variant frequency collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.GNOMAD
    
    @property
    def base_url(self) -> str:
        return "https://gnomad.broadinstitute.org/api"
    
    async def collect(
        self,
        genes: Optional[List[str]] = None,
        variants: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect gnomAD variant frequency data."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if genes:
                for gene in genes[:10]:
                    # gnomAD uses GraphQL
                    query = """
                    query($geneSymbol: String!) {
                        gene(gene_symbol: $geneSymbol, reference_genome: GRCh38) {
                            gene_id
                            symbol
                            variants(dataset: gnomad_r3) {
                                variant_id
                                pos
                                ref
                                alt
                                allele_freq
                            }
                        }
                    }
                    """
                    result = await self._post("", json_data={
                        "query": query,
                        "variables": {"geneSymbol": gene}
                    })
                    collected_data[gene] = result
            
            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )
            
        except Exception as e:
            logger.error(f"gnomAD collection failed: {e}")
            return self._create_result(
                success=False, errors=[str(e)], start_time=start_time
            )


@CollectorRegistry.register(DataSource.DBSNP)
class DbSNPCollector(BaseCollector):
    """dbSNP variant database collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.DBSNP
    
    @property
    def base_url(self) -> str:
        return "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    async def collect(
        self,
        rsids: Optional[List[str]] = None,
        genes: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect dbSNP variant data."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if rsids:
                for rsid in rsids[:50]:
                    rsid_clean = rsid.replace("rs", "")
                    result = await self._get("esummary.fcgi", params={
                        "db": "snp",
                        "id": rsid_clean,
                        "retmode": "json",
                    })
                    collected_data[rsid] = result.get("result", {})
            
            if genes:
                for gene in genes[:10]:
                    search = await self._get("esearch.fcgi", params={
                        "db": "snp",
                        "term": f"{gene}[gene]",
                        "retmax": 100,
                        "retmode": "json",
                    })
                    collected_data[f"gene_{gene}"] = search.get("esearchresult", {})
            
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

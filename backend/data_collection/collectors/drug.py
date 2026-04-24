"""
Drug & Pharmacology Collectors
==============================

Collectors for drug databases: DrugBank, ChEMBL, PharmGKB, GDSC, DGIdb.
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


@CollectorRegistry.register(DataSource.DRUGBANK)
class DrugBankCollector(BaseCollector):
    """
    DrugBank drug database collector.
    
    Requires API key from https://go.drugbank.com/
    Set DRUGBANK_API_KEY environment variable.
    
    Note: Full DrugBank API access requires a commercial license.
    Free tier has limited access.
    """
    
    auth_header_name = "Authorization"
    auth_header_prefix = "Bearer"
    
    @property
    def source(self) -> DataSource:
        return DataSource.DRUGBANK
    
    @property
    def base_url(self) -> str:
        return "https://api.drugbank.com/v1"
    
    @property
    def requires_auth(self) -> bool:
        return True
    
    async def collect(
        self,
        drug_names: Optional[List[str]] = None,
        targets: Optional[List[str]] = None,
        drugbank_ids: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """
        Collect DrugBank data.
        
        Args:
            drug_names: Drug names to search
            targets: Target protein names to search
            drugbank_ids: Specific DrugBank IDs (e.g., "DB00945")
        """
        start_time = utc_now()
        collected_data = {}
        errors = []
        
        if not self.has_api_key:
            return self._create_result(
                success=False,
                errors=["DrugBank API key not configured. Set DRUGBANK_API_KEY environment variable."],
                start_time=start_time,
            )
        
        try:
            # Search by drug names
            if drug_names:
                for drug in drug_names[:20]:
                    try:
                        result = await self._get("drugs", params={"q": drug})
                        collected_data[drug] = result
                    except Exception as e:
                        errors.append(f"Failed to search drug {drug}: {str(e)}")
            
            # Get specific drugs by ID
            if drugbank_ids:
                for db_id in drugbank_ids[:20]:
                    try:
                        result = await self._get(f"drugs/{db_id}")
                        collected_data[db_id] = result
                    except Exception as e:
                        errors.append(f"Failed to fetch {db_id}: {str(e)}")
            
            # Search by targets
            if targets:
                for target in targets[:10]:
                    try:
                        result = await self._get("targets", params={"q": target})
                        collected_data[f"target_{target}"] = result
                    except Exception as e:
                        errors.append(f"Failed to search target {target}: {str(e)}")
            
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
    
    async def get_drug_interactions(self, drugbank_id: str) -> Dict:
        """Get drug-drug interactions for a specific drug."""
        if not self.has_api_key:
            return {"error": "API key required"}
        return await self._get(f"drugs/{drugbank_id}/drug_interactions")
    
    async def get_drug_targets(self, drugbank_id: str) -> Dict:
        """Get targets for a specific drug."""
        if not self.has_api_key:
            return {"error": "API key required"}
        return await self._get(f"drugs/{drugbank_id}/targets")


@CollectorRegistry.register(DataSource.CHEMBL)
class ChEMBLCollector(BaseCollector):
    """ChEMBL bioactivity database collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.CHEMBL
    
    @property
    def base_url(self) -> str:
        return "https://www.ebi.ac.uk/chembl/api/data"
    
    async def collect(
        self,
        chembl_ids: Optional[List[str]] = None,
        targets: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect ChEMBL bioactivity data."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if chembl_ids:
                for cid in chembl_ids[:20]:
                    result = await self._get(f"molecule/{cid}.json")
                    collected_data[cid] = result
            
            if targets:
                for target in targets[:10]:
                    result = await self._get("target/search.json", params={
                        "q": target,
                    })
                    collected_data[f"target_{target}"] = result
            
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


@CollectorRegistry.register(DataSource.PHARMGKB)
class PharmGKBCollector(BaseCollector):
    """PharmGKB pharmacogenomics collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.PHARMGKB
    
    @property
    def base_url(self) -> str:
        return "https://api.pharmgkb.org/v1"
    
    async def collect(
        self,
        genes: Optional[List[str]] = None,
        drugs: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect PharmGKB pharmacogenomic data."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if genes:
                for gene in genes[:20]:
                    result = await self._get("data/gene", params={"symbol": gene})
                    collected_data[gene] = result
            
            if drugs:
                for drug in drugs[:20]:
                    result = await self._get("data/drug", params={"name": drug})
                    collected_data[f"drug_{drug}"] = result
            
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


@CollectorRegistry.register(DataSource.GDSC)
class GDSCCollector(BaseCollector):
    """GDSC (Genomics of Drug Sensitivity in Cancer) collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.GDSC
    
    @property
    def base_url(self) -> str:
        return "https://www.cancerrxgene.org/api"
    
    async def collect(
        self,
        drugs: Optional[List[str]] = None,
        cell_lines: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect GDSC drug response data."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            # Get compound list
            compounds = await self._get("compounds")
            collected_data["compounds"] = compounds
            
            # Get cell lines
            cell_lines_data = await self._get("cell_lines")
            collected_data["cell_lines"] = cell_lines_data
            
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


@CollectorRegistry.register(DataSource.DGI)
class DGIdbCollector(BaseCollector):
    """DGIdb (Drug-Gene Interaction Database) collector."""
    
    @property
    def source(self) -> DataSource:
        return DataSource.DGI
    
    @property
    def base_url(self) -> str:
        return "https://www.dgidb.org/api/v2"
    
    async def collect(
        self,
        genes: Optional[List[str]] = None,
        drugs: Optional[List[str]] = None,
        **kwargs
    ) -> CollectionResult:
        """Collect drug-gene interaction data."""
        start_time = utc_now()
        collected_data = {}
        
        try:
            if genes:
                genes_str = ",".join(genes[:50])
                result = await self._get("interactions.json", params={"genes": genes_str})
                collected_data["gene_interactions"] = result
            
            if drugs:
                drugs_str = ",".join(drugs[:50])
                result = await self._get("interactions.json", params={"drugs": drugs_str})
                collected_data["drug_interactions"] = result
            
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

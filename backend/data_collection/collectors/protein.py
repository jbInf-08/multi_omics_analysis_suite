"""Protein Data Collectors.
=======================

Collectors for protein databases: UniProt, STRING, BioGRID, PDB, AlphaFold.
"""

import logging
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


from backend.data_collection.base_collector import (
    BaseCollector,
    CollectionResult,
    CollectorRegistry,
    DataSource,
)

logger = logging.getLogger(__name__)


@CollectorRegistry.register(DataSource.UNIPROT)
class UniProtCollector(BaseCollector):
    """UniProt protein sequence and annotation collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.UNIPROT

    @property
    def base_url(self) -> str:
        return "https://rest.uniprot.org"

    async def collect(
        self,
        genes: list[str] | None = None,
        accessions: list[str] | None = None,
        organism: str = "human",
        **kwargs,
    ) -> CollectionResult:
        """Collect UniProt protein data."""
        start_time = utc_now()
        collected_data = {}

        try:
            if genes:
                for gene in genes[:20]:
                    query = f"gene:{gene} AND organism_name:{organism}"
                    result = await self._get(
                        "uniprotkb/search",
                        params={
                            "query": query,
                            "format": "json",
                            "size": 10,
                        },
                    )
                    collected_data[gene] = result.get("results", [])

            if accessions:
                for acc in accessions[:20]:
                    result = await self._get(f"uniprotkb/{acc}", params={"format": "json"})
                    collected_data[acc] = result

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)


@CollectorRegistry.register(DataSource.STRING)
class STRINGCollector(BaseCollector):
    """STRING protein-protein interaction collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.STRING

    @property
    def base_url(self) -> str:
        return "https://string-db.org/api"

    async def collect(
        self,
        genes: list[str] | None = None,
        species: int = 9606,  # Human
        score_threshold: float = 0.7,
        **kwargs,
    ) -> CollectionResult:
        """Collect STRING PPI data."""
        start_time = utc_now()
        collected_data = {}

        try:
            if genes:
                # Get interactions
                identifiers = "%0d".join(genes)
                interactions = await self._get(
                    "json/network",
                    params={
                        "identifiers": identifiers,
                        "species": species,
                        "required_score": int(score_threshold * 1000),
                    },
                )
                collected_data["interactions"] = interactions

                # Get functional enrichment
                enrichment = await self._get(
                    "json/enrichment",
                    params={
                        "identifiers": identifiers,
                        "species": species,
                    },
                )
                collected_data["enrichment"] = enrichment

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data.get("interactions", [])),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)


@CollectorRegistry.register(DataSource.BIOGRID)
class BioGRIDCollector(BaseCollector):
    """BioGRID interaction database collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.BIOGRID

    @property
    def base_url(self) -> str:
        return "https://webservice.thebiogrid.org"

    async def collect(
        self, genes: list[str] | None = None, organism: int = 9606, **kwargs
    ) -> CollectionResult:
        """Collect BioGRID interaction data."""
        start_time = utc_now()
        collected_data = {}

        try:
            if genes and self.config.api_key:
                for gene in genes[:10]:
                    result = await self._get(
                        "interactions",
                        params={
                            "accessKey": self.config.api_key,
                            "geneList": gene,
                            "taxId": organism,
                            "format": "json",
                        },
                    )
                    collected_data[gene] = result

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)


@CollectorRegistry.register(DataSource.PDB)
class PDBCollector(BaseCollector):
    """PDB protein structure collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.PDB

    @property
    def base_url(self) -> str:
        return "https://data.rcsb.org/rest/v1"

    async def collect(
        self, pdb_ids: list[str] | None = None, genes: list[str] | None = None, **kwargs
    ) -> CollectionResult:
        """Collect PDB structure data."""
        start_time = utc_now()
        collected_data = {}

        try:
            if pdb_ids:
                for pdb_id in pdb_ids[:20]:
                    result = await self._get(f"core/entry/{pdb_id}")
                    collected_data[pdb_id] = result

            if genes:
                # Search for structures by gene
                for gene in genes[:10]:
                    search_result = await self._post(
                        "https://search.rcsb.org/rcsbsearch/v2/query",
                        json_data={
                            "query": {
                                "type": "terminal",
                                "service": "text",
                                "parameters": {
                                    "attribute": "rcsb_entity_source_organism.rcsb_gene_name.value",
                                    "operator": "exact_match",
                                    "value": gene,
                                },
                            },
                            "return_type": "entry",
                        },
                    )
                    collected_data[f"gene_{gene}"] = search_result

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)


@CollectorRegistry.register(DataSource.ALPHAFOLD)
class AlphaFoldCollector(BaseCollector):
    """AlphaFold protein structure prediction collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.ALPHAFOLD

    @property
    def base_url(self) -> str:
        return "https://alphafold.ebi.ac.uk/api"

    async def collect(self, uniprot_ids: list[str] | None = None, **kwargs) -> CollectionResult:
        """Collect AlphaFold predicted structures."""
        start_time = utc_now()
        collected_data = {}

        try:
            if uniprot_ids:
                for uid in uniprot_ids[:20]:
                    result = await self._get(f"prediction/{uid}")
                    collected_data[uid] = result

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)

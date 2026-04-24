"""Pathway Data Collectors.
=======================

Collectors for pathway databases: KEGG, Reactome, GO, MSigDB, WikiPathways.
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


@CollectorRegistry.register(DataSource.KEGG)
class KEGGCollector(BaseCollector):
    """KEGG pathway database collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.KEGG

    @property
    def base_url(self) -> str:
        return "https://rest.kegg.jp"

    async def collect(
        self,
        pathway_ids: list[str] | None = None,
        genes: list[str] | None = None,
        organism: str = "hsa",
        **kwargs,
    ) -> CollectionResult:
        """Collect KEGG pathway data."""
        start_time = utc_now()
        collected_data = {}

        try:
            # Get pathway list
            pathways = await self._get(f"list/pathway/{organism}")
            collected_data["pathway_list"] = pathways.get("content", "")

            if pathway_ids:
                for pid in pathway_ids[:20]:
                    pathway_data = await self._get(f"get/{pid}")
                    collected_data[pid] = pathway_data.get("content", "")

            if genes:
                for gene in genes[:10]:
                    gene_pathways = await self._get(f"link/pathway/{organism}:{gene}")
                    collected_data[f"gene_{gene}"] = gene_pathways.get("content", "")

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)


@CollectorRegistry.register(DataSource.REACTOME)
class ReactomeCollector(BaseCollector):
    """Reactome pathway database collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.REACTOME

    @property
    def base_url(self) -> str:
        return "https://reactome.org/ContentService"

    async def collect(
        self,
        pathway_ids: list[str] | None = None,
        genes: list[str] | None = None,
        species: str = "Homo sapiens",
        **kwargs,
    ) -> CollectionResult:
        """Collect Reactome pathway data."""
        start_time = utc_now()
        collected_data = {}

        try:
            # Get top-level pathways
            top_pathways = await self._get(f"data/pathways/top/{species}")
            collected_data["top_pathways"] = top_pathways

            if pathway_ids:
                for pid in pathway_ids[:20]:
                    pathway = await self._get(f"data/pathway/{pid}/containedEvents")
                    collected_data[pid] = pathway

            if genes:
                for gene in genes[:10]:
                    # Map gene to pathways
                    mapping = await self._get(f"data/mapping/symbol/{gene}")
                    collected_data[f"gene_{gene}"] = mapping

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)


@CollectorRegistry.register(DataSource.GO)
class GeneOntologyCollector(BaseCollector):
    """Gene Ontology collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.GO

    @property
    def base_url(self) -> str:
        return "https://api.geneontology.org/api"

    async def collect(
        self, genes: list[str] | None = None, go_terms: list[str] | None = None, **kwargs
    ) -> CollectionResult:
        """Collect Gene Ontology data."""
        start_time = utc_now()
        collected_data = {}

        try:
            if genes:
                for gene in genes[:20]:
                    annotations = await self._get(
                        "bioentity/gene",
                        params={
                            "id": gene,
                            "rows": 100,
                        },
                    )
                    collected_data[gene] = annotations

            if go_terms:
                for term in go_terms[:20]:
                    term_data = await self._get(f"ontology/term/{term}")
                    collected_data[term] = term_data

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)


@CollectorRegistry.register(DataSource.MSIGDB)
class MSigDBCollector(BaseCollector):
    """MSigDB gene set database collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.MSIGDB

    @property
    def base_url(self) -> str:
        return "https://www.gsea-msigdb.org/gsea/msigdb/human"

    async def collect(
        self, collections: list[str] | None = None, gene_sets: list[str] | None = None, **kwargs
    ) -> CollectionResult:
        """Collect MSigDB gene sets."""
        start_time = utc_now()

        try:
            # MSigDB requires download of GMT files
            # This provides metadata about available collections
            collected_data = {
                "collections": [
                    "H (hallmark)",
                    "C1 (positional)",
                    "C2 (curated)",
                    "C3 (regulatory)",
                    "C4 (computational)",
                    "C5 (ontology)",
                    "C6 (oncogenic)",
                    "C7 (immunologic)",
                    "C8 (cell type)",
                ],
                "note": "Full gene sets require GMT file download",
            }

            return self._create_result(
                success=True,
                data=collected_data,
                records=0,
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)


@CollectorRegistry.register(DataSource.WIKIPATHWAYS)
class WikiPathwaysCollector(BaseCollector):
    """WikiPathways collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.WIKIPATHWAYS

    @property
    def base_url(self) -> str:
        return "https://webservice.wikipathways.org"

    async def collect(
        self,
        pathway_ids: list[str] | None = None,
        genes: list[str] | None = None,
        organism: str = "Homo sapiens",
        **kwargs,
    ) -> CollectionResult:
        """Collect WikiPathways data."""
        start_time = utc_now()
        collected_data = {}

        try:
            # List pathways
            pathways = await self._get(
                "listPathways",
                params={
                    "organism": organism,
                    "format": "json",
                },
            )
            collected_data["pathways"] = pathways

            if pathway_ids:
                for pid in pathway_ids[:10]:
                    pathway = await self._get(
                        "getPathway",
                        params={
                            "pwId": pid,
                            "format": "json",
                        },
                    )
                    collected_data[pid] = pathway

            if genes:
                for gene in genes[:10]:
                    results = await self._get(
                        "findPathwaysByXref",
                        params={
                            "ids": gene,
                            "codes": "H",
                            "format": "json",
                        },
                    )
                    collected_data[f"gene_{gene}"] = results

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)

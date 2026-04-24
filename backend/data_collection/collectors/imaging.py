"""Imaging Data Collectors.
=======================

Collectors for medical imaging databases: TCIA, MICCAI datasets, BraTS, etc.
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


@CollectorRegistry.register(DataSource.TCIA)
class TCIACollector(BaseCollector):
    """TCIA (The Cancer Imaging Archive) collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.TCIA

    @property
    def base_url(self) -> str:
        return "https://services.cancerimagingarchive.net/services/v4/TCIA"

    async def collect(
        self,
        collection: str | None = None,
        modality: str | None = None,
        body_part: str | None = None,
        **kwargs,
    ) -> CollectionResult:
        """Collect TCIA imaging metadata."""
        start_time = utc_now()
        collected_data = {}

        try:
            # Get collections
            collections = await self._get("getCollectionValues", params={"format": "json"})
            collected_data["collections"] = collections

            if collection:
                # Get patients in collection
                patients = await self._get(
                    "getPatient",
                    params={
                        "Collection": collection,
                        "format": "json",
                    },
                )
                collected_data["patients"] = patients

                # Get series
                series = await self._get(
                    "getSeries",
                    params={
                        "Collection": collection,
                        "format": "json",
                    },
                )
                collected_data["series"] = series

            if modality:
                modality_data = await self._get(
                    "getModalityValues",
                    params={
                        "Modality": modality,
                        "format": "json",
                    },
                )
                collected_data["modality_info"] = modality_data

            return self._create_result(
                success=True,
                data=collected_data,
                records=len(collected_data),
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)


@CollectorRegistry.register(DataSource.BRATS)
class BraTSCollector(BaseCollector):
    """BraTS (Brain Tumor Segmentation) challenge data collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.BRATS

    @property
    def base_url(self) -> str:
        """Human-facing BraTS landing page on Sage Synapse (not a REST root)."""
        return "https://www.synapse.org/#!Synapse:syn51514105"

    async def collect(self, **kwargs) -> CollectionResult:
        """Collect BraTS dataset metadata."""
        start_time = utc_now()

        # BraTS data requires Synapse account and download
        collected_data = {
            "dataset": "BraTS",
            "description": "Brain Tumor Segmentation Challenge",
            "modalities": ["T1", "T1Gd", "T2", "FLAIR"],
            "note": "Full dataset requires Synapse registration and download",
            "access_url": "https://www.synapse.org/#!Synapse:syn51514105",
        }

        return self._create_result(
            success=True,
            data=collected_data,
            records=0,
            start_time=start_time,
        )


@CollectorRegistry.register(DataSource.CAMELYON)
class CamelyonCollector(BaseCollector):
    """Camelyon pathology challenge data collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.CAMELYON

    @property
    def base_url(self) -> str:
        """Grand Challenge public API root for programmatic access where enabled."""
        return "https://grand-challenge.org/api/v2/"

    async def collect(self, **kwargs) -> CollectionResult:
        """Collect Camelyon dataset metadata."""
        start_time = utc_now()

        collected_data = {
            "dataset": "Camelyon",
            "description": "Pathology challenge for metastasis detection in lymph nodes",
            "versions": ["Camelyon16", "Camelyon17"],
            "note": "Full dataset requires registration",
        }

        return self._create_result(
            success=True,
            data=collected_data,
            records=0,
            start_time=start_time,
        )


@CollectorRegistry.register(DataSource.LIDC_IDRI)
class LIDCIDRICollector(BaseCollector):
    """LIDC-IDRI lung CT dataset collector."""

    @property
    def source(self) -> DataSource:
        return DataSource.LIDC_IDRI

    @property
    def base_url(self) -> str:
        return "https://services.cancerimagingarchive.net/services/v4/TCIA"

    async def collect(self, **kwargs) -> CollectionResult:
        """Collect LIDC-IDRI dataset metadata."""
        start_time = utc_now()

        try:
            # Get LIDC-IDRI collection info via TCIA
            patients = await self._get(
                "getPatient",
                params={
                    "Collection": "LIDC-IDRI",
                    "format": "json",
                },
            )

            return self._create_result(
                success=True,
                data={"patients": patients, "collection": "LIDC-IDRI"},
                records=len(patients) if isinstance(patients, list) else 0,
                start_time=start_time,
            )

        except Exception as e:
            return self._create_result(success=False, errors=[str(e)], start_time=start_time)

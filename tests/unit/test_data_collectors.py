"""
Unit Tests for Data Collectors
==============================

Tests for API key loading and collector authentication.
"""

import os
import pytest
from unittest.mock import patch

from backend.data_collection.base_collector import (
    get_api_key,
    API_KEY_MAPPING,
    BaseCollector,
    CollectorConfig,
    DataSource,
    CollectionResult,
)


class TestGetApiKey:
    """Tests for get_api_key helper."""

    def test_returns_none_when_not_set(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in list(os.environ.keys()):
                if key.startswith(("COSMIC_", "ONCOKB_", "DRUGBANK_")):
                    del os.environ[key]
            assert get_api_key("cosmic") is None
            assert get_api_key("oncokb") is None

    def test_returns_value_from_mapping(self):
        with patch.dict(os.environ, {"COSMIC_API_KEY": "test-key-123"}, clear=False):
            assert get_api_key("cosmic") == "test-key-123"

    def test_returns_value_for_oncokb_token(self):
        # get_api_key checks ONCOKB_API_KEY, ONCOKB_TOKEN, ONCOKB_KEY (in that order)
        with patch.dict(os.environ, {"ONCOKB_TOKEN": "token-abc"}, clear=False):
            assert get_api_key("oncokb") == "token-abc"


class TestApiKeyMapping:
    """Tests for API_KEY_MAPPING."""

    def test_mapping_has_expected_sources(self):
        expected = ["cosmic", "oncokb", "drugbank", "depmap", "ccle"]
        for src in expected:
            assert src in API_KEY_MAPPING

    def test_depmap_and_ccle_share_key(self):
        assert API_KEY_MAPPING.get("depmap") == API_KEY_MAPPING.get("ccle")


class TestBaseCollectorAuthHeader:
    """Tests for BaseCollector auth header generation."""

    def test_get_auth_header_empty_when_no_key(self):
        class DummyCollector(BaseCollector):
            source = DataSource.COSMIC
            base_url = "https://example.com"

            async def collect(self, **kwargs):
                return CollectionResult(source=self.source, success=False)

        config = CollectorConfig(source=DataSource.COSMIC, api_key=None)
        collector = DummyCollector(config)
        assert collector._get_auth_header() == {}

    def test_get_auth_header_bearer_when_key_set(self):
        class DummyCollector(BaseCollector):
            source = DataSource.ONCOKB
            base_url = "https://example.com"

            async def collect(self, **kwargs):
                return CollectionResult(source=self.source, success=False)

        config = CollectorConfig(source=DataSource.ONCOKB, api_key="secret-token")
        collector = DummyCollector(config)
        headers = collector._get_auth_header()
        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer secret-token"

    def test_has_api_key_property(self):
        class DummyCollector(BaseCollector):
            source = DataSource.COSMIC
            base_url = "https://example.com"

            async def collect(self, **kwargs):
                return CollectionResult(source=self.source, success=False)

        assert DummyCollector(CollectorConfig(source=DataSource.COSMIC, api_key=None)).has_api_key is False
        assert DummyCollector(CollectorConfig(source=DataSource.COSMIC, api_key="x")).has_api_key is True

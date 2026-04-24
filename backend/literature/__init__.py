"""
Literature Mining Module
========================

Tools for mining scientific literature:
- PubMed article scraping
- Article management
"""

from backend.literature.pubmed_scraper import (
    PubMedScraper,
    Article,
    SearchResult,
)
from backend.literature.article_manager import (
    ArticleManager,
    ArticleCollection,
)

__all__ = [
    "PubMedScraper",
    "Article",
    "SearchResult",
    "ArticleManager",
    "ArticleCollection",
]

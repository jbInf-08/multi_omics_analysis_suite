"""Literature Mining Module.
========================

Tools for mining scientific literature:
- PubMed article scraping
- Article management
"""

from backend.literature.article_manager import (
    ArticleCollection,
    ArticleManager,
)
from backend.literature.pubmed_scraper import (
    Article,
    PubMedScraper,
    SearchResult,
)

__all__ = [
    "PubMedScraper",
    "Article",
    "SearchResult",
    "ArticleManager",
    "ArticleCollection",
]

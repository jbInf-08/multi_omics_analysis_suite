"""PubMed Scraper Module.
=====================

Search and retrieve articles from PubMed.
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class Author:
    """Article author."""

    last_name: str
    first_name: str
    initials: str = ""
    affiliation: str = ""

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


@dataclass
class Article:
    """PubMed article."""

    pmid: str
    title: str
    abstract: str
    authors: list[Author]
    journal: str
    publication_date: datetime | None
    doi: str | None = None
    pmc_id: str | None = None
    keywords: list[str] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)
    publication_types: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    citation_count: int = 0


@dataclass
class SearchResult:
    """PubMed search result."""

    query: str
    total_count: int
    articles: list[Article]
    search_time: float
    web_env: str | None = None
    query_key: str | None = None


class PubMedScraper:
    """PubMed article scraper.

    Uses NCBI E-utilities API for searching and fetching articles.
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        api_key: str | None = None,
        email: str | None = None,
        tool: str = "MultiOmicsAnalysisSuite",
    ):
        """Initialize PubMed scraper.

        Args:
            api_key: NCBI API key (increases rate limit)
            email: Contact email (required by NCBI)
            tool: Tool name for identification

        """
        self.api_key = api_key
        self.email = email
        self.tool = tool
        self._session: aiohttp.ClientSession | None = None
        self._rate_limit = asyncio.Semaphore(10 if api_key else 3)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _base_params(self) -> dict[str, str]:
        """Get base parameters for API calls."""
        params = {"tool": self.tool}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email
        return params

    async def search(
        self,
        query: str,
        max_results: int = 100,
        sort: str = "relevance",
        min_date: str | None = None,
        max_date: str | None = None,
    ) -> SearchResult:
        """Search PubMed.

        Args:
            query: Search query
            max_results: Maximum results to return
            sort: Sort order ('relevance', 'pub_date')
            min_date: Minimum publication date (YYYY/MM/DD)
            max_date: Maximum publication date (YYYY/MM/DD)

        Returns:
            SearchResult

        """
        start_time = asyncio.get_event_loop().time()

        async with self._rate_limit:
            session = await self._get_session()

            # Search
            params = {
                **self._base_params(),
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "sort": sort,
                "usehistory": "y",
                "retmode": "json",
            }

            if min_date:
                params["mindate"] = min_date
            if max_date:
                params["maxdate"] = max_date

            async with session.get(
                f"{self.BASE_URL}/esearch.fcgi",
                params=params,
            ) as response:
                response.raise_for_status()
                search_data = await response.json()

            result = search_data.get("esearchresult", {})
            pmids = result.get("idlist", [])
            total_count = int(result.get("count", 0))
            web_env = result.get("webenv")
            query_key = result.get("querykey")

        # Fetch article details
        articles = []
        if pmids:
            articles = await self.fetch_articles(pmids)

        search_time = asyncio.get_event_loop().time() - start_time

        return SearchResult(
            query=query,
            total_count=total_count,
            articles=articles,
            search_time=search_time,
            web_env=web_env,
            query_key=query_key,
        )

    async def fetch_articles(self, pmids: list[str]) -> list[Article]:
        """Fetch article details by PMIDs.

        Args:
            pmids: List of PubMed IDs

        Returns:
            List of Articles

        """
        if not pmids:
            return []

        async with self._rate_limit:
            session = await self._get_session()

            params = {
                **self._base_params(),
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
                "rettype": "abstract",
            }

            async with session.get(
                f"{self.BASE_URL}/efetch.fcgi",
                params=params,
            ) as response:
                response.raise_for_status()
                xml_data = await response.text()

        return self._parse_articles_xml(xml_data)

    def _parse_articles_xml(self, xml_data: str) -> list[Article]:
        """Parse PubMed XML response."""
        articles = []

        try:
            root = ET.fromstring(xml_data)

            for article_elem in root.findall(".//PubmedArticle"):
                article = self._parse_article(article_elem)
                if article:
                    articles.append(article)

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")

        return articles

    def _parse_article(self, elem: ET.Element) -> Article | None:
        """Parse a single article element."""
        try:
            # PMID
            pmid_elem = elem.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            # Title
            title_elem = elem.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""

            # Abstract
            abstract_parts = []
            for abstract_elem in elem.findall(".//AbstractText"):
                if abstract_elem.text:
                    label = abstract_elem.get("Label", "")
                    text = abstract_elem.text
                    if label:
                        abstract_parts.append(f"{label}: {text}")
                    else:
                        abstract_parts.append(text)
            abstract = " ".join(abstract_parts)

            # Authors
            authors = []
            for author_elem in elem.findall(".//Author"):
                last_name = author_elem.findtext("LastName", "")
                first_name = author_elem.findtext("ForeName", "")
                initials = author_elem.findtext("Initials", "")
                affiliation = author_elem.findtext(".//Affiliation", "")

                if last_name:
                    authors.append(
                        Author(
                            last_name=last_name,
                            first_name=first_name,
                            initials=initials,
                            affiliation=affiliation,
                        )
                    )

            # Journal
            journal = elem.findtext(".//Journal/Title", "")

            # Publication date
            pub_date = None
            year = elem.findtext(".//PubDate/Year")
            month = elem.findtext(".//PubDate/Month", "1")
            day = elem.findtext(".//PubDate/Day", "1")
            if year:
                try:
                    # Handle month names
                    month_map = {
                        "Jan": "1",
                        "Feb": "2",
                        "Mar": "3",
                        "Apr": "4",
                        "May": "5",
                        "Jun": "6",
                        "Jul": "7",
                        "Aug": "8",
                        "Sep": "9",
                        "Oct": "10",
                        "Nov": "11",
                        "Dec": "12",
                    }
                    month = month_map.get(month, month)
                    pub_date = datetime(int(year), int(month), int(day))
                except ValueError:
                    pub_date = datetime(int(year), 1, 1)

            # DOI
            doi = None
            for article_id in elem.findall(".//ArticleId"):
                if article_id.get("IdType") == "doi":
                    doi = article_id.text
                    break

            # PMC ID
            pmc_id = None
            for article_id in elem.findall(".//ArticleId"):
                if article_id.get("IdType") == "pmc":
                    pmc_id = article_id.text
                    break

            # Keywords
            keywords = [kw.text for kw in elem.findall(".//Keyword") if kw.text]

            # MeSH terms
            mesh_terms = [
                mesh.findtext("DescriptorName", "") for mesh in elem.findall(".//MeshHeading")
            ]
            mesh_terms = [m for m in mesh_terms if m]

            # Publication types
            pub_types = [pt.text for pt in elem.findall(".//PublicationType") if pt.text]

            return Article(
                pmid=pmid,
                title=title,
                abstract=abstract,
                authors=authors,
                journal=journal,
                publication_date=pub_date,
                doi=doi,
                pmc_id=pmc_id,
                keywords=keywords,
                mesh_terms=mesh_terms,
                publication_types=pub_types,
            )

        except Exception as e:
            logger.error(f"Error parsing article: {e}")
            return None

    async def get_related_articles(
        self,
        pmid: str,
        max_results: int = 20,
    ) -> list[Article]:
        """Get articles related to a given PMID."""
        async with self._rate_limit:
            session = await self._get_session()

            params = {
                **self._base_params(),
                "dbfrom": "pubmed",
                "db": "pubmed",
                "id": pmid,
                "cmd": "neighbor_score",
                "retmode": "json",
            }

            async with session.get(
                f"{self.BASE_URL}/elink.fcgi",
                params=params,
            ) as response:
                response.raise_for_status()
                data = await response.json()

        # Extract related PMIDs
        related_pmids = []
        linksets = data.get("linksets", [])
        for linkset in linksets:
            for linksetdb in linkset.get("linksetdbs", []):
                if linksetdb.get("linkname") == "pubmed_pubmed":
                    related_pmids = [str(link.get("id")) for link in linksetdb.get("links", [])][
                        :max_results
                    ]
                    break

        if related_pmids:
            return await self.fetch_articles(related_pmids)
        return []

    async def get_citations(
        self,
        pmid: str,
        max_results: int = 100,
    ) -> list[Article]:
        """Get articles that cite the given PMID."""
        async with self._rate_limit:
            session = await self._get_session()

            params = {
                **self._base_params(),
                "dbfrom": "pubmed",
                "db": "pubmed",
                "id": pmid,
                "linkname": "pubmed_pubmed_citedin",
                "retmode": "json",
            }

            async with session.get(
                f"{self.BASE_URL}/elink.fcgi",
                params=params,
            ) as response:
                response.raise_for_status()
                data = await response.json()

        citing_pmids = []
        linksets = data.get("linksets", [])
        for linkset in linksets:
            for linksetdb in linkset.get("linksetdbs", []):
                if linksetdb.get("linkname") == "pubmed_pubmed_citedin":
                    citing_pmids = [str(link.get("id")) for link in linksetdb.get("links", [])][
                        :max_results
                    ]
                    break

        if citing_pmids:
            return await self.fetch_articles(citing_pmids)
        return []

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

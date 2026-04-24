"""
Article Manager Module
======================

Manage and organize scientific articles.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4
import logging
import json
from pathlib import Path


def utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)

from backend.literature.pubmed_scraper import Article, Author

logger = logging.getLogger(__name__)


@dataclass
class ArticleNote:
    """A note attached to an article."""
    id: str = field(default_factory=lambda: str(uuid4()))
    content: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    tags: List[str] = field(default_factory=list)


@dataclass
class ArticleCollection:
    """A collection of articles."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    article_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ArticleManager:
    """
    Manage scientific articles.
    
    Provides:
    - Article storage and retrieval
    - Collections/folders
    - Tagging and notes
    - Search and filtering
    - Export functionality
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize article manager.
        
        Args:
            storage_path: Path for persistent storage
        """
        self.storage_path = storage_path
        self._articles: Dict[str, Article] = {}
        self._collections: Dict[str, ArticleCollection] = {}
        self._notes: Dict[str, List[ArticleNote]] = {}  # pmid -> notes
        self._tags: Dict[str, Set[str]] = {}  # pmid -> tags
        
        if storage_path:
            self._load_from_storage()
    
    def add_article(self, article: Article) -> str:
        """
        Add an article.
        
        Args:
            article: Article to add
            
        Returns:
            Article PMID
        """
        self._articles[article.pmid] = article
        if article.pmid not in self._notes:
            self._notes[article.pmid] = []
        if article.pmid not in self._tags:
            self._tags[article.pmid] = set()
        
        self._save_to_storage()
        return article.pmid
    
    def add_articles(self, articles: List[Article]) -> List[str]:
        """Add multiple articles."""
        return [self.add_article(a) for a in articles]
    
    def get_article(self, pmid: str) -> Optional[Article]:
        """Get an article by PMID."""
        return self._articles.get(pmid)
    
    def remove_article(self, pmid: str) -> bool:
        """Remove an article."""
        if pmid in self._articles:
            del self._articles[pmid]
            self._notes.pop(pmid, None)
            self._tags.pop(pmid, None)
            
            # Remove from collections
            for collection in self._collections.values():
                if pmid in collection.article_ids:
                    collection.article_ids.remove(pmid)
            
            self._save_to_storage()
            return True
        return False
    
    def list_articles(
        self,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "date",
        reverse: bool = True,
    ) -> List[Article]:
        """List articles with pagination."""
        articles = list(self._articles.values())
        
        # Sort
        if sort_by == "date":
            articles.sort(
                key=lambda a: a.publication_date or datetime.min,
                reverse=reverse
            )
        elif sort_by == "title":
            articles.sort(key=lambda a: a.title.lower(), reverse=reverse)
        elif sort_by == "citations":
            articles.sort(key=lambda a: a.citation_count, reverse=reverse)
        
        return articles[offset:offset + limit]
    
    def search_articles(
        self,
        query: str,
        search_in: List[str] = None,
    ) -> List[Article]:
        """
        Search articles.
        
        Args:
            query: Search query
            search_in: Fields to search in (title, abstract, authors, keywords)
            
        Returns:
            Matching articles
        """
        search_in = search_in or ["title", "abstract", "authors", "keywords"]
        query_lower = query.lower()
        results = []
        
        for article in self._articles.values():
            match = False
            
            if "title" in search_in and query_lower in article.title.lower():
                match = True
            
            if "abstract" in search_in and query_lower in article.abstract.lower():
                match = True
            
            if "authors" in search_in:
                for author in article.authors:
                    if query_lower in author.full_name.lower():
                        match = True
                        break
            
            if "keywords" in search_in:
                for keyword in article.keywords + article.mesh_terms:
                    if query_lower in keyword.lower():
                        match = True
                        break
            
            if match:
                results.append(article)
        
        return results
    
    def filter_by_tags(self, tags: List[str], match_all: bool = False) -> List[Article]:
        """Filter articles by tags."""
        results = []
        tag_set = set(tags)
        
        for pmid, article_tags in self._tags.items():
            if match_all:
                if tag_set.issubset(article_tags):
                    article = self._articles.get(pmid)
                    if article:
                        results.append(article)
            else:
                if tag_set & article_tags:  # Any intersection
                    article = self._articles.get(pmid)
                    if article:
                        results.append(article)
        
        return results
    
    # Tag management
    
    def add_tag(self, pmid: str, tag: str) -> bool:
        """Add a tag to an article."""
        if pmid in self._tags:
            self._tags[pmid].add(tag)
            self._save_to_storage()
            return True
        return False
    
    def remove_tag(self, pmid: str, tag: str) -> bool:
        """Remove a tag from an article."""
        if pmid in self._tags and tag in self._tags[pmid]:
            self._tags[pmid].discard(tag)
            self._save_to_storage()
            return True
        return False
    
    def get_tags(self, pmid: str) -> Set[str]:
        """Get tags for an article."""
        return self._tags.get(pmid, set())
    
    def get_all_tags(self) -> Set[str]:
        """Get all unique tags."""
        all_tags = set()
        for tags in self._tags.values():
            all_tags.update(tags)
        return all_tags
    
    # Note management
    
    def add_note(self, pmid: str, content: str, tags: List[str] = None) -> Optional[ArticleNote]:
        """Add a note to an article."""
        if pmid not in self._notes:
            return None
        
        note = ArticleNote(content=content, tags=tags or [])
        self._notes[pmid].append(note)
        self._save_to_storage()
        return note
    
    def update_note(self, pmid: str, note_id: str, content: str) -> bool:
        """Update a note."""
        if pmid in self._notes:
            for note in self._notes[pmid]:
                if note.id == note_id:
                    note.content = content
                    note.updated_at = utc_now()
                    self._save_to_storage()
                    return True
        return False
    
    def delete_note(self, pmid: str, note_id: str) -> bool:
        """Delete a note."""
        if pmid in self._notes:
            self._notes[pmid] = [n for n in self._notes[pmid] if n.id != note_id]
            self._save_to_storage()
            return True
        return False
    
    def get_notes(self, pmid: str) -> List[ArticleNote]:
        """Get notes for an article."""
        return self._notes.get(pmid, [])
    
    # Collection management
    
    def create_collection(
        self,
        name: str,
        description: str = "",
        article_ids: List[str] = None,
    ) -> ArticleCollection:
        """Create a collection."""
        collection = ArticleCollection(
            name=name,
            description=description,
            article_ids=article_ids or [],
        )
        self._collections[collection.id] = collection
        self._save_to_storage()
        return collection
    
    def get_collection(self, collection_id: str) -> Optional[ArticleCollection]:
        """Get a collection."""
        return self._collections.get(collection_id)
    
    def update_collection(
        self,
        collection_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Optional[ArticleCollection]:
        """Update a collection."""
        collection = self._collections.get(collection_id)
        if collection:
            if name:
                collection.name = name
            if description:
                collection.description = description
            collection.updated_at = utc_now()
            self._save_to_storage()
        return collection
    
    def delete_collection(self, collection_id: str) -> bool:
        """Delete a collection."""
        if collection_id in self._collections:
            del self._collections[collection_id]
            self._save_to_storage()
            return True
        return False
    
    def add_to_collection(self, collection_id: str, pmid: str) -> bool:
        """Add an article to a collection."""
        collection = self._collections.get(collection_id)
        if collection and pmid in self._articles:
            if pmid not in collection.article_ids:
                collection.article_ids.append(pmid)
                collection.updated_at = utc_now()
                self._save_to_storage()
            return True
        return False
    
    def remove_from_collection(self, collection_id: str, pmid: str) -> bool:
        """Remove an article from a collection."""
        collection = self._collections.get(collection_id)
        if collection and pmid in collection.article_ids:
            collection.article_ids.remove(pmid)
            collection.updated_at = utc_now()
            self._save_to_storage()
            return True
        return False
    
    def get_collection_articles(self, collection_id: str) -> List[Article]:
        """Get articles in a collection."""
        collection = self._collections.get(collection_id)
        if collection:
            return [
                self._articles[pmid]
                for pmid in collection.article_ids
                if pmid in self._articles
            ]
        return []
    
    def list_collections(self) -> List[ArticleCollection]:
        """List all collections."""
        return list(self._collections.values())
    
    # Export
    
    def export_bibtex(self, pmids: Optional[List[str]] = None) -> str:
        """Export articles to BibTeX format."""
        articles = [
            self._articles[pmid]
            for pmid in (pmids or self._articles.keys())
            if pmid in self._articles
        ]
        
        bibtex_entries = []
        for article in articles:
            authors = " and ".join(
                f"{a.last_name}, {a.first_name}"
                for a in article.authors
            )
            year = article.publication_date.year if article.publication_date else "n.d."
            
            entry = f"""@article{{{article.pmid},
  title = {{{article.title}}},
  author = {{{authors}}},
  journal = {{{article.journal}}},
  year = {{{year}}},
  pmid = {{{article.pmid}}},"""
            
            if article.doi:
                entry += f"\n  doi = {{{article.doi}}},"
            
            entry += "\n}"
            bibtex_entries.append(entry)
        
        return "\n\n".join(bibtex_entries)
    
    def export_json(self, pmids: Optional[List[str]] = None) -> str:
        """Export articles to JSON."""
        articles = [
            self._articles[pmid]
            for pmid in (pmids or self._articles.keys())
            if pmid in self._articles
        ]
        
        data = []
        for article in articles:
            data.append({
                "pmid": article.pmid,
                "title": article.title,
                "abstract": article.abstract,
                "authors": [
                    {"name": a.full_name, "affiliation": a.affiliation}
                    for a in article.authors
                ],
                "journal": article.journal,
                "publication_date": (
                    article.publication_date.isoformat()
                    if article.publication_date else None
                ),
                "doi": article.doi,
                "keywords": article.keywords,
                "mesh_terms": article.mesh_terms,
            })
        
        return json.dumps(data, indent=2)
    
    # Persistence
    
    def _save_to_storage(self):
        """Save data to storage."""
        if not self.storage_path:
            return
        
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Save articles (simplified - would need proper serialization)
        data = {
            "articles": {
                pmid: {
                    "pmid": a.pmid,
                    "title": a.title,
                    "abstract": a.abstract,
                    "journal": a.journal,
                    "doi": a.doi,
                }
                for pmid, a in self._articles.items()
            },
            "tags": {k: list(v) for k, v in self._tags.items()},
            "collections": {
                cid: {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "article_ids": c.article_ids,
                }
                for cid, c in self._collections.items()
            },
        }
        
        with open(self.storage_path / "articles.json", "w") as f:
            json.dump(data, f, indent=2, default=str)
    
    def _load_from_storage(self):
        """Load data from storage."""
        if not self.storage_path:
            return
        
        data_file = self.storage_path / "articles.json"
        if not data_file.exists():
            return
        
        try:
            with open(data_file) as f:
                data = json.load(f)
            
            # Load articles (simplified)
            for pmid, article_data in data.get("articles", {}).items():
                self._articles[pmid] = Article(
                    pmid=article_data["pmid"],
                    title=article_data["title"],
                    abstract=article_data.get("abstract", ""),
                    authors=[],
                    journal=article_data.get("journal", ""),
                    publication_date=None,
                    doi=article_data.get("doi"),
                )
                self._notes[pmid] = []
            
            # Load tags
            for pmid, tags in data.get("tags", {}).items():
                self._tags[pmid] = set(tags)
            
            # Load collections
            for cid, collection_data in data.get("collections", {}).items():
                self._collections[cid] = ArticleCollection(
                    id=collection_data["id"],
                    name=collection_data["name"],
                    description=collection_data.get("description", ""),
                    article_ids=collection_data.get("article_ids", []),
                )
                
        except Exception as e:
            logger.error(f"Error loading from storage: {e}")

"""
Functional Annotation Module
============================

Functional annotation using sequence similarity, domain analysis, and pathway mapping.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
import numpy as np
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class FunctionalAnnotation:
    """Functional annotation for a gene/protein."""
    gene_id: str
    product: str = "hypothetical protein"
    gene_name: str = ""
    
    # Database references
    uniprot_id: str = ""
    refseq_id: str = ""
    
    # Functional categories
    go_terms: List[str] = field(default_factory=list)
    ec_numbers: List[str] = field(default_factory=list)
    kegg_orthology: List[str] = field(default_factory=list)
    cog_categories: List[str] = field(default_factory=list)
    pfam_domains: List[str] = field(default_factory=list)
    interpro_domains: List[str] = field(default_factory=list)
    
    # Pathway memberships
    kegg_pathways: List[str] = field(default_factory=list)
    reactome_pathways: List[str] = field(default_factory=list)
    
    # Evidence
    evidence_code: str = "IEA"  # Inferred from Electronic Annotation
    confidence: float = 0.0
    
    # Metadata
    source: str = ""
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'gene_id': self.gene_id,
            'product': self.product,
            'gene_name': self.gene_name,
            'GO': self.go_terms,
            'EC': self.ec_numbers,
            'KEGG': self.kegg_orthology,
            'COG': self.cog_categories,
            'Pfam': self.pfam_domains,
            'InterPro': self.interpro_domains,
            'pathways': self.kegg_pathways + self.reactome_pathways,
            'confidence': self.confidence,
        }


@dataclass
class BlastHit:
    """BLAST search hit."""
    query_id: str
    subject_id: str
    identity: float
    alignment_length: int
    mismatches: int
    gap_opens: int
    query_start: int
    query_end: int
    subject_start: int
    subject_end: int
    evalue: float
    bit_score: float
    subject_description: str = ""
    
    @classmethod
    def from_blast_line(cls, line: str) -> "BlastHit":
        """Parse from BLAST tabular output."""
        fields = line.strip().split('\t')
        return cls(
            query_id=fields[0],
            subject_id=fields[1],
            identity=float(fields[2]),
            alignment_length=int(fields[3]),
            mismatches=int(fields[4]),
            gap_opens=int(fields[5]),
            query_start=int(fields[6]),
            query_end=int(fields[7]),
            subject_start=int(fields[8]),
            subject_end=int(fields[9]),
            evalue=float(fields[10]),
            bit_score=float(fields[11]),
            subject_description=fields[12] if len(fields) > 12 else "",
        )


@dataclass 
class DomainHit:
    """Domain/motif search hit."""
    query_id: str
    domain_id: str
    domain_name: str
    domain_description: str
    evalue: float
    score: float
    start: int
    end: int
    domain_length: int
    coverage: float = 0.0


class FunctionalAnnotator(ABC):
    """Abstract base class for functional annotators."""
    
    @abstractmethod
    def annotate(self, sequences: Dict[str, str]) -> Dict[str, FunctionalAnnotation]:
        """Annotate protein sequences."""
        pass


class BlastAnnotator(FunctionalAnnotator):
    """Annotate using BLAST similarity search."""
    
    def __init__(
        self,
        database: str = "nr",
        evalue_cutoff: float = 1e-5,
        identity_cutoff: float = 30.0,
        coverage_cutoff: float = 50.0,
    ):
        self.database = database
        self.evalue_cutoff = evalue_cutoff
        self.identity_cutoff = identity_cutoff
        self.coverage_cutoff = coverage_cutoff
    
    def annotate(self, sequences: Dict[str, str]) -> Dict[str, FunctionalAnnotation]:
        """Annotate sequences using BLAST-like similarity search."""
        logger.info(f"Annotating {len(sequences)} sequences with BLAST")
        
        annotations = {}
        
        for seq_id, sequence in sequences.items():
            # Simulate BLAST search (in practice would call BLAST)
            hits = self._search_database(sequence)
            
            if hits:
                best_hit = hits[0]
                
                # Extract product name from description
                product = self._extract_product(best_hit.subject_description)
                
                annotations[seq_id] = FunctionalAnnotation(
                    gene_id=seq_id,
                    product=product,
                    confidence=min(1.0, best_hit.bit_score / 500),
                    source=f"BLAST:{self.database}",
                    notes=[f"Best hit: {best_hit.subject_id} (E={best_hit.evalue:.2e})"],
                )
            else:
                annotations[seq_id] = FunctionalAnnotation(
                    gene_id=seq_id,
                    product="hypothetical protein",
                    confidence=0.0,
                    source="no_hit",
                )
        
        return annotations
    
    def _search_database(self, sequence: str) -> List[BlastHit]:
        """
        Local similarity search against a tiny bundled peptide library.

        For production BLAST searches, call out to ``blastp``/cloud APIs instead.
        """
        from backend.bioinformatics.algorithms import GlobalAligner, ScoringMatrix

        reference = [
            (
                "sp|P04637|TP53_HUMAN",
                "MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQ",
                "Cellular tumor antigen p53",
            ),
            (
                "sp|P00533|EGFR_HUMAN",
                "MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEVVLGNLEITYVQRNYDLSFLTTI",
                "Epidermal growth factor receptor",
            ),
        ]
        q = (sequence or "").upper().replace("*", "")[:600]
        if not q:
            return []

        aligner = GlobalAligner(scoring_matrix=ScoringMatrix("simple"))
        hits: List[BlastHit] = []
        for subject_id, ref_aa, desc in reference:
            sub = ref_aa[: min(len(ref_aa), 400)]
            aln = aligner.align(q, sub)
            if aln.identity < 0.30:
                continue
            m, n = len(q), len(sub)
            evalue = float(min(1.0, max(1e-45, m * n * np.exp(-0.22 * max(aln.score, 1e-6)))))
            bit = float(max(0.0, (aln.score + 50.0) / 3.0))
            hits.append(
                BlastHit(
                    query_id="query",
                    subject_id=subject_id,
                    identity=float(aln.identity * 100.0),
                    alignment_length=int(aln.alignment_length),
                    mismatches=int(aln.mismatches),
                    gap_opens=int(aln.gaps // 2) if aln.gaps else 0,
                    query_start=1,
                    query_end=min(len(q), int(aln.alignment_length)),
                    subject_start=1,
                    subject_end=min(len(sub), int(aln.alignment_length)),
                    evalue=evalue,
                    bit_score=bit,
                    subject_description=desc,
                )
            )
        hits.sort(key=lambda h: h.evalue)
        return hits[:5]
    
    def _extract_product(self, description: str) -> str:
        """Extract product name from hit description."""
        # Remove organism info in brackets
        product = re.sub(r'\s*\[.*?\]\s*$', '', description)
        
        # Remove accession-like prefixes
        product = re.sub(r'^[A-Z]+_\d+\.\d+\s+', '', product)
        
        # Capitalize first letter
        if product:
            product = product[0].upper() + product[1:]
        
        return product or "hypothetical protein"


class HMMAnnotator(FunctionalAnnotator):
    """Annotate using HMM profile searches (Pfam, TIGRFAM, etc.)."""
    
    def __init__(
        self,
        database: str = "Pfam",
        evalue_cutoff: float = 1e-5,
        use_gathering_threshold: bool = True,
    ):
        self.database = database
        self.evalue_cutoff = evalue_cutoff
        self.use_gathering_threshold = use_gathering_threshold
        self.domain_info = self._load_domain_info()
    
    def _load_domain_info(self) -> Dict[str, Dict]:
        """Curated Pfam-style domain summaries (subset; extend via external HMM DB in production)."""
        return {
            "PF00001": {"name": "Rhodopsin", "description": "7 transmembrane receptor"},
            "PF00069": {"name": "Pkinase", "description": "Protein kinase domain"},
            "PF00076": {"name": "RRM_1", "description": "RNA recognition motif"},
        }
    
    def annotate(self, sequences: Dict[str, str]) -> Dict[str, FunctionalAnnotation]:
        """Annotate sequences using HMM profile search."""
        logger.info(f"Annotating {len(sequences)} sequences with HMM profiles")
        
        annotations = {}
        
        for seq_id, sequence in sequences.items():
            hits = self._search_profiles(seq_id, sequence)
            
            domains = []
            for hit in hits:
                domain_info = self.domain_info.get(hit.domain_id, {})
                domains.append(f"{hit.domain_id}:{domain_info.get('name', 'Unknown')}")
            
            if hits:
                # Combine domain information
                best_hit = hits[0]
                domain_info = self.domain_info.get(best_hit.domain_id, {})
                
                annotations[seq_id] = FunctionalAnnotation(
                    gene_id=seq_id,
                    product=f"{domain_info.get('description', 'Domain')}-containing protein",
                    pfam_domains=domains,
                    confidence=min(1.0, best_hit.score / 100),
                    source=f"HMM:{self.database}",
                )
            else:
                annotations[seq_id] = FunctionalAnnotation(
                    gene_id=seq_id,
                    confidence=0.0,
                )
        
        return annotations
    
    def _search_profiles(self, seq_id: str, sequence: str) -> List[DomainHit]:
        """Lightweight motif screen standing in for HMMER ``hmmscan`` on Pfam."""
        s = (sequence or "").upper()
        motifs = [
            ("PF00069", "GAGGV", 42.0, 2e-5),
            ("PF00001", "DRYLAIV", 30.0, 5e-4),
            ("PF00076", "RNPXKG", 28.0, 1e-3),
        ]
        hits: List[DomainHit] = []
        for dom, motif, score, evalue in motifs:
            pos = s.find(motif)
            if pos < 0:
                continue
            di = self.domain_info.get(dom, {})
            hits.append(
                DomainHit(
                    query_id=seq_id,
                    domain_id=dom,
                    domain_name=di.get("name", dom),
                    domain_description=di.get("description", ""),
                    evalue=float(evalue),
                    score=float(score),
                    start=pos,
                    end=pos + len(motif),
                    domain_length=len(motif),
                    coverage=len(motif) / max(1, len(s)),
                )
            )
        hits.sort(key=lambda h: h.evalue)
        return hits


class InterProAnnotator(FunctionalAnnotator):
    """InterProScan-like integrated annotation."""
    
    def __init__(
        self,
        applications: List[str] = None,
    ):
        self.applications = applications or [
            'Pfam', 'TIGRFAM', 'SMART', 'CDD', 'ProSiteProfiles',
            'PANTHER', 'Gene3D', 'SUPERFAMILY', 'Coils', 'MobiDBLite',
        ]
    
    def annotate(self, sequences: Dict[str, str]) -> Dict[str, FunctionalAnnotation]:
        """Run integrated InterPro annotation."""
        logger.info(f"Running InterProScan on {len(sequences)} sequences")
        
        annotations = {}
        
        for seq_id, sequence in sequences.items():
            # Run multiple analyses
            all_domains = []
            go_terms = set()
            
            for app in self.applications:
                hits = self._run_application(app, sequence)
                
                for hit in hits:
                    all_domains.append(f"{app}:{hit['id']}")
                    go_terms.update(hit.get('go_terms', []))
            
            annotations[seq_id] = FunctionalAnnotation(
                gene_id=seq_id,
                interpro_domains=all_domains,
                go_terms=list(go_terms),
                confidence=len(all_domains) / 10,  # More domains = higher confidence
                source="InterProScan",
            )
        
        return annotations
    
    def _run_application(self, app: str, sequence: str) -> List[Dict]:
        """Run a single InterProScan application (Pfam motif proxy when libraries are absent)."""
        if app == "Pfam":
            hmm = HMMAnnotator(database="Pfam")
            hits = hmm._search_profiles("interpro", sequence)
            return [{"id": h.domain_id, "go_terms": []} for h in hits]
        return []


class GOAnnotator(FunctionalAnnotator):
    """Gene Ontology annotation."""
    
    def __init__(self, go_obo_file: Optional[str] = None):
        self.go_graph = self._load_go_graph(go_obo_file)
    
    def _load_go_graph(self, obo_file: Optional[str]) -> Dict:
        """Load GO graph from OBO file."""
        # Simplified GO structure
        return {
            'GO:0003674': {'name': 'molecular_function', 'namespace': 'molecular_function'},
            'GO:0008150': {'name': 'biological_process', 'namespace': 'biological_process'},
            'GO:0005575': {'name': 'cellular_component', 'namespace': 'cellular_component'},
            # ... many more terms
        }
    
    def annotate(self, sequences: Dict[str, str]) -> Dict[str, FunctionalAnnotation]:
        """Annotate with GO terms."""
        logger.info("Annotating with GO terms")
        
        annotations = {}
        
        for seq_id, sequence in sequences.items():
            # Get GO terms from various sources
            go_terms = self._predict_go_terms(sequence)
            
            annotations[seq_id] = FunctionalAnnotation(
                gene_id=seq_id,
                go_terms=go_terms,
                source="GO",
            )
        
        return annotations
    
    def _predict_go_terms(self, sequence: str) -> List[str]:
        """Coarse GO hints from composition and short motifs (IA evidence only)."""
        s = (sequence or "").upper()
        if not s:
            return []
        cys_frac = s.count("C") / len(s)
        if cys_frac > 0.08:
            return ["GO:0005576", "GO:0008150"]
        if "RRRK" in s or "KRAR" in s:
            return ["GO:0003677", "GO:0006355", "GO:0008150"]
        if "DE" in s and s.count("E") / len(s) > 0.12:
            return ["GO:0003824", "GO:0008150"]
        return ["GO:0008150"]
    
    def propagate_terms(self, terms: List[str]) -> List[str]:
        """Propagate GO terms to parent terms."""
        all_terms = set(terms)
        
        # Would traverse GO graph to add parent terms
        
        return list(all_terms)
    
    def slim_terms(self, terms: List[str], slim_set: str = "goslim_generic") -> List[str]:
        """Map terms toward high-level GO slim roots when present in the input."""
        _ = slim_set
        slim_roots = ("GO:0008150", "GO:0003674", "GO:0005575")
        mapped = [t for t in terms if t in slim_roots]
        return mapped or list(terms)


class KEGGAnnotator(FunctionalAnnotator):
    """KEGG pathway and KO annotation."""
    
    def __init__(self, organism: str = "ko"):
        self.organism = organism
        self.ko_definitions = self._load_ko_definitions()
        self.pathway_map = self._load_pathway_map()
    
    def _load_ko_definitions(self) -> Dict[str, Dict]:
        """Load KEGG Orthology definitions."""
        return {
            "K00001": {"name": "E1.1.1.1", "definition": "alcohol dehydrogenase"},
            "K00002": {"name": "E1.1.1.2", "definition": "alcohol dehydrogenase (NADP+)"},
            "K04451": {"name": "K04451", "definition": "p53-like transcription factor"},
        }
    
    def _load_pathway_map(self) -> Dict[str, List[str]]:
        """Load KO to pathway mapping."""
        return {
            "K00001": ["map00010", "map00071"],
            "K00002": ["map00010"],
            "K04451": ["map04115"],
        }
    
    def annotate(self, sequences: Dict[str, str]) -> Dict[str, FunctionalAnnotation]:
        """Annotate with KEGG KO and pathways."""
        logger.info("Annotating with KEGG")
        
        annotations = {}
        
        for seq_id, sequence in sequences.items():
            # Assign KO
            ko_assignments = self._assign_ko(sequence)
            
            # Map to pathways
            pathways = set()
            for ko in ko_assignments:
                pathways.update(self.pathway_map.get(ko, []))
            
            # Get EC numbers
            ec_numbers = []
            for ko in ko_assignments:
                ko_def = self.ko_definitions.get(ko, {})
                name = ko_def.get('name', '')
                if name.startswith('E'):
                    ec = name[1:]  # Remove 'E' prefix
                    ec_numbers.append(ec)
            
            annotations[seq_id] = FunctionalAnnotation(
                gene_id=seq_id,
                kegg_orthology=ko_assignments,
                kegg_pathways=list(pathways),
                ec_numbers=ec_numbers,
                source="KEGG",
            )
        
        return annotations
    
    def _assign_ko(self, sequence: str) -> List[str]:
        """Heuristic KO hints (KOfam / BLASTKOALA replace this in production)."""
        u = (sequence or "").upper()
        if "MEEPQ" in u:
            return ["K04451"]
        if "GAGGV" in u:
            return ["K00001"]
        return []


class COGAnnotator(FunctionalAnnotator):
    """COG (Clusters of Orthologous Groups) annotation."""
    
    COG_CATEGORIES = {
        'J': 'Translation, ribosomal structure and biogenesis',
        'A': 'RNA processing and modification',
        'K': 'Transcription',
        'L': 'Replication, recombination and repair',
        'B': 'Chromatin structure and dynamics',
        'D': 'Cell cycle control, cell division, chromosome partitioning',
        'Y': 'Nuclear structure',
        'V': 'Defense mechanisms',
        'T': 'Signal transduction mechanisms',
        'M': 'Cell wall/membrane/envelope biogenesis',
        'N': 'Cell motility',
        'Z': 'Cytoskeleton',
        'W': 'Extracellular structures',
        'U': 'Intracellular trafficking, secretion, and vesicular transport',
        'O': 'Posttranslational modification, protein turnover, chaperones',
        'C': 'Energy production and conversion',
        'G': 'Carbohydrate transport and metabolism',
        'E': 'Amino acid transport and metabolism',
        'F': 'Nucleotide transport and metabolism',
        'H': 'Coenzyme transport and metabolism',
        'I': 'Lipid transport and metabolism',
        'P': 'Inorganic ion transport and metabolism',
        'Q': 'Secondary metabolites biosynthesis, transport and catabolism',
        'R': 'General function prediction only',
        'S': 'Function unknown',
    }
    
    def annotate(self, sequences: Dict[str, str]) -> Dict[str, FunctionalAnnotation]:
        """Annotate with COG categories."""
        logger.info("Annotating with COG")
        
        annotations = {}
        
        for seq_id, sequence in sequences.items():
            cog_hits = self._assign_cog(sequence)
            
            categories = []
            for cog_id, category in cog_hits:
                categories.append(f"{category}:{self.COG_CATEGORIES.get(category, 'Unknown')}")
            
            annotations[seq_id] = FunctionalAnnotation(
                gene_id=seq_id,
                cog_categories=categories,
                source="COG",
            )
        
        return annotations
    
    def _assign_cog(self, sequence: str) -> List[Tuple[str, str]]:
        """Very coarse COG category guess from composition (for demos only)."""
        u = (sequence or "").upper()
        if not u:
            return []
        hyd = sum(u.count(x) for x in "AILVFWYM") / len(u)
        charged = sum(u.count(x) for x in "DEKRH") / len(u)
        if hyd > 0.34:
            return [("COG0207", "M")]
        if charged > 0.22:
            return [("COG0533", "T")]
        return [("COG0539", "S")]


class ECNumberAnnotator(FunctionalAnnotator):
    """EC number (enzyme) annotation."""
    
    def __init__(self):
        self.ec_database = self._load_ec_database()
    
    def _load_ec_database(self) -> Dict[str, Dict]:
        """Load EC number database."""
        return {
            '1.1.1.1': {'name': 'alcohol dehydrogenase', 'reaction': 'alcohol + NAD+ = aldehyde + NADH'},
            '1.1.1.2': {'name': 'alcohol dehydrogenase (NADP+)', 'reaction': 'alcohol + NADP+ = aldehyde + NADPH'},
            # ... many more
        }
    
    def annotate(self, sequences: Dict[str, str]) -> Dict[str, FunctionalAnnotation]:
        """Annotate with EC numbers."""
        logger.info("Annotating with EC numbers")
        
        annotations = {}
        
        for seq_id, sequence in sequences.items():
            ec_numbers = self._predict_ec(sequence)
            
            product = "hypothetical protein"
            if ec_numbers:
                ec_info = self.ec_database.get(ec_numbers[0], {})
                product = ec_info.get('name', product)
            
            annotations[seq_id] = FunctionalAnnotation(
                gene_id=seq_id,
                product=product,
                ec_numbers=ec_numbers,
                source="EC",
            )
        
        return annotations
    
    def _predict_ec(self, sequence: str) -> List[str]:
        """Detect a few canonical active-site motifs when present."""
        u = (sequence or "").upper()
        if "GAGGV" in u:
            return ["2.7.11.1"]
        if "GHSAG" in u:
            return ["3.1.1.3"]
        return []


class IntegratedAnnotator:
    """Integrate annotations from multiple sources."""
    
    def __init__(self, annotators: List[FunctionalAnnotator] = None):
        self.annotators = annotators or [
            BlastAnnotator(),
            HMMAnnotator(),
            KEGGAnnotator(),
            COGAnnotator(),
        ]
    
    def annotate(self, sequences: Dict[str, str]) -> Dict[str, FunctionalAnnotation]:
        """Run all annotators and integrate results."""
        logger.info("Running integrated annotation")
        
        all_annotations = []
        
        # Run each annotator
        for annotator in self.annotators:
            try:
                annotations = annotator.annotate(sequences)
                all_annotations.append(annotations)
            except Exception as e:
                logger.warning(f"Annotator {type(annotator).__name__} failed: {e}")
        
        # Integrate results
        integrated = {}
        
        for seq_id in sequences:
            integrated[seq_id] = self._integrate_annotations(
                seq_id,
                [ann.get(seq_id) for ann in all_annotations if seq_id in ann]
            )
        
        return integrated
    
    def _integrate_annotations(
        self,
        seq_id: str,
        annotations: List[FunctionalAnnotation],
    ) -> FunctionalAnnotation:
        """Integrate multiple annotations for one sequence."""
        if not annotations:
            return FunctionalAnnotation(gene_id=seq_id)
        
        # Combine all terms
        go_terms = set()
        ec_numbers = set()
        kegg_ko = set()
        cog_cats = set()
        pfam = set()
        interpro = set()
        pathways = set()
        
        best_product = "hypothetical protein"
        best_confidence = 0.0
        
        for ann in annotations:
            if ann is None:
                continue
            
            go_terms.update(ann.go_terms)
            ec_numbers.update(ann.ec_numbers)
            kegg_ko.update(ann.kegg_orthology)
            cog_cats.update(ann.cog_categories)
            pfam.update(ann.pfam_domains)
            interpro.update(ann.interpro_domains)
            pathways.update(ann.kegg_pathways)
            
            if ann.product != "hypothetical protein" and ann.confidence > best_confidence:
                best_product = ann.product
                best_confidence = ann.confidence
        
        return FunctionalAnnotation(
            gene_id=seq_id,
            product=best_product,
            go_terms=list(go_terms),
            ec_numbers=list(ec_numbers),
            kegg_orthology=list(kegg_ko),
            cog_categories=list(cog_cats),
            pfam_domains=list(pfam),
            interpro_domains=list(interpro),
            kegg_pathways=list(pathways),
            confidence=best_confidence,
            source="integrated",
        )

"""
Gene Prediction Module
======================

Gene prediction algorithms for prokaryotic and eukaryotic genomes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class GenePrediction:
    """Predicted gene."""
    id: str
    contig: str
    start: int  # 1-based
    end: int    # 1-based, inclusive
    strand: str  # '+' or '-'
    gene_type: str = "CDS"  # CDS, tRNA, rRNA, ncRNA
    product: str = ""
    locus_tag: str = ""
    gene_name: str = ""
    protein_id: str = ""
    
    # Sequence
    nucleotide_seq: str = ""
    protein_seq: str = ""
    
    # Scores
    score: float = 0.0
    partial: bool = False
    pseudo: bool = False
    
    # Frame for CDS
    codon_start: int = 1
    translation_table: int = 11
    
    # Additional info
    attributes: Dict = field(default_factory=dict)
    
    @property
    def length(self) -> int:
        return self.end - self.start + 1
    
    def to_gff(self) -> str:
        """Convert to GFF3 format."""
        attrs = [f"ID={self.id}"]
        if self.gene_name:
            attrs.append(f"Name={self.gene_name}")
        if self.product:
            attrs.append(f"product={self.product}")
        if self.locus_tag:
            attrs.append(f"locus_tag={self.locus_tag}")
        
        score = f"{self.score:.1f}" if self.score else "."
        
        return f"{self.contig}\tprediction\t{self.gene_type}\t{self.start}\t{self.end}\t{score}\t{self.strand}\t.\t{';'.join(attrs)}"
    
    def to_genbank_feature(self) -> str:
        """Convert to GenBank feature format."""
        if self.strand == '+':
            location = f"{self.start}..{self.end}"
        else:
            location = f"complement({self.start}..{self.end})"
        
        lines = [f"     {self.gene_type.ljust(15)}{location}"]
        
        if self.locus_tag:
            lines.append(f'                     /locus_tag="{self.locus_tag}"')
        if self.gene_name:
            lines.append(f'                     /gene="{self.gene_name}"')
        if self.product:
            lines.append(f'                     /product="{self.product}"')
        if self.protein_seq:
            lines.append(f'                     /translation="{self.protein_seq}"')
        
        return '\n'.join(lines)


class GenePredictor(ABC):
    """Abstract base class for gene predictors."""
    
    def __init__(self, translation_table: int = 11):
        self.translation_table = translation_table
        self.codon_table = self._get_codon_table(translation_table)
    
    @abstractmethod
    def predict(self, sequence: str, contig_id: str = "contig") -> List[GenePrediction]:
        """Predict genes in sequence."""
        pass
    
    def _get_codon_table(self, table_id: int) -> Dict[str, str]:
        """Get codon translation table."""
        # Standard bacterial/archaeal code (table 11)
        standard = {
            'TTT': 'F', 'TTC': 'F', 'TTA': 'L', 'TTG': 'L',
            'TCT': 'S', 'TCC': 'S', 'TCA': 'S', 'TCG': 'S',
            'TAT': 'Y', 'TAC': 'Y', 'TAA': '*', 'TAG': '*',
            'TGT': 'C', 'TGC': 'C', 'TGA': '*', 'TGG': 'W',
            'CTT': 'L', 'CTC': 'L', 'CTA': 'L', 'CTG': 'L',
            'CCT': 'P', 'CCC': 'P', 'CCA': 'P', 'CCG': 'P',
            'CAT': 'H', 'CAC': 'H', 'CAA': 'Q', 'CAG': 'Q',
            'CGT': 'R', 'CGC': 'R', 'CGA': 'R', 'CGG': 'R',
            'ATT': 'I', 'ATC': 'I', 'ATA': 'I', 'ATG': 'M',
            'ACT': 'T', 'ACC': 'T', 'ACA': 'T', 'ACG': 'T',
            'AAT': 'N', 'AAC': 'N', 'AAA': 'K', 'AAG': 'K',
            'AGT': 'S', 'AGC': 'S', 'AGA': 'R', 'AGG': 'R',
            'GTT': 'V', 'GTC': 'V', 'GTA': 'V', 'GTG': 'V',
            'GCT': 'A', 'GCC': 'A', 'GCA': 'A', 'GCG': 'A',
            'GAT': 'D', 'GAC': 'D', 'GAA': 'E', 'GAG': 'E',
            'GGT': 'G', 'GGC': 'G', 'GGA': 'G', 'GGG': 'G',
        }
        
        # Table 11 (Bacterial) uses TTG and GTG as alternative starts
        if table_id == 11:
            return standard
        
        # Could add more tables here
        return standard
    
    def _translate(self, sequence: str) -> str:
        """Translate DNA to protein."""
        sequence = sequence.upper()
        protein = []
        
        for i in range(0, len(sequence) - 2, 3):
            codon = sequence[i:i + 3]
            if 'N' in codon:
                protein.append('X')
            else:
                protein.append(self.codon_table.get(codon, 'X'))
        
        return ''.join(protein)
    
    def _reverse_complement(self, sequence: str) -> str:
        """Get reverse complement."""
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
        return ''.join(complement.get(b, 'N') for b in reversed(sequence.upper()))


class ORFFinder(GenePredictor):
    """Simple ORF finder."""
    
    def __init__(
        self,
        min_length: int = 100,
        start_codons: List[str] = None,
        stop_codons: List[str] = None,
        translation_table: int = 11,
    ):
        super().__init__(translation_table)
        self.min_length = min_length
        self.start_codons = start_codons or ['ATG', 'GTG', 'TTG']
        self.stop_codons = stop_codons or ['TAA', 'TAG', 'TGA']
    
    def predict(self, sequence: str, contig_id: str = "contig") -> List[GenePrediction]:
        """Find ORFs in sequence."""
        sequence = sequence.upper()
        predictions = []
        gene_id = 0
        
        # Search both strands
        for strand, seq in [('+', sequence), ('-', self._reverse_complement(sequence))]:
            for frame in range(3):
                orfs = self._find_orfs_in_frame(seq, frame)
                
                for start, end in orfs:
                    if strand == '-':
                        # Convert coordinates back to original strand
                        orig_start = len(sequence) - end
                        orig_end = len(sequence) - start
                        start, end = orig_start, orig_end
                        nuc_seq = self._reverse_complement(sequence[start:end])
                    else:
                        nuc_seq = sequence[start:end]
                    
                    protein_seq = self._translate(nuc_seq)
                    
                    predictions.append(GenePrediction(
                        id=f"{contig_id}_orf_{gene_id}",
                        contig=contig_id,
                        start=start + 1,  # 1-based
                        end=end,
                        strand=strand,
                        gene_type="CDS",
                        nucleotide_seq=nuc_seq,
                        protein_seq=protein_seq.rstrip('*'),
                    ))
                    gene_id += 1
        
        return sorted(predictions, key=lambda p: p.start)
    
    def _find_orfs_in_frame(self, sequence: str, frame: int) -> List[Tuple[int, int]]:
        """Find ORFs in a single reading frame."""
        orfs = []
        seq = sequence[frame:]
        
        i = 0
        while i < len(seq) - 2:
            codon = seq[i:i + 3]
            
            if codon in self.start_codons:
                # Find stop codon
                for j in range(i + 3, len(seq) - 2, 3):
                    stop_codon = seq[j:j + 3]
                    if stop_codon in self.stop_codons:
                        orf_length = j - i + 3
                        if orf_length >= self.min_length:
                            orfs.append((i + frame, j + frame + 3))
                        break
            i += 3
        
        return orfs


class ProdigalPredictor(GenePredictor):
    """Prodigal-like gene predictor for prokaryotes."""
    
    def __init__(
        self,
        translation_table: int = 11,
        min_gene_length: int = 90,
        meta_mode: bool = False,
    ):
        super().__init__(translation_table)
        self.min_gene_length = min_gene_length
        self.meta_mode = meta_mode
        
        # Training parameters
        self.rbs_weights = {}
        self.start_weights = {'ATG': 1.0, 'GTG': 0.8, 'TTG': 0.5}
        self.gc_content = 0.5
    
    def train(self, sequence: str):
        """Train on a sequence to learn RBS patterns."""
        logger.info("Training gene prediction model")
        
        sequence = sequence.upper()
        self.gc_content = (sequence.count('G') + sequence.count('C')) / len(sequence)
        
        # Find high-confidence genes for training
        orf_finder = ORFFinder(min_length=300)
        training_orfs = orf_finder.predict(sequence)
        
        # Learn RBS patterns from training genes
        rbs_patterns = defaultdict(int)
        
        for gene in training_orfs:
            if gene.strand == '+':
                upstream = sequence[max(0, gene.start - 21):gene.start - 1]
            else:
                upstream = self._reverse_complement(
                    sequence[gene.end:min(len(sequence), gene.end + 20)]
                )
            
            # Look for Shine-Dalgarno sequences
            for pattern in ['AGGAGG', 'AGGAG', 'GGAGG', 'AGGA', 'GAGG']:
                if pattern in upstream:
                    rbs_patterns[pattern] += 1
        
        # Normalize weights
        total = sum(rbs_patterns.values()) or 1
        self.rbs_weights = {k: v / total for k, v in rbs_patterns.items()}
    
    def predict(self, sequence: str, contig_id: str = "contig") -> List[GenePrediction]:
        """Predict genes using dynamic programming approach."""
        sequence = sequence.upper()
        predictions = []
        
        if not self.meta_mode and not self.rbs_weights:
            self.train(sequence)
        
        # Find all potential start and stop codons
        for strand, seq in [('+', sequence), ('-', self._reverse_complement(sequence))]:
            genes = self._predict_genes_strand(seq, strand)
            
            for gene in genes:
                if strand == '-':
                    # Convert coordinates
                    orig_start = len(sequence) - gene['end']
                    orig_end = len(sequence) - gene['start']
                    gene['start'], gene['end'] = orig_start, orig_end
                
                nuc_seq = sequence[gene['start']:gene['end']]
                if strand == '-':
                    nuc_seq = self._reverse_complement(nuc_seq)
                
                protein_seq = self._translate(nuc_seq)
                
                predictions.append(GenePrediction(
                    id=f"{contig_id}_gene_{len(predictions)}",
                    contig=contig_id,
                    start=gene['start'] + 1,
                    end=gene['end'],
                    strand=strand,
                    gene_type="CDS",
                    score=gene['score'],
                    nucleotide_seq=nuc_seq,
                    protein_seq=protein_seq.rstrip('*'),
                ))
        
        # Resolve overlaps
        predictions = self._resolve_overlaps(predictions)
        
        return sorted(predictions, key=lambda p: p.start)
    
    def _predict_genes_strand(self, sequence: str, strand: str) -> List[Dict]:
        """Predict genes on one strand using scoring."""
        stop_codons = {'TAA', 'TAG', 'TGA'}
        start_codons = {'ATG', 'GTG', 'TTG'}
        
        genes = []
        
        # Find all stops
        stops = {frame: [] for frame in range(3)}
        for i in range(len(sequence) - 2):
            codon = sequence[i:i + 3]
            if codon in stop_codons:
                stops[i % 3].append(i)
        
        # For each frame, find genes
        for frame in range(3):
            frame_stops = stops[frame]
            
            for stop_idx, stop_pos in enumerate(frame_stops):
                # Find best start before this stop
                prev_stop = frame_stops[stop_idx - 1] + 3 if stop_idx > 0 else frame
                
                best_start = None
                best_score = 0
                
                for i in range(prev_stop, stop_pos - self.min_gene_length + 1, 3):
                    codon = sequence[i:i + 3]
                    
                    if codon in start_codons:
                        score = self._score_start(sequence, i, stop_pos)
                        
                        if score > best_score:
                            best_score = score
                            best_start = i
                
                if best_start is not None:
                    genes.append({
                        'start': best_start,
                        'end': stop_pos + 3,
                        'score': best_score,
                    })
        
        return genes
    
    def _score_start(self, sequence: str, start: int, stop: int) -> float:
        """Score a potential start codon."""
        score = 0.0
        
        # Start codon weight
        start_codon = sequence[start:start + 3]
        score += self.start_weights.get(start_codon, 0.1) * 10
        
        # Gene length (prefer longer genes)
        length = stop - start + 3
        score += min(length / 1000, 1.0) * 5
        
        # RBS motif
        upstream = sequence[max(0, start - 20):start]
        for pattern, weight in self.rbs_weights.items():
            if pattern in upstream:
                score += weight * 20
        
        # GC content similarity to genome
        gene_seq = sequence[start:stop + 3]
        gene_gc = (gene_seq.count('G') + gene_seq.count('C')) / len(gene_seq)
        gc_diff = abs(gene_gc - self.gc_content)
        score -= gc_diff * 5  # Penalize unusual GC
        
        return score
    
    def _resolve_overlaps(
        self,
        predictions: List[GenePrediction],
        max_overlap: int = 60,
    ) -> List[GenePrediction]:
        """Resolve overlapping gene predictions."""
        if not predictions:
            return predictions
        
        # Sort by start position
        predictions.sort(key=lambda p: (p.start, -p.score))
        
        resolved = [predictions[0]]
        
        for pred in predictions[1:]:
            last = resolved[-1]
            
            # Check overlap
            overlap = max(0, min(last.end, pred.end) - max(last.start, pred.start))
            
            if overlap > max_overlap:
                # Keep higher scoring
                if pred.score > last.score:
                    resolved[-1] = pred
            else:
                resolved.append(pred)
        
        return resolved


class AugustusPredictor(GenePredictor):
    """Augustus-like gene predictor for eukaryotes."""
    
    def __init__(
        self,
        species: str = "generic",
        strand: str = "both",
        utr: bool = True,
    ):
        super().__init__(translation_table=1)  # Standard code for eukaryotes
        self.species = species
        self.search_strand = strand
        self.predict_utr = utr
        
        # HMM parameters (simplified)
        self.exon_mean_length = 150
        self.intron_mean_length = 1000
        self.donor_site = 'GT'
        self.acceptor_site = 'AG'
    
    def predict(self, sequence: str, contig_id: str = "contig") -> List[GenePrediction]:
        """Predict genes using HMM-like approach."""
        sequence = sequence.upper()
        predictions = []
        
        strands = ['+'] if self.search_strand == '+' else (['-'] if self.search_strand == '-' else ['+', '-'])
        
        for strand in strands:
            seq = sequence if strand == '+' else self._reverse_complement(sequence)
            genes = self._predict_genes_hmm(seq)
            
            for gene in genes:
                if strand == '-':
                    # Convert coordinates
                    orig_start = len(sequence) - gene['end']
                    orig_end = len(sequence) - gene['start']
                    gene['start'], gene['end'] = orig_start, orig_end
                    
                    # Reverse exon coordinates
                    gene['exons'] = [(len(sequence) - e[1], len(sequence) - e[0]) 
                                    for e in reversed(gene['exons'])]
                
                # Build CDS sequence from exons
                cds_seq = ''.join(sequence[e[0]:e[1]] for e in gene['exons'])
                if strand == '-':
                    cds_seq = self._reverse_complement(cds_seq)
                
                protein_seq = self._translate(cds_seq)
                
                predictions.append(GenePrediction(
                    id=f"{contig_id}_gene_{len(predictions)}",
                    contig=contig_id,
                    start=gene['start'] + 1,
                    end=gene['end'],
                    strand=strand,
                    gene_type="CDS",
                    score=gene.get('score', 0),
                    nucleotide_seq=cds_seq,
                    protein_seq=protein_seq.rstrip('*'),
                    attributes={'exons': gene['exons']},
                ))
        
        return sorted(predictions, key=lambda p: p.start)
    
    def _predict_genes_hmm(self, sequence: str) -> List[Dict]:
        """Predict genes using simplified HMM."""
        genes = []
        
        # Find potential splice sites
        donors = self._find_splice_sites(sequence, 'donor')
        acceptors = self._find_splice_sites(sequence, 'acceptor')
        
        # Find start and stop codons
        starts = []
        stops = []
        
        for i in range(len(sequence) - 2):
            codon = sequence[i:i + 3]
            if codon == 'ATG':
                starts.append(i)
            elif codon in ['TAA', 'TAG', 'TGA']:
                stops.append(i)
        
        # Simple gene model: find start-exon-intron-exon-stop patterns
        for start in starts:
            for stop in stops:
                if stop - start < 100 or stop - start > 50000:
                    continue
                
                # Try single exon
                gene_seq = sequence[start:stop + 3]
                if len(gene_seq) % 3 == 0:
                    genes.append({
                        'start': start,
                        'end': stop + 3,
                        'exons': [(start, stop + 3)],
                        'score': self._score_gene(sequence, start, stop + 3, []),
                    })
                
                # Try with one intron
                for donor in donors:
                    if donor <= start:
                        continue
                    for acceptor in acceptors:
                        if acceptor <= donor + 50 or acceptor >= stop:
                            continue
                        
                        # Check if exon lengths make sense
                        exon1_len = donor - start
                        exon2_len = stop + 3 - acceptor
                        
                        if exon1_len >= 30 and exon2_len >= 30:
                            total_cds = exon1_len + exon2_len
                            if total_cds % 3 == 0:
                                genes.append({
                                    'start': start,
                                    'end': stop + 3,
                                    'exons': [(start, donor), (acceptor, stop + 3)],
                                    'score': self._score_gene(sequence, start, stop + 3, [(donor, acceptor)]),
                                })
                        
                        break  # Only try first acceptable intron
                    break
        
        # Keep best non-overlapping genes
        genes.sort(key=lambda g: -g['score'])
        return self._filter_overlapping(genes)
    
    def _find_splice_sites(self, sequence: str, site_type: str) -> List[int]:
        """Find potential splice sites."""
        sites = []
        
        if site_type == 'donor':
            pattern = 'GT'
        else:  # acceptor
            pattern = 'AG'
        
        for i in range(len(sequence) - 1):
            if sequence[i:i + 2] == pattern:
                sites.append(i)
        
        return sites
    
    def _score_gene(
        self,
        sequence: str,
        start: int,
        end: int,
        introns: List[Tuple[int, int]],
    ) -> float:
        """Score a gene model."""
        score = 0.0
        
        # Start codon context (Kozak sequence for eukaryotes)
        if start >= 3:
            context = sequence[start - 3:start + 4]
            if context[0] in 'AG' and context[3] == 'A':
                score += 10  # Good Kozak context
        
        # Gene length
        cds_length = end - start
        for intron_start, intron_end in introns:
            cds_length -= (intron_end - intron_start)
        
        if 100 <= cds_length <= 5000:
            score += 5
        
        # Intron scoring
        for intron_start, intron_end in introns:
            intron_len = intron_end - intron_start
            
            # Check GT-AG rule
            if sequence[intron_start:intron_start + 2] == 'GT':
                score += 5
            if sequence[intron_end - 2:intron_end] == 'AG':
                score += 5
            
            # Reasonable intron length
            if 50 <= intron_len <= 10000:
                score += 2
        
        return score
    
    def _filter_overlapping(self, genes: List[Dict]) -> List[Dict]:
        """Filter overlapping genes, keeping best."""
        filtered = []
        
        for gene in genes:
            overlap = False
            for existing in filtered:
                if gene['start'] < existing['end'] and gene['end'] > existing['start']:
                    overlap = True
                    break
            
            if not overlap:
                filtered.append(gene)
        
        return filtered


class GlimmerPredictor(GenePredictor):
    """Glimmer-like gene predictor using IMMs."""
    
    def __init__(self, translation_table: int = 11):
        super().__init__(translation_table)
        self.imm_order = 8
        self.imm_weights = {}
        self.trained = False
    
    def train(self, sequences: List[str]):
        """Train Interpolated Markov Model."""
        logger.info("Training Glimmer IMM model")
        
        # Build conditional probability tables
        for order in range(self.imm_order + 1):
            counts = defaultdict(lambda: defaultdict(int))
            
            for seq in sequences:
                seq = seq.upper()
                for i in range(len(seq) - order):
                    context = seq[i:i + order]
                    next_base = seq[i + order]
                    counts[context][next_base] += 1
            
            # Convert to probabilities
            for context, next_counts in counts.items():
                total = sum(next_counts.values())
                self.imm_weights[(order, context)] = {
                    base: count / total for base, count in next_counts.items()
                }
        
        self.trained = True
    
    def predict(self, sequence: str, contig_id: str = "contig") -> List[GenePrediction]:
        """Predict genes using trained IMM."""
        if not self.trained:
            # Use simple ORF finding if not trained
            orf_finder = ORFFinder(min_length=self.min_length if hasattr(self, 'min_length') else 100)
            return orf_finder.predict(sequence, contig_id)
        
        sequence = sequence.upper()
        predictions = []
        
        # Score all ORFs with IMM
        orf_finder = ORFFinder(min_length=90)
        orfs = orf_finder.predict(sequence, contig_id)
        
        for orf in orfs:
            # Score with IMM
            score = self._score_sequence(orf.nucleotide_seq)
            orf.score = score
            predictions.append(orf)
        
        # Filter low-scoring predictions
        threshold = np.percentile([p.score for p in predictions], 50) if predictions else 0
        predictions = [p for p in predictions if p.score >= threshold]
        
        return predictions
    
    def _score_sequence(self, sequence: str) -> float:
        """Score a sequence with IMM."""
        score = 0.0
        
        for i in range(len(sequence)):
            for order in range(min(i, self.imm_order), -1, -1):
                context = sequence[max(0, i - order):i]
                probs = self.imm_weights.get((order, context))
                
                if probs:
                    next_base = sequence[i]
                    prob = probs.get(next_base, 0.25)
                    score += np.log(prob + 1e-10)
                    break
        
        return score


class MetaGenePredictor(GenePredictor):
    """Gene predictor for metagenomic data."""
    
    def __init__(
        self,
        translation_table: int = 11,
        min_length: int = 60,
    ):
        super().__init__(translation_table)
        self.min_length = min_length
        
        # Multiple models for different GC content
        self.gc_models = {}
        self._init_models()
    
    def _init_models(self):
        """Initialize models for different GC ranges."""
        for gc_range in [(0.2, 0.35), (0.35, 0.50), (0.50, 0.65), (0.65, 0.80)]:
            gc_mid = (gc_range[0] + gc_range[1]) / 2
            self.gc_models[gc_range] = {
                'start_weights': {'ATG': 1.0, 'GTG': 0.9 - gc_mid * 0.2, 'TTG': 0.7 - gc_mid * 0.3},
                'rbs_consensus': 'AGGAGG' if gc_mid < 0.5 else 'GGAGG',
            }
    
    def predict(self, sequence: str, contig_id: str = "contig") -> List[GenePrediction]:
        """Predict genes in metagenomic fragment."""
        sequence = sequence.upper()
        
        # Determine GC content and select model
        gc = (sequence.count('G') + sequence.count('C')) / len(sequence)
        
        model = None
        for gc_range, gc_model in self.gc_models.items():
            if gc_range[0] <= gc < gc_range[1]:
                model = gc_model
                break
        
        if model is None:
            model = self.gc_models[(0.35, 0.50)]  # Default
        
        # Predict with selected model
        predictions = []
        
        for strand, seq in [('+', sequence), ('-', self._reverse_complement(sequence))]:
            genes = self._predict_strand(seq, model)
            
            for gene in genes:
                if strand == '-':
                    orig_start = len(sequence) - gene['end']
                    orig_end = len(sequence) - gene['start']
                    gene['start'], gene['end'] = orig_start, orig_end
                
                nuc_seq = sequence[gene['start']:gene['end']]
                if strand == '-':
                    nuc_seq = self._reverse_complement(nuc_seq)
                
                protein_seq = self._translate(nuc_seq)
                
                predictions.append(GenePrediction(
                    id=f"{contig_id}_gene_{len(predictions)}",
                    contig=contig_id,
                    start=gene['start'] + 1,
                    end=gene['end'],
                    strand=strand,
                    gene_type="CDS",
                    score=gene['score'],
                    partial=gene.get('partial', False),
                    nucleotide_seq=nuc_seq,
                    protein_seq=protein_seq.rstrip('*'),
                ))
        
        return sorted(predictions, key=lambda p: p.start)
    
    def _predict_strand(self, sequence: str, model: Dict) -> List[Dict]:
        """Predict genes on one strand with given model."""
        genes = []
        
        stop_codons = {'TAA', 'TAG', 'TGA'}
        start_codons = set(model['start_weights'].keys())
        
        # Find stops
        stops = []
        for i in range(len(sequence) - 2):
            if sequence[i:i + 3] in stop_codons:
                stops.append(i)
        
        # Check for partial genes at ends
        # ... (simplified - would check for genes running off contig ends)
        
        # Find genes between stops
        prev_stop = -3
        for stop in stops:
            best_start = None
            best_score = 0
            
            for i in range(prev_stop + 3, stop - self.min_length + 1, 3):
                codon = sequence[i:i + 3]
                
                if codon in start_codons:
                    # Score this start
                    score = model['start_weights'][codon]
                    
                    # RBS check
                    upstream = sequence[max(0, i - 20):i]
                    if model['rbs_consensus'] in upstream:
                        score *= 2
                    
                    # Length bonus
                    length = stop - i + 3
                    score *= (1 + length / 1000)
                    
                    if score > best_score:
                        best_score = score
                        best_start = i
            
            if best_start is not None:
                genes.append({
                    'start': best_start,
                    'end': stop + 3,
                    'score': best_score,
                })
            
            prev_stop = stop
        
        return genes

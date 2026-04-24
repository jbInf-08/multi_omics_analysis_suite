"""
Structural Annotation Module
============================

Structural annotation including repeats, RNA genes, and regulatory elements.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import re
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class StructuralAnnotation:
    """Structural annotation element."""
    id: str
    contig: str
    start: int
    end: int
    strand: str
    feature_type: str
    score: float = 0.0
    attributes: Dict = field(default_factory=dict)
    sequence: str = ""
    
    @property
    def length(self) -> int:
        return self.end - self.start + 1
    
    def to_gff(self) -> str:
        """Convert to GFF format."""
        attrs = [f"ID={self.id}"]
        for key, value in self.attributes.items():
            attrs.append(f"{key}={value}")
        
        return f"{self.contig}\tstructural\t{self.feature_type}\t{self.start}\t{self.end}\t{self.score:.1f}\t{self.strand}\t.\t{';'.join(attrs)}"


class RepeatFinder:
    """Find repetitive sequences in genomes."""
    
    def __init__(
        self,
        min_repeat_length: int = 50,
        min_copies: int = 2,
    ):
        self.min_repeat_length = min_repeat_length
        self.min_copies = min_copies
    
    def find_repeats(
        self,
        sequence: str,
        contig_id: str = "contig",
    ) -> List[StructuralAnnotation]:
        """Find all types of repeats."""
        repeats = []
        
        # Find tandem repeats
        repeats.extend(self._find_tandem_repeats(sequence, contig_id))
        
        # Find inverted repeats
        repeats.extend(self._find_inverted_repeats(sequence, contig_id))
        
        # Find interspersed repeats (simplified)
        repeats.extend(self._find_interspersed_repeats(sequence, contig_id))
        
        return repeats
    
    def _find_tandem_repeats(
        self,
        sequence: str,
        contig_id: str,
    ) -> List[StructuralAnnotation]:
        """Find tandem repeats."""
        repeats = []
        sequence = sequence.upper()
        
        for unit_len in range(1, 50):  # Unit lengths 1-50
            for start in range(len(sequence) - unit_len * self.min_copies):
                unit = sequence[start:start + unit_len]
                
                if 'N' in unit:
                    continue
                
                # Count consecutive repeats
                copies = 1
                pos = start + unit_len
                
                while pos + unit_len <= len(sequence):
                    if sequence[pos:pos + unit_len] == unit:
                        copies += 1
                        pos += unit_len
                    else:
                        break
                
                total_len = copies * unit_len
                
                if copies >= self.min_copies and total_len >= self.min_repeat_length:
                    # Check for simple sequence
                    is_simple = len(set(unit)) <= 2
                    
                    repeats.append(StructuralAnnotation(
                        id=f"{contig_id}_tandem_{len(repeats)}",
                        contig=contig_id,
                        start=start + 1,
                        end=start + total_len,
                        strand='.',
                        feature_type='tandem_repeat',
                        score=copies,
                        attributes={
                            'repeat_unit': unit,
                            'unit_length': unit_len,
                            'copy_number': copies,
                            'is_simple': is_simple,
                        },
                    ))
        
        return self._merge_overlapping(repeats)
    
    def _find_inverted_repeats(
        self,
        sequence: str,
        contig_id: str,
    ) -> List[StructuralAnnotation]:
        """Find inverted repeats (palindromes)."""
        repeats = []
        sequence = sequence.upper()
        
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
        
        for arm_len in range(10, 100):
            for gap in range(0, 100, 2):  # Even gaps for perfect palindromes
                for start in range(len(sequence) - 2 * arm_len - gap):
                    left = sequence[start:start + arm_len]
                    right_start = start + arm_len + gap
                    right = sequence[right_start:right_start + arm_len]
                    
                    if 'N' in left or 'N' in right:
                        continue
                    
                    # Check if right is reverse complement of left
                    left_revcomp = ''.join(complement.get(b, 'N') for b in reversed(left))
                    
                    # Allow some mismatches
                    matches = sum(1 for a, b in zip(right, left_revcomp) if a == b)
                    identity = matches / arm_len
                    
                    if identity >= 0.9:  # 90% identity
                        repeats.append(StructuralAnnotation(
                            id=f"{contig_id}_ir_{len(repeats)}",
                            contig=contig_id,
                            start=start + 1,
                            end=right_start + arm_len,
                            strand='.',
                            feature_type='inverted_repeat',
                            score=identity * 100,
                            attributes={
                                'arm_length': arm_len,
                                'loop_length': gap,
                                'identity': f"{identity:.1%}",
                            },
                        ))
        
        return self._merge_overlapping(repeats)
    
    def _find_interspersed_repeats(
        self,
        sequence: str,
        contig_id: str,
    ) -> List[StructuralAnnotation]:
        """Find interspersed/dispersed repeats."""
        repeats = []
        sequence = sequence.upper()
        
        # Use k-mer based detection
        k = 21
        kmer_positions = {}
        
        for i in range(len(sequence) - k + 1):
            kmer = sequence[i:i + k]
            if 'N' not in kmer:
                if kmer not in kmer_positions:
                    kmer_positions[kmer] = []
                kmer_positions[kmer].append(i)
        
        # Find repetitive k-mers
        for kmer, positions in kmer_positions.items():
            if len(positions) >= self.min_copies:
                # Try to extend
                for pos in positions:
                    # Extend this occurrence
                    extended = self._extend_repeat(sequence, pos, k, kmer_positions)
                    
                    if extended[1] - extended[0] >= self.min_repeat_length:
                        repeats.append(StructuralAnnotation(
                            id=f"{contig_id}_disp_{len(repeats)}",
                            contig=contig_id,
                            start=extended[0] + 1,
                            end=extended[1],
                            strand='.',
                            feature_type='dispersed_repeat',
                            score=len(positions),
                            attributes={
                                'copy_number': len(positions),
                            },
                        ))
        
        return self._merge_overlapping(repeats)
    
    def _extend_repeat(
        self,
        sequence: str,
        start: int,
        k: int,
        kmer_positions: Dict,
    ) -> Tuple[int, int]:
        """Extend repeat from seed position."""
        # Simplified extension
        left = start
        right = start + k
        
        # Extend right
        while right < len(sequence):
            next_kmer = sequence[right - k + 1:right + 1]
            if next_kmer in kmer_positions and len(kmer_positions[next_kmer]) >= 2:
                right += 1
            else:
                break
        
        return (left, right)
    
    def _merge_overlapping(
        self,
        annotations: List[StructuralAnnotation],
    ) -> List[StructuralAnnotation]:
        """Merge overlapping annotations."""
        if not annotations:
            return annotations
        
        annotations.sort(key=lambda a: (a.start, -a.score))
        
        merged = [annotations[0]]
        
        for ann in annotations[1:]:
            last = merged[-1]
            
            if ann.start <= last.end and ann.feature_type == last.feature_type:
                # Merge
                last.end = max(last.end, ann.end)
                last.score = max(last.score, ann.score)
            else:
                merged.append(ann)
        
        return merged


class tRNAScanner:
    """Find tRNA genes."""
    
    def __init__(self):
        # tRNA structural constraints
        self.stem_lengths = {
            'acceptor': 7,
            'd_arm': 4,
            'anticodon': 5,
            't_arm': 5,
        }
    
    def scan(
        self,
        sequence: str,
        contig_id: str = "contig",
    ) -> List[StructuralAnnotation]:
        """Scan for tRNA genes."""
        trnas = []
        sequence = sequence.upper()
        
        # Search both strands
        for strand, seq in [('+', sequence), ('-', self._reverse_complement(sequence))]:
            hits = self._find_trna_candidates(seq)
            
            for hit in hits:
                if strand == '-':
                    start = len(sequence) - hit['end']
                    end = len(sequence) - hit['start']
                else:
                    start = hit['start']
                    end = hit['end']
                
                trnas.append(StructuralAnnotation(
                    id=f"{contig_id}_tRNA_{len(trnas)}",
                    contig=contig_id,
                    start=start + 1,
                    end=end,
                    strand=strand,
                    feature_type='tRNA',
                    score=hit['score'],
                    attributes={
                        'amino_acid': hit.get('amino_acid', 'Unknown'),
                        'anticodon': hit.get('anticodon', 'NNN'),
                    },
                ))
        
        return trnas
    
    def _find_trna_candidates(self, sequence: str) -> List[Dict]:
        """Find tRNA candidates using structural patterns."""
        candidates = []
        
        # tRNAs are typically 73-95 nt
        for i in range(len(sequence) - 73):
            # Check for potential tRNA structure
            region = sequence[i:i + 95]
            
            score = self._score_trna_structure(region)
            
            if score > 50:  # Threshold
                anticodon = self._find_anticodon(region)
                amino_acid = self._anticodon_to_aa(anticodon)
                
                candidates.append({
                    'start': i,
                    'end': i + 75,  # Approximate length
                    'score': score,
                    'anticodon': anticodon,
                    'amino_acid': amino_acid,
                })
        
        return candidates
    
    def _score_trna_structure(self, sequence: str) -> float:
        """Score potential tRNA structure."""
        score = 0.0
        
        # Check for CCA tail
        if sequence[-3:] == 'CCA':
            score += 20
        
        # Check for conserved positions
        # Position 8 is often T
        if len(sequence) > 7 and sequence[7] == 'T':
            score += 10
        
        # Position 14 is often A
        if len(sequence) > 13 and sequence[13] == 'A':
            score += 10
        
        # Check for stem-loop structures
        # Acceptor stem (positions 1-7 pair with 66-72)
        acceptor_pairs = sum(1 for j in range(7) 
                           if len(sequence) > 71 - j 
                           and self._is_complementary(sequence[j], sequence[71 - j]))
        score += acceptor_pairs * 5
        
        return score
    
    def _is_complementary(self, base1: str, base2: str) -> bool:
        """Check if bases are complementary."""
        pairs = {('A', 'T'), ('T', 'A'), ('G', 'C'), ('C', 'G'), ('G', 'T'), ('T', 'G')}
        return (base1, base2) in pairs
    
    def _find_anticodon(self, sequence: str) -> str:
        """Find anticodon in tRNA sequence."""
        # Anticodon is typically at positions 34-36
        if len(sequence) >= 36:
            return sequence[33:36]
        return 'NNN'
    
    def _anticodon_to_aa(self, anticodon: str) -> str:
        """Convert anticodon to amino acid."""
        # Standard genetic code (simplified)
        codon_table = {
            'GCA': 'Cys', 'GCC': 'Gly', 'GCG': 'Arg', 'GCT': 'Ser',
            # ... would include full table
        }
        
        # Reverse complement to get codon
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G'}
        codon = ''.join(complement.get(b, 'N') for b in reversed(anticodon))
        
        return codon_table.get(codon, 'Unknown')
    
    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement."""
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
        return ''.join(complement.get(b, 'N') for b in reversed(seq))


class rRNAFinder:
    """Find ribosomal RNA genes."""
    
    def __init__(self):
        # rRNA gene sizes
        self.rrna_sizes = {
            '5S': (100, 130),
            '16S': (1400, 1600),
            '23S': (2800, 3100),
            '18S': (1800, 2000),  # Eukaryotic
            '28S': (4000, 5000),  # Eukaryotic
        }
        
        # Conserved motifs
        self.conserved_motifs = {
            '16S': ['GGATTAGATACCC', 'TTTAATTGACTCAACG'],
            '23S': ['GACTAAGG', 'GTCCTGACT'],
        }
    
    def find_rrna(
        self,
        sequence: str,
        contig_id: str = "contig",
        domain: str = "bacteria",
    ) -> List[StructuralAnnotation]:
        """Find rRNA genes."""
        rrnas = []
        sequence = sequence.upper()
        
        # Determine which rRNAs to look for
        if domain in ['bacteria', 'archaea']:
            rrna_types = ['5S', '16S', '23S']
        else:
            rrna_types = ['5S', '18S', '28S']
        
        for strand, seq in [('+', sequence), ('-', self._reverse_complement(sequence))]:
            for rrna_type in rrna_types:
                hits = self._find_rrna_type(seq, rrna_type)
                
                for hit in hits:
                    if strand == '-':
                        start = len(sequence) - hit['end']
                        end = len(sequence) - hit['start']
                    else:
                        start = hit['start']
                        end = hit['end']
                    
                    rrnas.append(StructuralAnnotation(
                        id=f"{contig_id}_rRNA_{len(rrnas)}",
                        contig=contig_id,
                        start=start + 1,
                        end=end,
                        strand=strand,
                        feature_type='rRNA',
                        score=hit['score'],
                        attributes={
                            'product': f"{rrna_type} ribosomal RNA",
                        },
                    ))
        
        return rrnas
    
    def _find_rrna_type(self, sequence: str, rrna_type: str) -> List[Dict]:
        """Find specific rRNA type."""
        hits = []
        min_len, max_len = self.rrna_sizes.get(rrna_type, (100, 5000))
        
        # Look for conserved motifs
        motifs = self.conserved_motifs.get(rrna_type, [])
        
        for motif in motifs:
            pos = 0
            while True:
                idx = sequence.find(motif, pos)
                if idx == -1:
                    break
                
                # Estimate full gene boundaries
                # This is simplified - real tools use HMM profiles
                estimated_start = max(0, idx - min_len // 2)
                estimated_end = min(len(sequence), idx + min_len // 2)
                
                span = max(1, estimated_end - estimated_start)
                motif_score = float(len(motif) * 12 + min(60.0, span * 0.02))
                hits.append({
                    'start': estimated_start,
                    'end': estimated_end,
                    'score': min(100.0, motif_score),
                })
                
                pos = idx + 1
        
        return hits
    
    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement."""
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
        return ''.join(complement.get(b, 'N') for b in reversed(seq))


class ncRNAFinder:
    """Find non-coding RNA genes."""
    
    def __init__(self, rfam_models: Optional[Dict] = None):
        self.rfam_models = rfam_models or {}
    
    def find_ncrna(
        self,
        sequence: str,
        contig_id: str = "contig",
    ) -> List[StructuralAnnotation]:
        """Find ncRNA genes using Rfam-like search."""
        ncrnas = []
        sequence = sequence.upper()
        
        # In practice, would use Infernal to search Rfam covariance models
        # Simplified implementation looks for known ncRNA patterns
        
        ncrnas.extend(self._find_tmrna(sequence, contig_id))
        ncrnas.extend(self._find_rnasep(sequence, contig_id))
        ncrnas.extend(self._find_riboswitches(sequence, contig_id))
        
        return ncrnas
    
    def _find_tmrna(self, sequence: str, contig_id: str) -> List[StructuralAnnotation]:
        """Find tmRNA (transfer-messenger RNA)."""
        # tmRNA is ~350-400 nt with characteristic features
        # Simplified pattern matching
        return []
    
    def _find_rnasep(self, sequence: str, contig_id: str) -> List[StructuralAnnotation]:
        """Find RNase P RNA."""
        return []
    
    def _find_riboswitches(self, sequence: str, contig_id: str) -> List[StructuralAnnotation]:
        """Find riboswitches."""
        return []


class CRISPRFinder:
    """Find CRISPR arrays."""
    
    def __init__(
        self,
        min_repeat_length: int = 23,
        max_repeat_length: int = 55,
        min_spacer_length: int = 26,
        max_spacer_length: int = 72,
        min_repeats: int = 3,
    ):
        self.min_repeat_length = min_repeat_length
        self.max_repeat_length = max_repeat_length
        self.min_spacer_length = min_spacer_length
        self.max_spacer_length = max_spacer_length
        self.min_repeats = min_repeats
    
    def find_crisprs(
        self,
        sequence: str,
        contig_id: str = "contig",
    ) -> List[StructuralAnnotation]:
        """Find CRISPR arrays."""
        crisprs = []
        sequence = sequence.upper()
        
        # Find candidate repeat sequences
        candidates = self._find_repeat_candidates(sequence)
        
        for repeat, positions in candidates.items():
            if len(positions) < self.min_repeats:
                continue
            
            # Check spacer lengths
            valid_array = True
            spacers = []
            
            for i in range(len(positions) - 1):
                spacer_start = positions[i] + len(repeat)
                spacer_end = positions[i + 1]
                spacer_len = spacer_end - spacer_start
                
                if not (self.min_spacer_length <= spacer_len <= self.max_spacer_length):
                    valid_array = False
                    break
                
                spacers.append(sequence[spacer_start:spacer_end])
            
            if valid_array and spacers:
                crisprs.append(StructuralAnnotation(
                    id=f"{contig_id}_CRISPR_{len(crisprs)}",
                    contig=contig_id,
                    start=positions[0] + 1,
                    end=positions[-1] + len(repeat),
                    strand='.',
                    feature_type='CRISPR',
                    score=len(spacers),
                    attributes={
                        'repeat_sequence': repeat,
                        'repeat_length': len(repeat),
                        'num_repeats': len(positions),
                        'num_spacers': len(spacers),
                    },
                ))
        
        return crisprs
    
    def _find_repeat_candidates(self, sequence: str) -> Dict[str, List[int]]:
        """Find candidate repeat sequences."""
        candidates = {}
        
        for repeat_len in range(self.min_repeat_length, self.max_repeat_length + 1):
            # Build k-mer index
            kmer_positions = {}
            
            for i in range(len(sequence) - repeat_len + 1):
                kmer = sequence[i:i + repeat_len]
                
                if 'N' in kmer:
                    continue
                
                if kmer not in kmer_positions:
                    kmer_positions[kmer] = []
                kmer_positions[kmer].append(i)
            
            # Find sequences that repeat
            for kmer, positions in kmer_positions.items():
                if len(positions) >= self.min_repeats:
                    # Check for even spacing
                    sorted_pos = sorted(positions)
                    spacings = [sorted_pos[i + 1] - sorted_pos[i] for i in range(len(sorted_pos) - 1)]
                    
                    # All spacings should be similar
                    if spacings and max(spacings) - min(spacings) < 50:
                        candidates[kmer] = sorted_pos
        
        return candidates


class PromoterFinder:
    """Find promoter elements."""
    
    def __init__(self, organism_type: str = "bacteria"):
        self.organism_type = organism_type
        
        if organism_type == "bacteria":
            self.motifs = {
                'pribnow_box': (r'TATAAT', -10, 6),
                'minus35': (r'TTGACA', -35, 6),
            }
        else:
            self.motifs = {
                'tata_box': (r'TATA[AT]A[AT]', -30, 7),
                'caat_box': (r'GG[TC]CAATCT', -80, 9),
                'gc_box': (r'GGGCGG', -90, 6),
            }
    
    def find_promoters(
        self,
        sequence: str,
        gene_starts: List[Tuple[int, str]],  # (position, strand)
        contig_id: str = "contig",
    ) -> List[StructuralAnnotation]:
        """Find promoters upstream of genes."""
        promoters = []
        sequence = sequence.upper()
        
        for gene_start, strand in gene_starts:
            # Search upstream region
            if strand == '+':
                upstream_start = max(0, gene_start - 100)
                upstream_end = gene_start
                upstream = sequence[upstream_start:upstream_end]
            else:
                upstream_start = gene_start
                upstream_end = min(len(sequence), gene_start + 100)
                upstream = self._reverse_complement(sequence[upstream_start:upstream_end])
            
            # Find motifs
            found_motifs = {}
            for motif_name, (pattern, expected_pos, length) in self.motifs.items():
                matches = list(re.finditer(pattern, upstream))
                
                for match in matches:
                    motif_pos = match.start() - len(upstream)
                    
                    # Check if position is reasonable
                    if abs(motif_pos - expected_pos) < 10:
                        found_motifs[motif_name] = match.group()
            
            if found_motifs:
                # Calculate promoter region
                if strand == '+':
                    prom_start = upstream_start
                    prom_end = gene_start
                else:
                    prom_start = gene_start
                    prom_end = upstream_end
                
                promoters.append(StructuralAnnotation(
                    id=f"{contig_id}_promoter_{len(promoters)}",
                    contig=contig_id,
                    start=prom_start + 1,
                    end=prom_end,
                    strand=strand,
                    feature_type='promoter',
                    score=len(found_motifs) * 50,
                    attributes=found_motifs,
                ))
        
        return promoters
    
    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement."""
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
        return ''.join(complement.get(b, 'N') for b in reversed(seq))


class TerminatorFinder:
    """Find transcription terminators."""
    
    def __init__(self):
        self.min_stem_length = 4
        self.min_loop_length = 3
        self.max_loop_length = 10
        self.min_u_tract = 4
    
    def find_terminators(
        self,
        sequence: str,
        gene_ends: List[Tuple[int, str]],
        contig_id: str = "contig",
    ) -> List[StructuralAnnotation]:
        """Find rho-independent terminators downstream of genes."""
        terminators = []
        sequence = sequence.upper()
        
        for gene_end, strand in gene_ends:
            # Search downstream region
            if strand == '+':
                downstream_start = gene_end
                downstream_end = min(len(sequence), gene_end + 100)
                downstream = sequence[downstream_start:downstream_end]
            else:
                downstream_start = max(0, gene_end - 100)
                downstream_end = gene_end
                downstream = self._reverse_complement(sequence[downstream_start:downstream_end])
            
            # Find stem-loop followed by U-tract
            terminator = self._find_terminator_structure(downstream)
            
            if terminator:
                if strand == '+':
                    term_start = downstream_start + terminator['start']
                    term_end = downstream_start + terminator['end']
                else:
                    term_start = downstream_end - terminator['end']
                    term_end = downstream_end - terminator['start']
                
                terminators.append(StructuralAnnotation(
                    id=f"{contig_id}_terminator_{len(terminators)}",
                    contig=contig_id,
                    start=term_start + 1,
                    end=term_end,
                    strand=strand,
                    feature_type='terminator',
                    score=terminator['score'],
                    attributes={
                        'stem_length': terminator['stem_length'],
                        'loop_length': terminator['loop_length'],
                        'u_tract_length': terminator['u_tract_length'],
                    },
                ))
        
        return terminators
    
    def _find_terminator_structure(self, sequence: str) -> Optional[Dict]:
        """Find terminator structure in sequence."""
        best_terminator = None
        best_score = 0
        
        for stem_len in range(self.min_stem_length, 15):
            for loop_len in range(self.min_loop_length, self.max_loop_length + 1):
                for start in range(len(sequence) - stem_len * 2 - loop_len - self.min_u_tract):
                    stem1 = sequence[start:start + stem_len]
                    loop_start = start + stem_len
                    stem2_start = loop_start + loop_len
                    stem2 = sequence[stem2_start:stem2_start + stem_len]
                    
                    # Check for stem complementarity
                    complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G'}
                    stem2_revcomp = ''.join(complement.get(b, 'N') for b in reversed(stem2))
                    
                    stem_matches = sum(1 for a, b in zip(stem1, stem2_revcomp) if a == b)
                    
                    if stem_matches >= stem_len * 0.8:  # 80% complementarity
                        # Check for U-tract after stem-loop
                        u_start = stem2_start + stem_len
                        u_count = 0
                        
                        for i in range(u_start, min(u_start + 10, len(sequence))):
                            if sequence[i] == 'T':
                                u_count += 1
                            else:
                                break
                        
                        if u_count >= self.min_u_tract:
                            score = stem_matches * 10 + u_count * 5
                            
                            if score > best_score:
                                best_score = score
                                best_terminator = {
                                    'start': start,
                                    'end': u_start + u_count,
                                    'stem_length': stem_len,
                                    'loop_length': loop_len,
                                    'u_tract_length': u_count,
                                    'score': score,
                                }
        
        return best_terminator
    
    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement."""
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
        return ''.join(complement.get(b, 'N') for b in reversed(seq))

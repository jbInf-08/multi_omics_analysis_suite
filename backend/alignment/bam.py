"""
BAM Processing Module
=====================

BAM file processing, pileup generation, and alignment manipulation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Iterator
from collections import defaultdict
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class PileupColumn:
    """Pileup at a single position."""
    reference_name: str
    position: int  # 0-based
    reference_base: str
    depth: int
    bases: List[str]
    qualities: List[int]
    mapping_qualities: List[int]
    read_names: List[str] = field(default_factory=list)
    
    def base_counts(self) -> Dict[str, int]:
        """Count bases at this position."""
        counts = defaultdict(int)
        for base in self.bases:
            counts[base.upper()] += 1
        return dict(counts)
    
    def consensus_base(self, min_freq: float = 0.5) -> str:
        """Get consensus base if frequency above threshold."""
        counts = self.base_counts()
        if not counts:
            return 'N'
        
        best_base = max(counts.keys(), key=lambda b: counts[b])
        freq = counts[best_base] / self.depth
        
        return best_base if freq >= min_freq else 'N'
    
    def variant_allele_frequency(self, ref_base: str) -> Dict[str, float]:
        """Calculate variant allele frequencies."""
        counts = self.base_counts()
        total = sum(counts.values())
        
        if total == 0:
            return {}
        
        return {base: count / total for base, count in counts.items() if base != ref_base.upper()}


class BAMProcessor:
    """Process BAM alignments."""
    
    def __init__(self, min_mapping_quality: int = 20, min_base_quality: int = 20):
        self.min_mapping_quality = min_mapping_quality
        self.min_base_quality = min_base_quality
    
    def filter_alignments(
        self,
        alignments: List["AlignmentResult"],
        remove_duplicates: bool = True,
        remove_secondary: bool = True,
        remove_supplementary: bool = True,
    ) -> List["AlignmentResult"]:
        """Filter alignments by quality criteria."""
        filtered = []
        
        for aln in alignments:
            # Skip unmapped
            if not aln.is_mapped:
                continue
            
            # Skip low quality
            if aln.mapping_quality < self.min_mapping_quality:
                continue
            
            # Skip secondary
            if remove_secondary and aln.is_secondary:
                continue
            
            # Skip supplementary
            if remove_supplementary and aln.is_supplementary:
                continue
            
            filtered.append(aln)
        
        # Remove duplicates
        if remove_duplicates:
            filtered = self._remove_duplicates(filtered)
        
        return filtered
    
    def _remove_duplicates(self, alignments: List["AlignmentResult"]) -> List["AlignmentResult"]:
        """Mark/remove duplicate alignments."""
        # Group by position and orientation
        groups = defaultdict(list)
        
        for aln in alignments:
            key = (aln.reference_name, aln.reference_start, aln.is_reverse)
            groups[key].append(aln)
        
        # Keep best alignment from each group
        unique = []
        for group in groups.values():
            best = max(group, key=lambda a: a.mapping_quality)
            unique.append(best)
        
        return unique
    
    def sort_alignments(
        self,
        alignments: List["AlignmentResult"],
        by: str = "position",
    ) -> List["AlignmentResult"]:
        """Sort alignments."""
        if by == "position":
            return sorted(alignments, key=lambda a: (a.reference_name, a.reference_start))
        elif by == "name":
            return sorted(alignments, key=lambda a: a.query_name)
        else:
            return alignments
    
    def merge_alignments(
        self,
        alignment_lists: List[List["AlignmentResult"]],
    ) -> List["AlignmentResult"]:
        """Merge multiple alignment lists."""
        merged = []
        for alns in alignment_lists:
            merged.extend(alns)
        
        return self.sort_alignments(merged)


class PileupGenerator:
    """Generate pileup from alignments."""
    
    def __init__(
        self,
        min_mapping_quality: int = 20,
        min_base_quality: int = 20,
    ):
        self.min_mapping_quality = min_mapping_quality
        self.min_base_quality = min_base_quality
    
    def generate(
        self,
        alignments: List["AlignmentResult"],
        reference: str,
        region_start: int = 0,
        region_end: Optional[int] = None,
    ) -> Iterator[PileupColumn]:
        """Generate pileup columns."""
        if region_end is None:
            region_end = len(reference)
        
        # Filter alignments
        filtered = [a for a in alignments 
                   if a.is_mapped and a.mapping_quality >= self.min_mapping_quality]
        
        # Sort by position
        filtered.sort(key=lambda a: a.reference_start)
        
        # Generate pileup for each position
        for pos in range(region_start, region_end):
            bases = []
            qualities = []
            mapping_qualities = []
            read_names = []
            
            for aln in filtered:
                if aln.reference_start <= pos < aln.reference_end:
                    # Get base at this position
                    query_pos = self._get_query_position(aln, pos)
                    
                    if query_pos is not None and 0 <= query_pos < len(aln.query_sequence):
                        base = aln.query_sequence[query_pos]
                        
                        # Get quality
                        qual = 30  # Default
                        if aln.query_qualities and query_pos < len(aln.query_qualities):
                            qual = ord(aln.query_qualities[query_pos]) - 33
                        
                        if qual >= self.min_base_quality:
                            if aln.is_reverse:
                                base = base.lower()
                            
                            bases.append(base)
                            qualities.append(qual)
                            mapping_qualities.append(aln.mapping_quality)
                            read_names.append(aln.query_name)
            
            yield PileupColumn(
                reference_name=alignments[0].reference_name if alignments else "ref",
                position=pos,
                reference_base=reference[pos] if pos < len(reference) else 'N',
                depth=len(bases),
                bases=bases,
                qualities=qualities,
                mapping_qualities=mapping_qualities,
                read_names=read_names,
            )
    
    def _get_query_position(self, alignment: "AlignmentResult", ref_pos: int) -> Optional[int]:
        """Get query position corresponding to reference position."""
        ref_cursor = alignment.reference_start
        query_cursor = 0
        
        cigar = alignment.cigar
        num = ""
        
        for char in cigar:
            if char.isdigit():
                num += char
            else:
                length = int(num) if num else 0
                
                if char in "M=X":
                    if ref_cursor <= ref_pos < ref_cursor + length:
                        return query_cursor + (ref_pos - ref_cursor)
                    ref_cursor += length
                    query_cursor += length
                elif char == "I":
                    query_cursor += length
                elif char == "D":
                    if ref_cursor <= ref_pos < ref_cursor + length:
                        return None  # Deletion
                    ref_cursor += length
                elif char == "N":
                    if ref_cursor <= ref_pos < ref_cursor + length:
                        return None  # Intron
                    ref_cursor += length
                elif char == "S":
                    query_cursor += length
                
                num = ""
        
        return None


class CoverageCalculator:
    """Calculate coverage statistics."""
    
    def __init__(self, min_mapping_quality: int = 20):
        self.min_mapping_quality = min_mapping_quality
    
    def calculate_coverage(
        self,
        alignments: List["AlignmentResult"],
        reference_length: int,
    ) -> np.ndarray:
        """Calculate per-base coverage."""
        coverage = np.zeros(reference_length, dtype=np.int32)
        
        for aln in alignments:
            if not aln.is_mapped:
                continue
            if aln.mapping_quality < self.min_mapping_quality:
                continue
            
            start = max(0, aln.reference_start)
            end = min(reference_length, aln.reference_end)
            coverage[start:end] += 1
        
        return coverage
    
    def calculate_statistics(
        self,
        coverage: np.ndarray,
    ) -> Dict:
        """Calculate coverage statistics."""
        return {
            'mean_coverage': float(np.mean(coverage)),
            'median_coverage': float(np.median(coverage)),
            'std_coverage': float(np.std(coverage)),
            'min_coverage': int(np.min(coverage)),
            'max_coverage': int(np.max(coverage)),
            'bases_covered': int(np.sum(coverage > 0)),
            'bases_at_1x': int(np.sum(coverage >= 1)),
            'bases_at_10x': int(np.sum(coverage >= 10)),
            'bases_at_30x': int(np.sum(coverage >= 30)),
            'total_bases': len(coverage),
            'coverage_breadth': float(np.mean(coverage > 0)),
        }
    
    def find_low_coverage_regions(
        self,
        coverage: np.ndarray,
        threshold: int = 10,
        min_length: int = 100,
    ) -> List[Tuple[int, int, float]]:
        """Find regions with coverage below threshold."""
        regions = []
        in_low_region = False
        start = 0
        
        for i, cov in enumerate(coverage):
            if cov < threshold:
                if not in_low_region:
                    in_low_region = True
                    start = i
            else:
                if in_low_region:
                    if i - start >= min_length:
                        mean_cov = float(np.mean(coverage[start:i]))
                        regions.append((start, i, mean_cov))
                    in_low_region = False
        
        # Don't forget last region
        if in_low_region and len(coverage) - start >= min_length:
            mean_cov = float(np.mean(coverage[start:]))
            regions.append((start, len(coverage), mean_cov))
        
        return regions


class DuplicateMarker:
    """Mark PCR/optical duplicates."""
    
    def __init__(self, optical_distance: int = 100):
        self.optical_distance = optical_distance
    
    def mark_duplicates(
        self,
        alignments: List["AlignmentResult"],
    ) -> Tuple[List["AlignmentResult"], Dict]:
        """Mark duplicate alignments."""
        # Group by 5' position and orientation
        groups = defaultdict(list)
        
        for i, aln in enumerate(alignments):
            if not aln.is_mapped:
                continue
            
            # Use 5' position as key
            if aln.is_reverse:
                pos = aln.reference_end
            else:
                pos = aln.reference_start
            
            key = (aln.reference_name, pos, aln.is_reverse)
            groups[key].append((i, aln))
        
        # Mark duplicates
        duplicate_indices = set()
        optical_duplicates = 0
        pcr_duplicates = 0
        
        for group in groups.values():
            if len(group) <= 1:
                continue
            
            # Sort by quality
            group.sort(key=lambda x: -x[1].mapping_quality)
            
            # Mark all but best as duplicates
            for i, (idx, aln) in enumerate(group[1:]):
                duplicate_indices.add(idx)
                
                # Check if optical duplicate (would need tile info)
                pcr_duplicates += 1
        
        # Create marked list
        marked = []
        for i, aln in enumerate(alignments):
            if i in duplicate_indices:
                # Mark as duplicate
                aln.tags['DI'] = ('i', 1)
            marked.append(aln)
        
        stats = {
            'total_reads': len(alignments),
            'duplicate_reads': len(duplicate_indices),
            'pcr_duplicates': pcr_duplicates,
            'optical_duplicates': optical_duplicates,
            'duplicate_rate': len(duplicate_indices) / len(alignments) if alignments else 0,
        }
        
        return marked, stats


class BaseRecalibrator:
    """Base quality score recalibration."""
    
    def __init__(self):
        self.recalibration_table = {}
    
    def build_recalibration_table(
        self,
        alignments: List["AlignmentResult"],
        reference: str,
        known_sites: Optional[List[Tuple[int, str, str]]] = None,
    ):
        """Build recalibration table from alignments."""
        known_positions = set()
        if known_sites:
            for pos, ref, alt in known_sites:
                known_positions.add(pos)
        
        # Count errors by quality score
        quality_errors = defaultdict(lambda: {'total': 0, 'errors': 0})
        
        for aln in alignments:
            if not aln.is_mapped:
                continue
            
            ref_pos = aln.reference_start
            query_pos = 0
            
            for i, char in enumerate(aln.cigar):
                if char.isdigit():
                    continue
                
                # Parse CIGAR
                num = ""
                j = i - 1
                while j >= 0 and aln.cigar[j].isdigit():
                    num = aln.cigar[j] + num
                    j -= 1
                length = int(num) if num else 0
                
                if char in "M=X":
                    for k in range(length):
                        if ref_pos + k in known_positions:
                            continue
                        
                        if ref_pos + k < len(reference):
                            ref_base = reference[ref_pos + k]
                            query_base = aln.query_sequence[query_pos + k]
                            
                            # Get quality
                            qual = 30
                            if aln.query_qualities:
                                qual = ord(aln.query_qualities[query_pos + k]) - 33
                            
                            quality_errors[qual]['total'] += 1
                            if query_base.upper() != ref_base.upper():
                                quality_errors[qual]['errors'] += 1
                    
                    ref_pos += length
                    query_pos += length
                elif char == "I":
                    query_pos += length
                elif char == "D":
                    ref_pos += length
        
        # Calculate recalibration
        for qual, counts in quality_errors.items():
            if counts['total'] > 0:
                empirical_error_rate = counts['errors'] / counts['total']
                if empirical_error_rate > 0:
                    empirical_qual = -10 * np.log10(empirical_error_rate)
                else:
                    empirical_qual = 40  # Max quality
                
                self.recalibration_table[qual] = int(min(40, empirical_qual))
    
    def recalibrate(
        self,
        alignment: "AlignmentResult",
    ) -> "AlignmentResult":
        """Recalibrate base qualities for alignment."""
        if not alignment.query_qualities:
            return alignment
        
        new_quals = []
        for q_char in alignment.query_qualities:
            orig_qual = ord(q_char) - 33
            new_qual = self.recalibration_table.get(orig_qual, orig_qual)
            new_quals.append(chr(new_qual + 33))
        
        alignment.query_qualities = ''.join(new_quals)
        return alignment

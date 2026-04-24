"""
Long Read Analysis Module
=========================

Quality control and analysis for long read sequencing data.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class LongRead:
    """Long read sequence data."""
    id: str
    sequence: str
    quality: str = ""
    channel: int = 0
    start_time: float = 0.0
    
    # Metadata
    is_pass: bool = True
    template_strand: bool = True
    
    @property
    def length(self) -> int:
        return len(self.sequence)
    
    @property
    def mean_quality(self) -> float:
        if not self.quality:
            return 0.0
        scores = [ord(c) - 33 for c in self.quality]
        return np.mean(scores)
    
    @property
    def gc_content(self) -> float:
        seq = self.sequence.upper()
        gc = seq.count('G') + seq.count('C')
        return gc / self.length if self.length > 0 else 0.0


@dataclass
class ReadStatistics:
    """Statistics for a set of reads."""
    num_reads: int = 0
    total_bases: int = 0
    mean_length: float = 0.0
    median_length: float = 0.0
    n50: int = 0
    longest_read: int = 0
    shortest_read: int = 0
    mean_quality: float = 0.0
    
    # Pass/fail
    num_pass: int = 0
    num_fail: int = 0
    
    # Time
    sequencing_hours: float = 0.0
    throughput_per_hour: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            'num_reads': self.num_reads,
            'total_bases': self.total_bases,
            'mean_length': f"{self.mean_length:.0f}",
            'median_length': f"{self.median_length:.0f}",
            'N50': self.n50,
            'longest_read': self.longest_read,
            'shortest_read': self.shortest_read,
            'mean_quality': f"{self.mean_quality:.1f}",
            'pass_reads': self.num_pass,
            'fail_reads': self.num_fail,
            'pass_rate': f"{self.num_pass / self.num_reads * 100:.1f}%" if self.num_reads > 0 else "0%",
        }


class LongReadQC:
    """Quality control for long read data."""
    
    def __init__(self, min_quality: float = 7.0, min_length: int = 200):
        self.min_quality = min_quality
        self.min_length = min_length
    
    def calculate_statistics(self, reads: List[LongRead]) -> ReadStatistics:
        """Calculate read statistics."""
        if not reads:
            return ReadStatistics()
        
        lengths = [r.length for r in reads]
        qualities = [r.mean_quality for r in reads if r.mean_quality > 0]
        
        # Calculate N50
        sorted_lengths = sorted(lengths, reverse=True)
        total = sum(sorted_lengths)
        cumsum = 0
        n50 = 0
        
        for length in sorted_lengths:
            cumsum += length
            if cumsum >= total / 2:
                n50 = length
                break
        
        # Count pass/fail
        num_pass = sum(1 for r in reads if r.is_pass)
        
        return ReadStatistics(
            num_reads=len(reads),
            total_bases=sum(lengths),
            mean_length=np.mean(lengths),
            median_length=np.median(lengths),
            n50=n50,
            longest_read=max(lengths),
            shortest_read=min(lengths),
            mean_quality=np.mean(qualities) if qualities else 0.0,
            num_pass=num_pass,
            num_fail=len(reads) - num_pass,
        )
    
    def filter_reads(
        self,
        reads: List[LongRead],
        min_quality: Optional[float] = None,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
    ) -> List[LongRead]:
        """Filter reads by quality and length."""
        min_qual = min_quality or self.min_quality
        min_len = min_length or self.min_length
        
        filtered = []
        for read in reads:
            if read.mean_quality < min_qual:
                continue
            if read.length < min_len:
                continue
            if max_length and read.length > max_length:
                continue
            filtered.append(read)
        
        logger.info(f"Filtered {len(reads)} -> {len(filtered)} reads")
        return filtered


class ReadLengthDistribution:
    """Analyze read length distribution."""
    
    def __init__(self):
        self.lengths: List[int] = []
    
    def add_reads(self, reads: List[LongRead]):
        """Add reads for analysis."""
        self.lengths.extend(r.length for r in reads)
    
    def histogram(
        self,
        bins: int = 100,
        max_length: Optional[int] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Calculate length histogram."""
        if not self.lengths:
            return np.array([]), np.array([])
        
        data = np.array(self.lengths)
        
        if max_length:
            data = data[data <= max_length]
        
        counts, edges = np.histogram(data, bins=bins)
        return counts, edges
    
    def percentiles(self) -> Dict[str, int]:
        """Calculate length percentiles."""
        if not self.lengths:
            return {}
        
        data = np.array(self.lengths)
        
        return {
            'p10': int(np.percentile(data, 10)),
            'p25': int(np.percentile(data, 25)),
            'p50': int(np.percentile(data, 50)),
            'p75': int(np.percentile(data, 75)),
            'p90': int(np.percentile(data, 90)),
            'p99': int(np.percentile(data, 99)),
        }
    
    def nx_values(self) -> Dict[str, int]:
        """Calculate Nx values."""
        if not self.lengths:
            return {}
        
        sorted_lengths = sorted(self.lengths, reverse=True)
        total = sum(sorted_lengths)
        
        results = {}
        cumsum = 0
        
        for x in [10, 25, 50, 75, 90]:
            threshold = total * x / 100
            
            for length in sorted_lengths:
                cumsum += length
                if cumsum >= threshold and f'N{x}' not in results:
                    results[f'N{x}'] = length
                    break
        
        return results


class QualityAnalysis:
    """Analyze read quality scores."""
    
    def __init__(self):
        self.quality_counts = defaultdict(int)
        self.position_qualities = defaultdict(list)
    
    def add_reads(self, reads: List[LongRead]):
        """Add reads for quality analysis."""
        for read in reads:
            if not read.quality:
                continue
            
            mean_q = int(read.mean_quality)
            self.quality_counts[mean_q] += 1
            
            # Per-position quality (limited to first 1000 bp)
            for i, q_char in enumerate(read.quality[:1000]):
                q = ord(q_char) - 33
                self.position_qualities[i].append(q)
    
    def quality_histogram(self) -> Dict[int, int]:
        """Get quality score histogram."""
        return dict(self.quality_counts)
    
    def mean_quality_by_position(self) -> List[float]:
        """Calculate mean quality by position."""
        if not self.position_qualities:
            return []
        
        max_pos = max(self.position_qualities.keys())
        return [np.mean(self.position_qualities.get(i, [0])) for i in range(max_pos + 1)]
    
    def phred_to_error_rate(self, phred: float) -> float:
        """Convert Phred score to error rate."""
        return 10 ** (-phred / 10)
    
    def error_rate_to_accuracy(self, error_rate: float) -> float:
        """Convert error rate to accuracy."""
        return 1 - error_rate


class ErrorProfile:
    """Analyze error profile of long reads."""
    
    def __init__(self):
        self.substitutions = defaultdict(int)
        self.insertions = defaultdict(int)
        self.deletions = defaultdict(int)
        self.total_aligned = 0
    
    def analyze_alignment(
        self,
        query: str,
        reference: str,
        cigar: str,
    ):
        """Analyze errors from alignment."""
        query = query.upper()
        reference = reference.upper()
        
        q_pos = 0
        r_pos = 0
        
        # Parse CIGAR
        num = ""
        for char in cigar:
            if char.isdigit():
                num += char
            else:
                length = int(num) if num else 0
                
                if char in 'M=X':
                    for i in range(length):
                        if q_pos < len(query) and r_pos < len(reference):
                            q_base = query[q_pos]
                            r_base = reference[r_pos]
                            
                            if q_base != r_base:
                                self.substitutions[f"{r_base}>{q_base}"] += 1
                            
                            self.total_aligned += 1
                        q_pos += 1
                        r_pos += 1
                
                elif char == 'I':
                    for i in range(length):
                        if q_pos < len(query):
                            self.insertions[query[q_pos]] += 1
                        q_pos += 1
                    self.total_aligned += length
                
                elif char == 'D':
                    for i in range(length):
                        if r_pos < len(reference):
                            self.deletions[reference[r_pos]] += 1
                        r_pos += 1
                    self.total_aligned += length
                
                elif char == 'N':
                    r_pos += length
                
                elif char == 'S':
                    q_pos += length
                
                num = ""
    
    def get_error_rates(self) -> Dict:
        """Calculate error rates."""
        if self.total_aligned == 0:
            return {}
        
        total_sub = sum(self.substitutions.values())
        total_ins = sum(self.insertions.values())
        total_del = sum(self.deletions.values())
        
        return {
            'substitution_rate': total_sub / self.total_aligned,
            'insertion_rate': total_ins / self.total_aligned,
            'deletion_rate': total_del / self.total_aligned,
            'total_error_rate': (total_sub + total_ins + total_del) / self.total_aligned,
        }
    
    def get_substitution_matrix(self) -> Dict[str, Dict[str, int]]:
        """Get substitution matrix."""
        bases = ['A', 'C', 'G', 'T']
        matrix = {b: {b2: 0 for b2 in bases} for b in bases}
        
        for sub, count in self.substitutions.items():
            if '>' in sub:
                ref, alt = sub.split('>')
                if ref in bases and alt in bases:
                    matrix[ref][alt] = count
        
        return matrix


class AdapterDetector:
    """Detect and trim adapters from long reads."""
    
    def __init__(self):
        # Common adapter sequences
        self.adapters = {
            'ONT_5': 'AATGTACTTCGTTCAGTTACGTATTGCT',
            'ONT_3': 'GCAATACGTAACTGAACGAAGT',
            'PacBio_barcoded': 'ATCTCTCTCTTTTCCTCCTCCTCCGTTGTTGTTGTTGAGAGAGAT',
        }
    
    def detect(
        self,
        read: LongRead,
        check_length: int = 100,
    ) -> Dict:
        """Detect adapters in read."""
        results = {
            'has_5_adapter': False,
            'has_3_adapter': False,
            '5_adapter_position': -1,
            '3_adapter_position': -1,
            'adapter_type': None,
        }
        
        seq = read.sequence.upper()
        
        for adapter_name, adapter_seq in self.adapters.items():
            # Check 5' end
            head = seq[:check_length]
            pos = self._find_adapter(head, adapter_seq)
            
            if pos >= 0:
                results['has_5_adapter'] = True
                results['5_adapter_position'] = pos
                results['adapter_type'] = adapter_name
            
            # Check 3' end
            tail = seq[-check_length:]
            pos = self._find_adapter(tail, adapter_seq)
            
            if pos >= 0:
                results['has_3_adapter'] = True
                results['3_adapter_position'] = len(seq) - check_length + pos
        
        return results
    
    def _find_adapter(
        self,
        sequence: str,
        adapter: str,
        max_errors: int = 3,
    ) -> int:
        """Find adapter allowing mismatches."""
        adapter_len = min(len(adapter), 20)
        adapter_short = adapter[:adapter_len]
        
        for i in range(len(sequence) - adapter_len + 1):
            window = sequence[i:i + adapter_len]
            errors = sum(1 for a, b in zip(adapter_short, window) if a != b)
            
            if errors <= max_errors:
                return i
        
        return -1
    
    def trim(
        self,
        read: LongRead,
        check_length: int = 100,
    ) -> LongRead:
        """Trim adapters from read."""
        detection = self.detect(read, check_length)
        
        start = 0
        end = read.length
        
        if detection['has_5_adapter']:
            # Find end of adapter region
            start = detection['5_adapter_position'] + 30  # Approximate adapter length
        
        if detection['has_3_adapter']:
            end = detection['3_adapter_position']
        
        if start >= end:
            return read
        
        return LongRead(
            id=read.id,
            sequence=read.sequence[start:end],
            quality=read.quality[start:end] if read.quality else "",
            is_pass=read.is_pass,
        )

"""
Reference Index Module
======================

Index structures for fast sequence lookup.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReferenceIndex:
    """Base class for reference indices."""
    name: str
    length: int
    sequence: str = ""


class FMIndex:
    """FM-index for exact and approximate string matching."""
    
    def __init__(self, checkpoint_interval: int = 128):
        self.checkpoint_interval = checkpoint_interval
        self.reference = ""
        self.bwt = ""
        self.suffix_array = []
        self.occ = {}
        self.c = {}
        self.checkpoints = {}
    
    def build(self, sequence: str):
        """Build FM-index."""
        logger.info(f"Building FM-index for {len(sequence)} bp sequence")
        
        self.reference = sequence.upper()
        text = self.reference + "$"
        
        # Build suffix array
        self.suffix_array = sorted(range(len(text)), key=lambda i: text[i:])
        
        # Build BWT
        self.bwt = ''.join(text[(i - 1) % len(text)] for i in self.suffix_array)
        
        # Build occurrence table with checkpoints
        self._build_occ_with_checkpoints()
        
        # Build C array
        self._build_c_array()
        
        logger.info("FM-index built successfully")
    
    def _build_occ_with_checkpoints(self):
        """Build occurrence table with checkpoints."""
        self.checkpoints = defaultdict(dict)
        counts = defaultdict(int)
        
        for i, char in enumerate(self.bwt):
            counts[char] += 1
            
            if i % self.checkpoint_interval == 0:
                for c, count in counts.items():
                    self.checkpoints[c][i // self.checkpoint_interval] = count
        
        # Store final counts
        self.final_counts = dict(counts)
    
    def _build_c_array(self):
        """Build C array (count of chars less than each char)."""
        self.c = {}
        total = 0
        
        for char in sorted(set(self.bwt)):
            self.c[char] = total
            total += self.bwt.count(char)
    
    def count(self, char: str, position: int) -> int:
        """Count occurrences of char up to position."""
        if char not in self.checkpoints:
            return 0
        
        checkpoint_idx = position // self.checkpoint_interval
        checkpoint_count = self.checkpoints[char].get(checkpoint_idx, 0)
        
        # Count from checkpoint to position
        start = checkpoint_idx * self.checkpoint_interval
        extra = sum(1 for i in range(start, position) if self.bwt[i] == char)
        
        return checkpoint_count + extra
    
    def search(self, pattern: str) -> List[int]:
        """Search for exact pattern matches."""
        pattern = pattern.upper()
        
        if not pattern:
            return []
        
        top = 0
        bottom = len(self.bwt) - 1
        
        for char in reversed(pattern):
            if char not in self.c:
                return []
            
            top = self.c[char] + self.count(char, top)
            bottom = self.c[char] + self.count(char, bottom + 1)
            
            if top >= bottom:
                return []
        
        return [self.suffix_array[i] for i in range(top, bottom)]


class MinimapIndex:
    """Minimizer-based index for long read mapping."""
    
    def __init__(self, k: int = 15, w: int = 10):
        self.k = k
        self.w = w
        self.index = {}
        self.reference = ""
    
    def build(self, sequence: str):
        """Build minimizer index."""
        logger.info(f"Building minimizer index (k={self.k}, w={self.w})")
        
        self.reference = sequence.upper()
        self.index = defaultdict(list)
        
        for i in range(len(self.reference) - self.k - self.w + 1):
            minimizer = self._get_minimizer(i)
            if minimizer:
                self.index[minimizer[0]].append((minimizer[1], minimizer[2]))
        
        self.index = dict(self.index)
        logger.info(f"Index built with {len(self.index)} minimizers")
    
    def _get_minimizer(self, start: int) -> Optional[Tuple[str, int, bool]]:
        """Get minimizer from window."""
        candidates = []
        
        for j in range(self.w):
            pos = start + j
            if pos + self.k > len(self.reference):
                break
            
            kmer = self.reference[pos:pos + self.k]
            if 'N' in kmer:
                continue
            
            revcomp = self._reverse_complement(kmer)
            canonical = min(kmer, revcomp)
            is_reverse = canonical == revcomp
            
            candidates.append((canonical, pos, is_reverse))
        
        if candidates:
            return min(candidates, key=lambda x: x[0])
        return None
    
    def _reverse_complement(self, seq: str) -> str:
        """Get reverse complement."""
        complement = {'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'N': 'N'}
        return ''.join(complement.get(b, 'N') for b in reversed(seq))
    
    def query(self, minimizer: str) -> List[Tuple[int, bool]]:
        """Query index for minimizer positions."""
        return self.index.get(minimizer, [])


class HashIndex:
    """Simple hash-based index for seed lookup."""
    
    def __init__(self, seed_length: int = 20):
        self.seed_length = seed_length
        self.index = {}
        self.reference = ""
    
    def build(self, sequence: str, step: int = 1):
        """Build hash index."""
        logger.info(f"Building hash index with seed length {self.seed_length}")
        
        self.reference = sequence.upper()
        self.index = defaultdict(list)
        
        for i in range(0, len(self.reference) - self.seed_length + 1, step):
            seed = self.reference[i:i + self.seed_length]
            if 'N' not in seed:
                self.index[seed].append(i)
        
        self.index = dict(self.index)
        logger.info(f"Index built with {len(self.index)} seeds")
    
    def query(self, seed: str) -> List[int]:
        """Query index for seed positions."""
        return self.index.get(seed.upper(), [])
    
    def query_with_mismatches(self, seed: str, max_mismatches: int = 1) -> List[Tuple[int, int]]:
        """Query allowing mismatches."""
        results = []
        seed = seed.upper()
        
        # Exact matches
        for pos in self.index.get(seed, []):
            results.append((pos, 0))
        
        if max_mismatches > 0:
            # Generate variants with 1 mismatch
            for i in range(len(seed)):
                for base in 'ACGT':
                    if base != seed[i]:
                        variant = seed[:i] + base + seed[i + 1:]
                        for pos in self.index.get(variant, []):
                            results.append((pos, 1))
        
        return results

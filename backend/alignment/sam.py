"""
SAM/BAM Format Module
=====================

SAM format parsing and writing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Iterator
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class SAMHeader:
    """SAM file header."""
    version: str = "1.6"
    sort_order: str = "unsorted"
    references: List[Dict] = field(default_factory=list)
    read_groups: List[Dict] = field(default_factory=list)
    programs: List[Dict] = field(default_factory=list)
    comments: List[str] = field(default_factory=list)
    
    def to_string(self) -> str:
        """Convert header to SAM format."""
        lines = []
        
        # HD line
        lines.append(f"@HD\tVN:{self.version}\tSO:{self.sort_order}")
        
        # SQ lines
        for ref in self.references:
            parts = [f"@SQ\tSN:{ref['name']}\tLN:{ref['length']}"]
            if 'md5' in ref:
                parts.append(f"M5:{ref['md5']}")
            lines.append('\t'.join(parts))
        
        # RG lines
        for rg in self.read_groups:
            parts = [f"@RG\tID:{rg['id']}"]
            if 'sample' in rg:
                parts.append(f"SM:{rg['sample']}")
            if 'platform' in rg:
                parts.append(f"PL:{rg['platform']}")
            lines.append('\t'.join(parts))
        
        # PG lines
        for pg in self.programs:
            parts = [f"@PG\tID:{pg['id']}"]
            if 'name' in pg:
                parts.append(f"PN:{pg['name']}")
            if 'version' in pg:
                parts.append(f"VN:{pg['version']}")
            if 'command' in pg:
                parts.append(f"CL:{pg['command']}")
            lines.append('\t'.join(parts))
        
        # CO lines
        for comment in self.comments:
            lines.append(f"@CO\t{comment}")
        
        return '\n'.join(lines)
    
    @classmethod
    def from_string(cls, header_text: str) -> "SAMHeader":
        """Parse header from SAM format."""
        header = cls()
        
        for line in header_text.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('\t')
            record_type = parts[0]
            
            if record_type == '@HD':
                for field in parts[1:]:
                    if field.startswith('VN:'):
                        header.version = field[3:]
                    elif field.startswith('SO:'):
                        header.sort_order = field[3:]
            
            elif record_type == '@SQ':
                ref = {}
                for field in parts[1:]:
                    if field.startswith('SN:'):
                        ref['name'] = field[3:]
                    elif field.startswith('LN:'):
                        ref['length'] = int(field[3:])
                    elif field.startswith('M5:'):
                        ref['md5'] = field[3:]
                header.references.append(ref)
            
            elif record_type == '@RG':
                rg = {}
                for field in parts[1:]:
                    if field.startswith('ID:'):
                        rg['id'] = field[3:]
                    elif field.startswith('SM:'):
                        rg['sample'] = field[3:]
                    elif field.startswith('PL:'):
                        rg['platform'] = field[3:]
                header.read_groups.append(rg)
            
            elif record_type == '@PG':
                pg = {}
                for field in parts[1:]:
                    if field.startswith('ID:'):
                        pg['id'] = field[3:]
                    elif field.startswith('PN:'):
                        pg['name'] = field[3:]
                    elif field.startswith('VN:'):
                        pg['version'] = field[3:]
                    elif field.startswith('CL:'):
                        pg['command'] = field[3:]
                header.programs.append(pg)
            
            elif record_type == '@CO':
                header.comments.append('\t'.join(parts[1:]))
        
        return header


@dataclass
class SAMRecord:
    """SAM alignment record."""
    qname: str
    flag: int
    rname: str
    pos: int  # 1-based
    mapq: int
    cigar: str
    rnext: str
    pnext: int
    tlen: int
    seq: str
    qual: str
    tags: Dict = field(default_factory=dict)
    
    @property
    def is_paired(self) -> bool:
        return bool(self.flag & 0x1)
    
    @property
    def is_proper_pair(self) -> bool:
        return bool(self.flag & 0x2)
    
    @property
    def is_unmapped(self) -> bool:
        return bool(self.flag & 0x4)
    
    @property
    def is_mate_unmapped(self) -> bool:
        return bool(self.flag & 0x8)
    
    @property
    def is_reverse(self) -> bool:
        return bool(self.flag & 0x10)
    
    @property
    def is_mate_reverse(self) -> bool:
        return bool(self.flag & 0x20)
    
    @property
    def is_read1(self) -> bool:
        return bool(self.flag & 0x40)
    
    @property
    def is_read2(self) -> bool:
        return bool(self.flag & 0x80)
    
    @property
    def is_secondary(self) -> bool:
        return bool(self.flag & 0x100)
    
    @property
    def is_failed(self) -> bool:
        return bool(self.flag & 0x200)
    
    @property
    def is_duplicate(self) -> bool:
        return bool(self.flag & 0x400)
    
    @property
    def is_supplementary(self) -> bool:
        return bool(self.flag & 0x800)
    
    def to_string(self) -> str:
        """Convert to SAM format line."""
        fields = [
            self.qname,
            str(self.flag),
            self.rname,
            str(self.pos),
            str(self.mapq),
            self.cigar,
            self.rnext,
            str(self.pnext),
            str(self.tlen),
            self.seq,
            self.qual,
        ]
        
        for tag, (tag_type, value) in self.tags.items():
            fields.append(f"{tag}:{tag_type}:{value}")
        
        return '\t'.join(fields)
    
    @classmethod
    def from_string(cls, line: str) -> "SAMRecord":
        """Parse SAM record from line."""
        fields = line.strip().split('\t')
        
        tags = {}
        for field in fields[11:]:
            match = re.match(r'(\w+):(\w):(.+)', field)
            if match:
                tag_name, tag_type, value = match.groups()
                if tag_type == 'i':
                    value = int(value)
                elif tag_type == 'f':
                    value = float(value)
                tags[tag_name] = (tag_type, value)
        
        return cls(
            qname=fields[0],
            flag=int(fields[1]),
            rname=fields[2],
            pos=int(fields[3]),
            mapq=int(fields[4]),
            cigar=fields[5],
            rnext=fields[6],
            pnext=int(fields[7]),
            tlen=int(fields[8]),
            seq=fields[9],
            qual=fields[10] if len(fields) > 10 else "*",
            tags=tags,
        )


class SAMReader:
    """Read SAM files."""
    
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.header = None
    
    def __iter__(self) -> Iterator[SAMRecord]:
        """Iterate over alignments."""
        header_lines = []
        
        with open(self.filepath, 'r') as f:
            for line in f:
                if line.startswith('@'):
                    header_lines.append(line)
                else:
                    if header_lines and self.header is None:
                        self.header = SAMHeader.from_string(''.join(header_lines))
                    
                    yield SAMRecord.from_string(line)
    
    def get_header(self) -> SAMHeader:
        """Get SAM header."""
        if self.header is None:
            header_lines = []
            with open(self.filepath, 'r') as f:
                for line in f:
                    if line.startswith('@'):
                        header_lines.append(line)
                    else:
                        break
            self.header = SAMHeader.from_string(''.join(header_lines))
        
        return self.header


class SAMWriter:
    """Write SAM files."""
    
    def __init__(self, filepath: str, header: SAMHeader):
        self.filepath = Path(filepath)
        self.header = header
        self.file = None
    
    def __enter__(self):
        self.file = open(self.filepath, 'w')
        self.file.write(self.header.to_string() + '\n')
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()
    
    def write(self, record: SAMRecord):
        """Write alignment record."""
        if self.file:
            self.file.write(record.to_string() + '\n')


class CIGARParser:
    """Parse and manipulate CIGAR strings."""
    
    OPERATIONS = {
        'M': 'alignment match',
        'I': 'insertion',
        'D': 'deletion',
        'N': 'skipped region',
        'S': 'soft clipping',
        'H': 'hard clipping',
        'P': 'padding',
        '=': 'sequence match',
        'X': 'sequence mismatch',
    }
    
    @staticmethod
    def parse(cigar: str) -> List[Tuple[int, str]]:
        """Parse CIGAR into list of (length, operation)."""
        pattern = re.compile(r'(\d+)([MIDNSHP=X])')
        return [(int(m.group(1)), m.group(2)) for m in pattern.finditer(cigar)]
    
    @staticmethod
    def reference_length(cigar: str) -> int:
        """Calculate reference length consumed by CIGAR."""
        total = 0
        for length, op in CIGARParser.parse(cigar):
            if op in 'MDN=X':
                total += length
        return total
    
    @staticmethod
    def query_length(cigar: str) -> int:
        """Calculate query length consumed by CIGAR."""
        total = 0
        for length, op in CIGARParser.parse(cigar):
            if op in 'MIS=X':
                total += length
        return total
    
    @staticmethod
    def aligned_pairs(cigar: str, ref_start: int) -> List[Tuple[Optional[int], Optional[int]]]:
        """Generate aligned pairs (query_pos, ref_pos)."""
        pairs = []
        query_pos = 0
        ref_pos = ref_start
        
        for length, op in CIGARParser.parse(cigar):
            if op in 'M=X':
                for i in range(length):
                    pairs.append((query_pos, ref_pos))
                    query_pos += 1
                    ref_pos += 1
            elif op == 'I':
                for i in range(length):
                    pairs.append((query_pos, None))
                    query_pos += 1
            elif op == 'D':
                for i in range(length):
                    pairs.append((None, ref_pos))
                    ref_pos += 1
            elif op == 'N':
                ref_pos += length
            elif op == 'S':
                query_pos += length
        
        return pairs
    
    @staticmethod
    def to_string(operations: List[Tuple[int, str]]) -> str:
        """Convert operations back to CIGAR string."""
        return ''.join(f"{length}{op}" for length, op in operations)
    
    @staticmethod
    def simplify(cigar: str) -> str:
        """Simplify CIGAR by merging adjacent same operations."""
        ops = CIGARParser.parse(cigar)
        if not ops:
            return cigar
        
        simplified = [ops[0]]
        
        for length, op in ops[1:]:
            if op == simplified[-1][1]:
                simplified[-1] = (simplified[-1][0] + length, op)
            else:
                simplified.append((length, op))
        
        return CIGARParser.to_string(simplified)

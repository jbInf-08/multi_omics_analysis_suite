"""
Bioinformatics File Format Parsers
==================================

Parsers for common bioinformatics file formats including FASTA, FASTQ,
GFF/GTF, BED, SAM/BAM, VCF, and GenBank.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Iterator, Union, TextIO, Tuple
from pathlib import Path
import gzip
import re
from datetime import datetime

from .sequence import DNASequence, RNASequence, ProteinSequence, SequenceQuality, SequenceCollection


@dataclass
class FastaRecord:
    """FASTA record."""
    id: str
    sequence: str
    description: str = ""
    
    def to_dna(self) -> DNASequence:
        return DNASequence(self.sequence, id=self.id, description=self.description)
    
    def to_rna(self) -> RNASequence:
        return RNASequence(self.sequence, id=self.id, description=self.description)
    
    def to_protein(self) -> ProteinSequence:
        return ProteinSequence(self.sequence, id=self.id, description=self.description)


@dataclass
class FastqRecord:
    """FASTQ record with quality scores."""
    id: str
    sequence: str
    quality: str
    description: str = ""
    
    @property
    def quality_scores(self) -> List[int]:
        """Convert quality string to Phred scores (Phred+33)."""
        return [ord(c) - 33 for c in self.quality]
    
    @property
    def mean_quality(self) -> float:
        """Calculate mean quality score."""
        scores = self.quality_scores
        return sum(scores) / len(scores) if scores else 0.0
    
    def to_dna(self) -> DNASequence:
        quality = SequenceQuality(self.quality_scores)
        return DNASequence(self.sequence, id=self.id, description=self.description, quality=quality)
    
    def trim(self, min_quality: int = 20) -> "FastqRecord":
        """Trim low-quality bases from ends."""
        scores = self.quality_scores
        
        # Find trim positions
        start, end = 0, len(scores)
        
        for i, q in enumerate(scores):
            if q >= min_quality:
                start = i
                break
        
        for i in range(len(scores) - 1, -1, -1):
            if scores[i] >= min_quality:
                end = i + 1
                break
        
        return FastqRecord(
            id=self.id,
            sequence=self.sequence[start:end],
            quality=self.quality[start:end],
            description=self.description,
        )


@dataclass
class GFFFeature:
    """GFF/GTF feature record."""
    seqid: str
    source: str
    feature_type: str
    start: int  # 1-based
    end: int    # 1-based, inclusive
    score: Optional[float]
    strand: str  # +, -, .
    phase: Optional[int]  # 0, 1, 2 for CDS
    attributes: Dict[str, str]
    
    @property
    def length(self) -> int:
        return self.end - self.start + 1
    
    def get_attribute(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self.attributes.get(key, default)


@dataclass
class BEDRecord:
    """BED format record."""
    chrom: str
    start: int  # 0-based
    end: int    # 0-based, exclusive
    name: Optional[str] = None
    score: Optional[int] = None
    strand: Optional[str] = None
    thick_start: Optional[int] = None
    thick_end: Optional[int] = None
    item_rgb: Optional[str] = None
    block_count: Optional[int] = None
    block_sizes: Optional[List[int]] = None
    block_starts: Optional[List[int]] = None
    
    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass
class SAMAlignment:
    """SAM alignment record."""
    qname: str  # Query name
    flag: int   # Bitwise flag
    rname: str  # Reference name
    pos: int    # 1-based position
    mapq: int   # Mapping quality
    cigar: str  # CIGAR string
    rnext: str  # Next reference name
    pnext: int  # Next position
    tlen: int   # Template length
    seq: str    # Sequence
    qual: str   # Quality scores
    tags: Dict[str, Tuple[str, any]] = field(default_factory=dict)
    
    @property
    def is_mapped(self) -> bool:
        return not (self.flag & 0x4)
    
    @property
    def is_reverse(self) -> bool:
        return bool(self.flag & 0x10)
    
    @property
    def is_paired(self) -> bool:
        return bool(self.flag & 0x1)
    
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
    def is_supplementary(self) -> bool:
        return bool(self.flag & 0x800)
    
    @property
    def is_duplicate(self) -> bool:
        return bool(self.flag & 0x400)
    
    def get_aligned_pairs(self) -> List[Tuple[Optional[int], Optional[int]]]:
        """Get aligned positions (query, reference) from CIGAR."""
        pairs = []
        query_pos = 0
        ref_pos = self.pos - 1  # Convert to 0-based
        
        for length, op in self._parse_cigar():
            if op == 'M' or op == '=' or op == 'X':  # Match/mismatch
                for i in range(length):
                    pairs.append((query_pos, ref_pos))
                    query_pos += 1
                    ref_pos += 1
            elif op == 'I':  # Insertion
                for i in range(length):
                    pairs.append((query_pos, None))
                    query_pos += 1
            elif op == 'D':  # Deletion
                for i in range(length):
                    pairs.append((None, ref_pos))
                    ref_pos += 1
            elif op == 'N':  # Skipped region
                ref_pos += length
            elif op == 'S':  # Soft clip
                query_pos += length
            elif op == 'H':  # Hard clip
                pass
            elif op == 'P':  # Padding
                pass
        
        return pairs
    
    def _parse_cigar(self) -> List[Tuple[int, str]]:
        """Parse CIGAR string."""
        pattern = re.compile(r'(\d+)([MIDNSHP=X])')
        return [(int(m.group(1)), m.group(2)) for m in pattern.finditer(self.cigar)]
    
    def get_reference_positions(self) -> List[int]:
        """Get reference positions covered by this alignment."""
        positions = []
        ref_pos = self.pos - 1
        
        for length, op in self._parse_cigar():
            if op in ['M', '=', 'X', 'D', 'N']:
                positions.extend(range(ref_pos, ref_pos + length))
                ref_pos += length
        
        return positions


@dataclass
class VCFVariant:
    """VCF variant record."""
    chrom: str
    pos: int    # 1-based
    id: str
    ref: str
    alt: List[str]
    qual: Optional[float]
    filter: List[str]
    info: Dict[str, any]
    format_fields: List[str] = field(default_factory=list)
    samples: Dict[str, Dict[str, any]] = field(default_factory=dict)
    
    @property
    def is_snp(self) -> bool:
        return len(self.ref) == 1 and all(len(a) == 1 for a in self.alt)
    
    @property
    def is_indel(self) -> bool:
        return len(self.ref) != 1 or any(len(a) != 1 for a in self.alt)
    
    @property
    def is_deletion(self) -> bool:
        return any(len(a) < len(self.ref) for a in self.alt)
    
    @property
    def is_insertion(self) -> bool:
        return any(len(a) > len(self.ref) for a in self.alt)
    
    @property
    def is_passed(self) -> bool:
        return self.filter == ['.'] or self.filter == ['PASS']
    
    def get_genotype(self, sample: str) -> Optional[str]:
        """Get genotype for a sample."""
        if sample in self.samples and 'GT' in self.samples[sample]:
            return self.samples[sample]['GT']
        return None


@dataclass
class GenBankFeature:
    """GenBank feature."""
    type: str
    location: str
    qualifiers: Dict[str, List[str]]
    
    def get_qualifier(self, key: str) -> Optional[str]:
        values = self.qualifiers.get(key, [])
        return values[0] if values else None


@dataclass
class GenBankRecord:
    """GenBank record."""
    locus: str
    length: int
    molecule_type: str
    topology: str  # linear or circular
    division: str
    date: str
    definition: str
    accession: str
    version: str
    keywords: List[str]
    source: str
    organism: str
    taxonomy: List[str]
    references: List[Dict]
    features: List[GenBankFeature]
    sequence: str
    
    def get_features_by_type(self, feature_type: str) -> List[GenBankFeature]:
        return [f for f in self.features if f.type == feature_type]
    
    def get_cds_features(self) -> List[GenBankFeature]:
        return self.get_features_by_type('CDS')
    
    def get_gene_features(self) -> List[GenBankFeature]:
        return self.get_features_by_type('gene')


class FileParser(ABC):
    """Abstract base class for file parsers."""
    
    @abstractmethod
    def parse(self, filepath: Union[str, Path]) -> Iterator:
        """Parse file and yield records."""
        pass
    
    def _open_file(self, filepath: Union[str, Path]) -> TextIO:
        """Open file, handling gzip compression."""
        filepath = Path(filepath)
        if filepath.suffix == '.gz':
            return gzip.open(filepath, 'rt')
        return open(filepath, 'r')


class FastaParser(FileParser):
    """FASTA file parser."""
    
    def parse(self, filepath: Union[str, Path]) -> Iterator[FastaRecord]:
        """Parse FASTA file and yield records."""
        with self._open_file(filepath) as f:
            current_id = None
            current_desc = ""
            current_seq = []
            
            for line in f:
                line = line.rstrip()
                
                if line.startswith('>'):
                    # Yield previous record
                    if current_id is not None:
                        yield FastaRecord(
                            id=current_id,
                            sequence=''.join(current_seq),
                            description=current_desc,
                        )
                    
                    # Parse header
                    header = line[1:]
                    parts = header.split(None, 1)
                    current_id = parts[0]
                    current_desc = parts[1] if len(parts) > 1 else ""
                    current_seq = []
                else:
                    current_seq.append(line)
            
            # Yield last record
            if current_id is not None:
                yield FastaRecord(
                    id=current_id,
                    sequence=''.join(current_seq),
                    description=current_desc,
                )
    
    def parse_to_collection(self, filepath: Union[str, Path]) -> SequenceCollection:
        """Parse FASTA to SequenceCollection."""
        sequences = []
        for record in self.parse(filepath):
            # Guess sequence type
            seq_upper = record.sequence.upper()
            if 'U' in seq_upper:
                sequences.append(record.to_rna())
            elif set(seq_upper) - {'A', 'C', 'G', 'T', 'N', '-', '.'}:
                sequences.append(record.to_protein())
            else:
                sequences.append(record.to_dna())
        
        return SequenceCollection(sequences, name=Path(filepath).stem)
    
    @staticmethod
    def write(records: List[FastaRecord], filepath: Union[str, Path], line_width: int = 60):
        """Write FASTA records to file."""
        with open(filepath, 'w') as f:
            for record in records:
                f.write(f">{record.id}")
                if record.description:
                    f.write(f" {record.description}")
                f.write("\n")
                
                # Write sequence in lines
                for i in range(0, len(record.sequence), line_width):
                    f.write(record.sequence[i:i + line_width] + "\n")


class FastqParser(FileParser):
    """FASTQ file parser."""
    
    def parse(self, filepath: Union[str, Path]) -> Iterator[FastqRecord]:
        """Parse FASTQ file and yield records."""
        with self._open_file(filepath) as f:
            while True:
                # Read 4 lines
                header = f.readline().rstrip()
                if not header:
                    break
                
                sequence = f.readline().rstrip()
                plus = f.readline().rstrip()
                quality = f.readline().rstrip()
                
                if not header.startswith('@'):
                    raise ValueError(f"Invalid FASTQ header: {header}")
                
                # Parse header
                header_parts = header[1:].split(None, 1)
                seq_id = header_parts[0]
                description = header_parts[1] if len(header_parts) > 1 else ""
                
                yield FastqRecord(
                    id=seq_id,
                    sequence=sequence,
                    quality=quality,
                    description=description,
                )
    
    def parse_paired(
        self,
        filepath1: Union[str, Path],
        filepath2: Union[str, Path],
    ) -> Iterator[Tuple[FastqRecord, FastqRecord]]:
        """Parse paired-end FASTQ files."""
        parser1 = self.parse(filepath1)
        parser2 = self.parse(filepath2)
        
        for r1, r2 in zip(parser1, parser2):
            yield r1, r2
    
    @staticmethod
    def write(records: List[FastqRecord], filepath: Union[str, Path]):
        """Write FASTQ records to file."""
        with open(filepath, 'w') as f:
            for record in records:
                f.write(f"@{record.id}")
                if record.description:
                    f.write(f" {record.description}")
                f.write(f"\n{record.sequence}\n+\n{record.quality}\n")


class GFFParser(FileParser):
    """GFF/GTF file parser."""
    
    def __init__(self, format: str = "gff3"):
        self.format = format  # gff3 or gtf
    
    def parse(self, filepath: Union[str, Path]) -> Iterator[GFFFeature]:
        """Parse GFF/GTF file and yield features."""
        with self._open_file(filepath) as f:
            for line in f:
                line = line.rstrip()
                
                # Skip comments and empty lines
                if line.startswith('#') or not line:
                    continue
                
                fields = line.split('\t')
                if len(fields) < 8:
                    continue
                
                # Parse attributes
                attributes = self._parse_attributes(fields[8] if len(fields) > 8 else "")
                
                yield GFFFeature(
                    seqid=fields[0],
                    source=fields[1],
                    feature_type=fields[2],
                    start=int(fields[3]),
                    end=int(fields[4]),
                    score=float(fields[5]) if fields[5] != '.' else None,
                    strand=fields[6],
                    phase=int(fields[7]) if fields[7] != '.' else None,
                    attributes=attributes,
                )
    
    def _parse_attributes(self, attr_string: str) -> Dict[str, str]:
        """Parse attribute string."""
        attributes = {}
        
        if self.format == "gff3":
            # GFF3: key=value;key=value
            for pair in attr_string.split(';'):
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    attributes[key.strip()] = value.strip()
        else:
            # GTF: key "value"; key "value"
            pattern = re.compile(r'(\w+)\s+"([^"]*)"')
            for match in pattern.finditer(attr_string):
                attributes[match.group(1)] = match.group(2)
        
        return attributes
    
    def parse_genes(self, filepath: Union[str, Path]) -> Dict[str, List[GFFFeature]]:
        """Parse and group features by gene."""
        genes = {}
        
        for feature in self.parse(filepath):
            gene_id = feature.get_attribute('gene_id') or feature.get_attribute('ID')
            if gene_id:
                if gene_id not in genes:
                    genes[gene_id] = []
                genes[gene_id].append(feature)
        
        return genes


class BEDParser(FileParser):
    """BED file parser."""
    
    def parse(self, filepath: Union[str, Path]) -> Iterator[BEDRecord]:
        """Parse BED file and yield records."""
        with self._open_file(filepath) as f:
            for line in f:
                line = line.rstrip()
                
                # Skip track/browser lines and comments
                if line.startswith(('track', 'browser', '#')) or not line:
                    continue
                
                fields = line.split('\t')
                
                record = BEDRecord(
                    chrom=fields[0],
                    start=int(fields[1]),
                    end=int(fields[2]),
                )
                
                # Optional fields
                if len(fields) > 3:
                    record.name = fields[3]
                if len(fields) > 4:
                    record.score = int(fields[4]) if fields[4] != '.' else None
                if len(fields) > 5:
                    record.strand = fields[5]
                if len(fields) > 6:
                    record.thick_start = int(fields[6])
                if len(fields) > 7:
                    record.thick_end = int(fields[7])
                if len(fields) > 8:
                    record.item_rgb = fields[8]
                if len(fields) > 9:
                    record.block_count = int(fields[9])
                if len(fields) > 10:
                    record.block_sizes = [int(x) for x in fields[10].rstrip(',').split(',')]
                if len(fields) > 11:
                    record.block_starts = [int(x) for x in fields[11].rstrip(',').split(',')]
                
                yield record
    
    @staticmethod
    def write(records: List[BEDRecord], filepath: Union[str, Path]):
        """Write BED records to file."""
        with open(filepath, 'w') as f:
            for record in records:
                fields = [record.chrom, str(record.start), str(record.end)]
                
                if record.name is not None:
                    fields.append(record.name)
                if record.score is not None:
                    fields.append(str(record.score))
                if record.strand is not None:
                    fields.append(record.strand)
                
                f.write('\t'.join(fields) + '\n')


class SAMParser(FileParser):
    """SAM file parser."""
    
    def __init__(self):
        self.header = {}
    
    def parse(self, filepath: Union[str, Path]) -> Iterator[SAMAlignment]:
        """Parse SAM file and yield alignments."""
        with self._open_file(filepath) as f:
            for line in f:
                line = line.rstrip()
                
                if line.startswith('@'):
                    self._parse_header_line(line)
                    continue
                
                if not line:
                    continue
                
                fields = line.split('\t')
                
                # Parse optional tags
                tags = {}
                for tag_field in fields[11:]:
                    parts = tag_field.split(':', 2)
                    if len(parts) == 3:
                        tag_name, tag_type, tag_value = parts
                        if tag_type == 'i':
                            tag_value = int(tag_value)
                        elif tag_type == 'f':
                            tag_value = float(tag_value)
                        tags[tag_name] = (tag_type, tag_value)
                
                yield SAMAlignment(
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
                    qual=fields[10],
                    tags=tags,
                )
    
    def _parse_header_line(self, line: str):
        """Parse SAM header line."""
        if line.startswith('@HD'):
            self.header['HD'] = dict(pair.split(':') for pair in line.split('\t')[1:])
        elif line.startswith('@SQ'):
            if 'SQ' not in self.header:
                self.header['SQ'] = []
            self.header['SQ'].append(dict(pair.split(':') for pair in line.split('\t')[1:]))
        elif line.startswith('@RG'):
            if 'RG' not in self.header:
                self.header['RG'] = []
            self.header['RG'].append(dict(pair.split(':') for pair in line.split('\t')[1:]))
        elif line.startswith('@PG'):
            if 'PG' not in self.header:
                self.header['PG'] = []
            self.header['PG'].append(dict(pair.split(':') for pair in line.split('\t')[1:]))
    
    def get_reference_lengths(self) -> Dict[str, int]:
        """Get reference sequence lengths from header."""
        lengths = {}
        for sq in self.header.get('SQ', []):
            lengths[sq['SN']] = int(sq['LN'])
        return lengths


class VCFParser(FileParser):
    """VCF file parser."""
    
    def __init__(self):
        self.header = {
            'fileformat': None,
            'info': {},
            'format': {},
            'filter': {},
            'contig': {},
            'samples': [],
        }
    
    def parse(self, filepath: Union[str, Path]) -> Iterator[VCFVariant]:
        """Parse VCF file and yield variants."""
        with self._open_file(filepath) as f:
            for line in f:
                line = line.rstrip()
                
                if line.startswith('##'):
                    self._parse_meta_line(line)
                    continue
                
                if line.startswith('#CHROM'):
                    fields = line.split('\t')
                    self.header['samples'] = fields[9:] if len(fields) > 9 else []
                    continue
                
                if not line:
                    continue
                
                fields = line.split('\t')
                
                # Parse INFO
                info = {}
                if fields[7] != '.':
                    for item in fields[7].split(';'):
                        if '=' in item:
                            key, value = item.split('=', 1)
                            info[key] = value
                        else:
                            info[item] = True
                
                # Parse FORMAT and samples
                format_fields = fields[8].split(':') if len(fields) > 8 else []
                samples = {}
                
                for i, sample_name in enumerate(self.header['samples']):
                    if len(fields) > 9 + i:
                        sample_values = fields[9 + i].split(':')
                        samples[sample_name] = dict(zip(format_fields, sample_values))
                
                yield VCFVariant(
                    chrom=fields[0],
                    pos=int(fields[1]),
                    id=fields[2],
                    ref=fields[3],
                    alt=fields[4].split(','),
                    qual=float(fields[5]) if fields[5] != '.' else None,
                    filter=fields[6].split(';'),
                    info=info,
                    format_fields=format_fields,
                    samples=samples,
                )
    
    def _parse_meta_line(self, line: str):
        """Parse VCF meta-information line."""
        if line.startswith('##fileformat'):
            self.header['fileformat'] = line.split('=')[1]
        elif line.startswith('##INFO'):
            match = re.match(r'##INFO=<(.+)>', line)
            if match:
                info = self._parse_header_dict(match.group(1))
                self.header['info'][info.get('ID', '')] = info
        elif line.startswith('##FORMAT'):
            match = re.match(r'##FORMAT=<(.+)>', line)
            if match:
                fmt = self._parse_header_dict(match.group(1))
                self.header['format'][fmt.get('ID', '')] = fmt
        elif line.startswith('##FILTER'):
            match = re.match(r'##FILTER=<(.+)>', line)
            if match:
                filt = self._parse_header_dict(match.group(1))
                self.header['filter'][filt.get('ID', '')] = filt
        elif line.startswith('##contig'):
            match = re.match(r'##contig=<(.+)>', line)
            if match:
                contig = self._parse_header_dict(match.group(1))
                self.header['contig'][contig.get('ID', '')] = contig
    
    def _parse_header_dict(self, content: str) -> Dict[str, str]:
        """Parse header dictionary content."""
        result = {}
        # Handle quoted strings
        pattern = re.compile(r'(\w+)=(?:"([^"]*)"|([^,]*))')
        for match in pattern.finditer(content):
            key = match.group(1)
            value = match.group(2) if match.group(2) is not None else match.group(3)
            result[key] = value
        return result


class GenBankParser(FileParser):
    """GenBank file parser."""
    
    def parse(self, filepath: Union[str, Path]) -> Iterator[GenBankRecord]:
        """Parse GenBank file and yield records."""
        with self._open_file(filepath) as f:
            content = f.read()
        
        # Split into records
        records = content.split('//\n')
        
        for record_text in records:
            if not record_text.strip():
                continue
            
            record = self._parse_record(record_text)
            if record:
                yield record
    
    def _parse_record(self, text: str) -> Optional[GenBankRecord]:
        """Parse a single GenBank record."""
        lines = text.split('\n')
        
        # Initialize fields
        locus_info = {}
        definition = ""
        accession = ""
        version = ""
        keywords = []
        source = ""
        organism = ""
        taxonomy = []
        references = []
        features = []
        sequence = ""
        
        current_section = None
        current_feature = None
        
        for line in lines:
            if not line:
                continue
            
            # LOCUS line
            if line.startswith('LOCUS'):
                parts = line.split()
                locus_info = {
                    'locus': parts[1] if len(parts) > 1 else "",
                    'length': int(parts[2]) if len(parts) > 2 else 0,
                    'molecule_type': parts[4] if len(parts) > 4 else "",
                    'topology': parts[5] if len(parts) > 5 and parts[5] in ['linear', 'circular'] else "linear",
                    'division': parts[-2] if len(parts) > 6 else "",
                    'date': parts[-1] if len(parts) > 6 else "",
                }
            
            elif line.startswith('DEFINITION'):
                definition = line[12:].strip()
                current_section = 'DEFINITION'
            
            elif line.startswith('ACCESSION'):
                accession = line[12:].strip()
            
            elif line.startswith('VERSION'):
                version = line[12:].strip()
            
            elif line.startswith('KEYWORDS'):
                keywords = [k.strip() for k in line[12:].strip().rstrip('.').split(';')]
            
            elif line.startswith('SOURCE'):
                source = line[12:].strip()
                current_section = 'SOURCE'
            
            elif line.startswith('  ORGANISM'):
                organism = line[12:].strip()
                current_section = 'ORGANISM'
            
            elif line.startswith('FEATURES'):
                current_section = 'FEATURES'
            
            elif line.startswith('ORIGIN'):
                current_section = 'ORIGIN'
            
            elif current_section == 'DEFINITION' and line.startswith(' '):
                definition += ' ' + line.strip()
            
            elif current_section == 'ORGANISM' and line.startswith(' '):
                taxonomy.extend([t.strip() for t in line.strip().rstrip('.').split(';')])
            
            elif current_section == 'FEATURES':
                if line[5:6] != ' ' and line[0:5] == '     ':
                    # New feature
                    if current_feature:
                        features.append(current_feature)
                    
                    parts = line.split()
                    if len(parts) >= 2:
                        current_feature = GenBankFeature(
                            type=parts[0],
                            location=parts[1],
                            qualifiers={},
                        )
                elif line.startswith('                     /') and current_feature:
                    # Qualifier
                    qual_line = line[21:]
                    if '=' in qual_line:
                        key, value = qual_line.split('=', 1)
                        key = key.lstrip('/')
                        value = value.strip('"')
                        if key not in current_feature.qualifiers:
                            current_feature.qualifiers[key] = []
                        current_feature.qualifiers[key].append(value)
            
            elif current_section == 'ORIGIN':
                # Sequence data
                seq_match = re.findall(r'[acgt]+', line.lower())
                sequence += ''.join(seq_match)
        
        # Add last feature
        if current_feature:
            features.append(current_feature)
        
        if not locus_info:
            return None
        
        return GenBankRecord(
            locus=locus_info.get('locus', ''),
            length=locus_info.get('length', 0),
            molecule_type=locus_info.get('molecule_type', ''),
            topology=locus_info.get('topology', 'linear'),
            division=locus_info.get('division', ''),
            date=locus_info.get('date', ''),
            definition=definition,
            accession=accession,
            version=version,
            keywords=keywords,
            source=source,
            organism=organism,
            taxonomy=taxonomy,
            references=references,
            features=features,
            sequence=sequence.upper(),
        )

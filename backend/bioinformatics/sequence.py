"""Sequence Classes.
================

Core sequence classes for DNA, RNA, and protein sequences with
rich functionality for manipulation and analysis.
"""

import hashlib
import re
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field

# Genetic code tables
STANDARD_CODON_TABLE = {
    "TTT": "F",
    "TTC": "F",
    "TTA": "L",
    "TTG": "L",
    "TCT": "S",
    "TCC": "S",
    "TCA": "S",
    "TCG": "S",
    "TAT": "Y",
    "TAC": "Y",
    "TAA": "*",
    "TAG": "*",
    "TGT": "C",
    "TGC": "C",
    "TGA": "*",
    "TGG": "W",
    "CTT": "L",
    "CTC": "L",
    "CTA": "L",
    "CTG": "L",
    "CCT": "P",
    "CCC": "P",
    "CCA": "P",
    "CCG": "P",
    "CAT": "H",
    "CAC": "H",
    "CAA": "Q",
    "CAG": "Q",
    "CGT": "R",
    "CGC": "R",
    "CGA": "R",
    "CGG": "R",
    "ATT": "I",
    "ATC": "I",
    "ATA": "I",
    "ATG": "M",
    "ACT": "T",
    "ACC": "T",
    "ACA": "T",
    "ACG": "T",
    "AAT": "N",
    "AAC": "N",
    "AAA": "K",
    "AAG": "K",
    "AGT": "S",
    "AGC": "S",
    "AGA": "R",
    "AGG": "R",
    "GTT": "V",
    "GTC": "V",
    "GTA": "V",
    "GTG": "V",
    "GCT": "A",
    "GCC": "A",
    "GCA": "A",
    "GCG": "A",
    "GAT": "D",
    "GAC": "D",
    "GAA": "E",
    "GAG": "E",
    "GGT": "G",
    "GGC": "G",
    "GGA": "G",
    "GGG": "G",
}

# Complement mappings
DNA_COMPLEMENT = {
    "A": "T",
    "T": "A",
    "G": "C",
    "C": "G",
    "N": "N",
    "a": "t",
    "t": "a",
    "g": "c",
    "c": "g",
    "n": "n",
}
RNA_COMPLEMENT = {
    "A": "U",
    "U": "A",
    "G": "C",
    "C": "G",
    "N": "N",
    "a": "u",
    "u": "a",
    "g": "c",
    "c": "g",
    "n": "n",
}


@dataclass
class SequenceQuality:
    """Quality scores for sequence data."""

    scores: list[int]
    encoding: str = "phred33"

    @property
    def mean_quality(self) -> float:
        """Calculate mean quality score."""
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def min_quality(self) -> int:
        """Get minimum quality score."""
        return min(self.scores) if self.scores else 0

    def trim_by_quality(self, min_qual: int = 20) -> tuple[int, int]:
        """Find trim positions based on quality threshold."""
        start = 0
        end = len(self.scores)

        # Trim from start
        for i, q in enumerate(self.scores):
            if q >= min_qual:
                start = i
                break

        # Trim from end
        for i in range(len(self.scores) - 1, -1, -1):
            if self.scores[i] >= min_qual:
                end = i + 1
                break

        return start, end


class Sequence(ABC):
    """Abstract base class for biological sequences."""

    def __init__(
        self,
        sequence: str,
        id: str | None = None,
        description: str | None = None,
        quality: SequenceQuality | None = None,
        annotations: dict | None = None,
    ):
        self._sequence = sequence.upper()
        self.id = id or self._generate_id()
        self.description = description or ""
        self.quality = quality
        self.annotations = annotations or {}
        self._validate()

    @property
    @abstractmethod
    def alphabet(self) -> set:
        """Valid characters for this sequence type."""
        pass

    @property
    @abstractmethod
    def sequence_type(self) -> str:
        """Type of sequence (DNA, RNA, protein)."""
        pass

    def _validate(self):
        """Validate sequence against alphabet."""
        invalid_chars = set(self._sequence) - self.alphabet - {"N", "X", "-", "."}
        if invalid_chars:
            raise ValueError(f"Invalid characters for {self.sequence_type}: {invalid_chars}")

    def _generate_id(self) -> str:
        """Generate a unique ID based on sequence hash."""
        return f"seq_{hashlib.md5(self._sequence.encode()).hexdigest()[:8]}"

    @property
    def seq(self) -> str:
        """Get sequence string."""
        return self._sequence

    def __len__(self) -> int:
        return len(self._sequence)

    def __str__(self) -> str:
        return self._sequence

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id='{self.id}', length={len(self)})"

    def __getitem__(self, key) -> str:
        return self._sequence[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._sequence)

    def __eq__(self, other) -> bool:
        if isinstance(other, Sequence):
            return self._sequence == other._sequence
        return self._sequence == str(other)

    def __hash__(self) -> int:
        return hash(self._sequence)

    def __contains__(self, item: str) -> bool:
        return item.upper() in self._sequence

    def __add__(self, other: "Sequence") -> "Sequence":
        if type(self) is not type(other):
            raise TypeError(f"Cannot concatenate {type(self)} with {type(other)}")
        return type(self)(self._sequence + other._sequence)

    def count(self, pattern: str) -> int:
        """Count occurrences of a pattern."""
        return self._sequence.count(pattern.upper())

    def find(self, pattern: str, start: int = 0, end: int | None = None) -> int:
        """Find first occurrence of pattern."""
        return self._sequence.find(pattern.upper(), start, end)

    def find_all(self, pattern: str) -> list[int]:
        """Find all occurrences of pattern."""
        positions = []
        start = 0
        while True:
            pos = self._sequence.find(pattern.upper(), start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1
        return positions

    def composition(self) -> dict[str, int]:
        """Get base/residue composition."""
        return dict(Counter(self._sequence))

    def frequency(self) -> dict[str, float]:
        """Get base/residue frequency."""
        comp = self.composition()
        total = len(self._sequence)
        return {k: v / total for k, v in comp.items()}

    def to_fasta(self, line_width: int = 60) -> str:
        """Convert to FASTA format."""
        header = f">{self.id}"
        if self.description:
            header += f" {self.description}"

        lines = [header]
        for i in range(0, len(self._sequence), line_width):
            lines.append(self._sequence[i : i + line_width])

        return "\n".join(lines)

    def subsequence(self, start: int, end: int) -> "Sequence":
        """Extract a subsequence."""
        return type(self)(
            self._sequence[start:end],
            id=f"{self.id}_{start}_{end}",
            description=f"Subsequence of {self.id}",
        )


class DNASequence(Sequence):
    """DNA sequence class with DNA-specific methods."""

    @property
    def alphabet(self) -> set:
        return {"A", "T", "G", "C"}

    @property
    def sequence_type(self) -> str:
        return "DNA"

    def complement(self) -> "DNASequence":
        """Get complement sequence."""
        comp_seq = "".join(DNA_COMPLEMENT.get(base, "N") for base in self._sequence)
        return DNASequence(comp_seq, id=f"{self.id}_complement")

    def reverse_complement(self) -> "DNASequence":
        """Get reverse complement sequence."""
        comp = self.complement()
        return DNASequence(comp.seq[::-1], id=f"{self.id}_revcomp")

    def gc_content(self) -> float:
        """Calculate GC content."""
        gc = self._sequence.count("G") + self._sequence.count("C")
        return gc / len(self._sequence) if len(self._sequence) > 0 else 0.0

    def gc_skew(self, window: int = 1000, step: int = 100) -> list[tuple[int, float]]:
        """Calculate GC skew along sequence."""
        skews = []
        for i in range(0, len(self._sequence) - window + 1, step):
            subseq = self._sequence[i : i + window]
            g = subseq.count("G")
            c = subseq.count("C")
            skew = (g - c) / (g + c) if (g + c) > 0 else 0
            skews.append((i + window // 2, skew))
        return skews

    def transcribe(self) -> "RNASequence":
        """Transcribe DNA to RNA."""
        return RNASequence(
            self._sequence.replace("T", "U"),
            id=f"{self.id}_rna",
            description=f"Transcribed from {self.id}",
        )

    def translate(
        self,
        frame: int = 0,
        to_stop: bool = False,
        codon_table: dict | None = None,
    ) -> "ProteinSequence":
        """Translate DNA to protein sequence."""
        if frame not in [0, 1, 2]:
            raise ValueError("Frame must be 0, 1, or 2")

        table = codon_table or STANDARD_CODON_TABLE
        seq = self._sequence[frame:]
        protein = []

        for i in range(0, len(seq) - 2, 3):
            codon = seq[i : i + 3]
            aa = "X" if "N" in codon else table.get(codon, "X")

            if aa == "*" and to_stop:
                break
            protein.append(aa)

        return ProteinSequence(
            "".join(protein),
            id=f"{self.id}_protein_frame{frame}",
            description=f"Translated from {self.id} frame {frame}",
        )

    def find_orfs(
        self,
        min_length: int = 100,
        start_codons: list[str] = None,
        stop_codons: list[str] = None,
    ) -> list[dict]:
        """Find open reading frames."""
        start_codons = start_codons or ["ATG"]
        stop_codons = stop_codons or ["TAA", "TAG", "TGA"]
        orfs = []

        for frame in range(3):
            seq = self._sequence[frame:]
            i = 0

            while i < len(seq) - 2:
                codon = seq[i : i + 3]

                if codon in start_codons:
                    # Find stop codon
                    for j in range(i + 3, len(seq) - 2, 3):
                        stop_codon = seq[j : j + 3]
                        if stop_codon in stop_codons:
                            orf_length = j - i + 3
                            if orf_length >= min_length:
                                orfs.append(
                                    {
                                        "start": i + frame,
                                        "end": j + frame + 3,
                                        "length": orf_length,
                                        "frame": frame,
                                        "strand": "+",
                                        "sequence": seq[i : j + 3],
                                    }
                                )
                            break
                i += 3

        # Check reverse strand
        revcomp = self.reverse_complement()
        for frame in range(3):
            seq = revcomp.seq[frame:]
            i = 0

            while i < len(seq) - 2:
                codon = seq[i : i + 3]

                if codon in start_codons:
                    for j in range(i + 3, len(seq) - 2, 3):
                        stop_codon = seq[j : j + 3]
                        if stop_codon in stop_codons:
                            orf_length = j - i + 3
                            if orf_length >= min_length:
                                # Convert coordinates back to original strand
                                orig_end = len(self._sequence) - (i + frame)
                                orig_start = orig_end - orf_length
                                orfs.append(
                                    {
                                        "start": orig_start,
                                        "end": orig_end,
                                        "length": orf_length,
                                        "frame": frame,
                                        "strand": "-",
                                        "sequence": seq[i : j + 3],
                                    }
                                )
                            break
                i += 3

        return sorted(orfs, key=lambda x: x["start"])

    def melting_temperature(self, method: str = "basic") -> float:
        """Calculate melting temperature."""
        if method == "basic":
            # Basic formula for short oligos
            if len(self._sequence) < 14:
                return 2 * (self._sequence.count("A") + self._sequence.count("T")) + 4 * (
                    self._sequence.count("G") + self._sequence.count("C")
                )
            else:
                # Wallace rule
                return 64.9 + 41 * (
                    self._sequence.count("G") + self._sequence.count("C") - 16.4
                ) / len(self._sequence)
        elif method == "nearest_neighbor":
            # Simplified nearest neighbor (would need full implementation)
            return 64.9 + 41 * self.gc_content() - 500 / len(self._sequence)
        else:
            raise ValueError(f"Unknown method: {method}")

    def find_restriction_sites(self, enzyme_patterns: dict[str, str]) -> dict[str, list[int]]:
        """Find restriction enzyme cut sites."""
        sites = {}
        for enzyme, pattern in enzyme_patterns.items():
            # Handle IUPAC codes
            regex_pattern = self._iupac_to_regex(pattern)
            matches = list(re.finditer(regex_pattern, self._sequence))
            if matches:
                sites[enzyme] = [m.start() for m in matches]
        return sites

    def _iupac_to_regex(self, pattern: str) -> str:
        """Convert IUPAC codes to regex."""
        iupac = {
            "R": "[AG]",
            "Y": "[CT]",
            "S": "[GC]",
            "W": "[AT]",
            "K": "[GT]",
            "M": "[AC]",
            "B": "[CGT]",
            "D": "[AGT]",
            "H": "[ACT]",
            "V": "[ACG]",
            "N": "[ACGT]",
        }
        regex = ""
        for char in pattern.upper():
            regex += iupac.get(char, char)
        return regex

    def cpg_islands(
        self,
        min_length: int = 200,
        min_gc: float = 0.5,
        min_obs_exp: float = 0.6,
    ) -> list[dict]:
        """Find CpG islands."""
        islands = []
        window = min_length

        for i in range(0, len(self._sequence) - window + 1, 50):
            subseq = self._sequence[i : i + window]

            # Calculate GC content
            gc = (subseq.count("G") + subseq.count("C")) / len(subseq)
            if gc < min_gc:
                continue

            # Calculate observed/expected CpG ratio
            cpg_count = subseq.count("CG")
            c_count = subseq.count("C")
            g_count = subseq.count("G")

            if c_count == 0 or g_count == 0:
                continue

            expected_cpg = (c_count * g_count) / len(subseq)
            obs_exp = cpg_count / expected_cpg if expected_cpg > 0 else 0

            if obs_exp >= min_obs_exp:
                islands.append(
                    {
                        "start": i,
                        "end": i + window,
                        "gc_content": gc,
                        "obs_exp_ratio": obs_exp,
                        "cpg_count": cpg_count,
                    }
                )

        # Merge overlapping islands
        merged = []
        for island in sorted(islands, key=lambda x: x["start"]):
            if merged and island["start"] <= merged[-1]["end"]:
                merged[-1]["end"] = max(merged[-1]["end"], island["end"])
            else:
                merged.append(island)

        return merged


class RNASequence(Sequence):
    """RNA sequence class with RNA-specific methods."""

    @property
    def alphabet(self) -> set:
        return {"A", "U", "G", "C"}

    @property
    def sequence_type(self) -> str:
        return "RNA"

    def complement(self) -> "RNASequence":
        """Get complement sequence."""
        comp_seq = "".join(RNA_COMPLEMENT.get(base, "N") for base in self._sequence)
        return RNASequence(comp_seq, id=f"{self.id}_complement")

    def reverse_complement(self) -> "RNASequence":
        """Get reverse complement sequence."""
        comp = self.complement()
        return RNASequence(comp.seq[::-1], id=f"{self.id}_revcomp")

    def to_dna(self) -> DNASequence:
        """Convert RNA to DNA."""
        return DNASequence(
            self._sequence.replace("U", "T"),
            id=f"{self.id}_dna",
        )

    def translate(
        self,
        frame: int = 0,
        to_stop: bool = False,
    ) -> "ProteinSequence":
        """Translate RNA to protein."""
        return self.to_dna().translate(frame, to_stop)

    def gc_content(self) -> float:
        """Calculate GC content."""
        gc = self._sequence.count("G") + self._sequence.count("C")
        return gc / len(self._sequence) if len(self._sequence) > 0 else 0.0

    def find_secondary_structure_motifs(self) -> list[dict]:
        """Find potential secondary structure motifs (stem-loops)."""
        motifs = []
        # Simplified stem-loop finder
        min_stem = 4
        min_loop = 3
        max_loop = 8

        for i in range(len(self._sequence) - min_stem * 2 - min_loop):
            for stem_len in range(min_stem, 15):
                for loop_len in range(min_loop, max_loop + 1):
                    if i + stem_len * 2 + loop_len > len(self._sequence):
                        continue

                    stem1 = self._sequence[i : i + stem_len]
                    loop = self._sequence[i + stem_len : i + stem_len + loop_len]
                    stem2 = self._sequence[i + stem_len + loop_len : i + stem_len * 2 + loop_len]

                    # Check if stems are complementary
                    rev_stem2 = stem2[::-1]
                    matches = sum(
                        1
                        for a, b in zip(stem1, rev_stem2, strict=False)
                        if (a, b)
                        in [("A", "U"), ("U", "A"), ("G", "C"), ("C", "G"), ("G", "U"), ("U", "G")]
                    )

                    if matches >= stem_len * 0.8:  # 80% base pairing
                        motifs.append(
                            {
                                "start": i,
                                "end": i + stem_len * 2 + loop_len,
                                "stem_length": stem_len,
                                "loop_length": loop_len,
                                "stem1": stem1,
                                "loop": loop,
                                "stem2": stem2,
                                "stability": matches / stem_len,
                            }
                        )

        return motifs


class ProteinSequence(Sequence):
    """Protein sequence class with protein-specific methods."""

    AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")

    # Amino acid properties
    HYDROPHOBICITY = {
        "A": 1.8,
        "R": -4.5,
        "N": -3.5,
        "D": -3.5,
        "C": 2.5,
        "Q": -3.5,
        "E": -3.5,
        "G": -0.4,
        "H": -3.2,
        "I": 4.5,
        "L": 3.8,
        "K": -3.9,
        "M": 1.9,
        "F": 2.8,
        "P": -1.6,
        "S": -0.8,
        "T": -0.7,
        "W": -0.9,
        "Y": -1.3,
        "V": 4.2,
    }

    MOLECULAR_WEIGHTS = {
        "A": 89.09,
        "R": 174.20,
        "N": 132.12,
        "D": 133.10,
        "C": 121.16,
        "Q": 146.15,
        "E": 147.13,
        "G": 75.07,
        "H": 155.16,
        "I": 131.17,
        "L": 131.17,
        "K": 146.19,
        "M": 149.21,
        "F": 165.19,
        "P": 115.13,
        "S": 105.09,
        "T": 119.12,
        "W": 204.23,
        "Y": 181.19,
        "V": 117.15,
    }

    @property
    def alphabet(self) -> set:
        return self.AMINO_ACIDS

    @property
    def sequence_type(self) -> str:
        return "protein"

    def molecular_weight(self) -> float:
        """Calculate molecular weight in Daltons."""
        weight = sum(self.MOLECULAR_WEIGHTS.get(aa, 0) for aa in self._sequence)
        # Subtract water for peptide bonds
        weight -= (len(self._sequence) - 1) * 18.015
        return weight

    def isoelectric_point(self) -> float:
        """Estimate isoelectric point (pI)."""
        # Simplified pI calculation using Henderson-Hasselbalch
        # pKa values
        pKa = {
            "N_term": 9.69,
            "C_term": 2.34,
            "D": 3.86,
            "E": 4.25,
            "C": 8.33,
            "Y": 10.07,
            "H": 6.00,
            "K": 10.53,
            "R": 12.48,
        }

        def charge_at_pH(pH: float) -> float:
            charge = 0.0
            # N-terminus
            charge += 1.0 / (1.0 + 10 ** (pH - pKa["N_term"]))
            # C-terminus
            charge -= 1.0 / (1.0 + 10 ** (pKa["C_term"] - pH))

            # Charged residues
            for aa in self._sequence:
                if aa in ["D", "E"]:
                    charge -= 1.0 / (1.0 + 10 ** (pKa.get(aa, 4.0) - pH))
                elif aa in ["K", "R", "H"]:
                    charge += 1.0 / (1.0 + 10 ** (pH - pKa.get(aa, 10.0)))
                elif aa == "C":
                    charge -= 1.0 / (1.0 + 10 ** (pKa["C"] - pH))
                elif aa == "Y":
                    charge -= 1.0 / (1.0 + 10 ** (pKa["Y"] - pH))

            return charge

        # Binary search for pI
        low, high = 0.0, 14.0
        while high - low > 0.01:
            mid = (low + high) / 2
            if charge_at_pH(mid) > 0:
                low = mid
            else:
                high = mid

        return (low + high) / 2

    def hydrophobicity_profile(self, window: int = 9) -> list[tuple[int, float]]:
        """Calculate Kyte-Doolittle hydrophobicity profile."""
        profile = []
        half_window = window // 2

        for i in range(half_window, len(self._sequence) - half_window):
            window_seq = self._sequence[i - half_window : i + half_window + 1]
            hydro = sum(self.HYDROPHOBICITY.get(aa, 0) for aa in window_seq) / window
            profile.append((i, hydro))

        return profile

    def find_domains(self) -> list[dict]:
        """Find potential protein domains based on sequence patterns."""
        domains = []

        # Common domain patterns (simplified)
        patterns = {
            "signal_peptide": r"^M[A-Z]{15,30}[AVILMFYW]{3,}",
            "transmembrane": r"[AVILMFYW]{18,25}",
            "nuclear_localization": r"[KR]{4,}|[KR][A-Z]{10,12}[KR]{3,}",
            "zinc_finger": r"C[A-Z]{2,4}C[A-Z]{12,14}H[A-Z]{3,5}H",
            "leucine_zipper": r"L[A-Z]{6}L[A-Z]{6}L[A-Z]{6}L",
        }

        for domain_name, pattern in patterns.items():
            matches = list(re.finditer(pattern, self._sequence))
            for match in matches:
                domains.append(
                    {
                        "type": domain_name,
                        "start": match.start(),
                        "end": match.end(),
                        "sequence": match.group(),
                    }
                )

        return domains

    def secondary_structure_propensity(self) -> dict[str, float]:
        """Estimate secondary structure propensity."""
        # Chou-Fasman parameters (simplified)
        helix_propensity = {
            "A": 1.42,
            "L": 1.21,
            "E": 1.51,
            "M": 1.45,
            "Q": 1.11,
            "K": 1.16,
            "R": 0.98,
            "H": 1.00,
            "V": 1.06,
            "I": 1.08,
            "Y": 0.69,
            "C": 0.70,
            "W": 1.08,
            "F": 1.13,
            "T": 0.83,
            "G": 0.57,
            "N": 0.67,
            "P": 0.57,
            "S": 0.77,
            "D": 1.01,
        }

        sheet_propensity = {
            "V": 1.70,
            "I": 1.60,
            "Y": 1.47,
            "F": 1.38,
            "W": 1.37,
            "L": 1.30,
            "T": 1.19,
            "C": 1.19,
            "M": 1.05,
            "A": 0.83,
            "R": 0.93,
            "G": 0.75,
            "D": 0.54,
            "K": 0.74,
            "S": 0.75,
            "H": 0.87,
            "N": 0.89,
            "Q": 1.10,
            "P": 0.55,
            "E": 0.37,
        }

        helix_score = sum(helix_propensity.get(aa, 1.0) for aa in self._sequence) / len(
            self._sequence
        )
        sheet_score = sum(sheet_propensity.get(aa, 1.0) for aa in self._sequence) / len(
            self._sequence
        )

        return {
            "helix_propensity": helix_score,
            "sheet_propensity": sheet_score,
            "coil_propensity": 2.0 - helix_score - sheet_score + 1.0,
        }

    def aromaticity(self) -> float:
        """Calculate aromaticity (frequency of aromatic amino acids)."""
        aromatic = ["F", "W", "Y"]
        count = sum(1 for aa in self._sequence if aa in aromatic)
        return count / len(self._sequence) if len(self._sequence) > 0 else 0.0

    def instability_index(self) -> float:
        """Calculate protein instability index."""
        # DIWV instability weights (simplified)
        diwv = {
            ("A", "A"): 1.0,
            ("A", "G"): 1.0,
            ("A", "L"): 1.0,
            ("D", "G"): 1.0,
            ("D", "P"): 1.0,
            # ... (would include full table in production)
        }

        score = 0.0
        for i in range(len(self._sequence) - 1):
            dipeptide = (self._sequence[i], self._sequence[i + 1])
            score += diwv.get(dipeptide, 1.0)

        return (10.0 / len(self._sequence)) * score


@dataclass
class SequenceCollection:
    """Collection of sequences with batch operations."""

    sequences: list[Sequence] = field(default_factory=list)
    name: str | None = None
    description: str | None = None

    def __len__(self) -> int:
        return len(self.sequences)

    def __iter__(self) -> Iterator[Sequence]:
        return iter(self.sequences)

    def __getitem__(self, key) -> Sequence:
        if isinstance(key, str):
            for seq in self.sequences:
                if seq.id == key:
                    return seq
            raise KeyError(f"Sequence with ID '{key}' not found")
        return self.sequences[key]

    def add(self, sequence: Sequence):
        """Add a sequence to the collection."""
        self.sequences.append(sequence)

    def remove(self, seq_id: str):
        """Remove a sequence by ID."""
        self.sequences = [s for s in self.sequences if s.id != seq_id]

    def filter_by_length(
        self, min_length: int = 0, max_length: int | None = None
    ) -> "SequenceCollection":
        """Filter sequences by length."""
        filtered = [s for s in self.sequences if len(s) >= min_length]
        if max_length:
            filtered = [s for s in filtered if len(s) <= max_length]
        return SequenceCollection(filtered, name=f"{self.name}_filtered")

    def filter_by_gc(self, min_gc: float = 0.0, max_gc: float = 1.0) -> "SequenceCollection":
        """Filter DNA/RNA sequences by GC content."""
        filtered = []
        for seq in self.sequences:
            if hasattr(seq, "gc_content"):
                gc = seq.gc_content()
                if min_gc <= gc <= max_gc:
                    filtered.append(seq)
        return SequenceCollection(filtered, name=f"{self.name}_gc_filtered")

    def statistics(self) -> dict:
        """Calculate collection statistics."""
        lengths = [len(s) for s in self.sequences]

        stats = {
            "count": len(self.sequences),
            "total_length": sum(lengths),
            "mean_length": sum(lengths) / len(lengths) if lengths else 0,
            "min_length": min(lengths) if lengths else 0,
            "max_length": max(lengths) if lengths else 0,
            "n50": self._calculate_n50(lengths),
        }

        # GC content for DNA/RNA
        gc_values = []
        for seq in self.sequences:
            if hasattr(seq, "gc_content"):
                gc_values.append(seq.gc_content())

        if gc_values:
            stats["mean_gc"] = sum(gc_values) / len(gc_values)

        return stats

    def _calculate_n50(self, lengths: list[int]) -> int:
        """Calculate N50 statistic."""
        if not lengths:
            return 0

        sorted_lengths = sorted(lengths, reverse=True)
        total = sum(sorted_lengths)
        cumsum = 0

        for length in sorted_lengths:
            cumsum += length
            if cumsum >= total / 2:
                return length

        return sorted_lengths[-1]

    def to_fasta(self) -> str:
        """Convert collection to FASTA format."""
        return "\n".join(seq.to_fasta() for seq in self.sequences)

    def consensus(self) -> Sequence | None:
        """Generate consensus sequence (requires aligned sequences)."""
        if not self.sequences:
            return None

        # Check all sequences are same length
        length = len(self.sequences[0])
        if not all(len(s) == length for s in self.sequences):
            raise ValueError("Sequences must be aligned (same length) for consensus")

        consensus = []
        for i in range(length):
            bases = [s[i] for s in self.sequences]
            counter = Counter(bases)
            # Get most common, excluding gaps
            for base, _count in counter.most_common():
                if base not in ["-", "."]:
                    consensus.append(base)
                    break
            else:
                consensus.append("-")

        # Return appropriate sequence type
        seq_type = type(self.sequences[0])
        return seq_type("".join(consensus), id="consensus")

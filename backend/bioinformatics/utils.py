"""Bioinformatics Utilities.
========================

Common utility functions for sequence analysis and manipulation.
"""

import math
import re
from collections import Counter

from .sequence import DNA_COMPLEMENT, STANDARD_CODON_TABLE


def reverse_complement(sequence: str) -> str:
    """Get reverse complement of DNA sequence.

    Args:
        sequence: DNA sequence string

    Returns:
        Reverse complement sequence

    """
    complement = "".join(DNA_COMPLEMENT.get(base, "N") for base in sequence.upper())
    return complement[::-1]


def translate(
    sequence: str,
    frame: int = 0,
    codon_table: dict[str, str] | None = None,
    to_stop: bool = False,
) -> str:
    """Translate DNA/RNA sequence to protein.

    Args:
        sequence: DNA or RNA sequence
        frame: Reading frame (0, 1, or 2)
        codon_table: Custom codon table (default: standard genetic code)
        to_stop: Stop at first stop codon

    Returns:
        Protein sequence

    """
    table = codon_table or STANDARD_CODON_TABLE

    # Convert RNA to DNA
    sequence = sequence.upper().replace("U", "T")

    protein = []
    seq = sequence[frame:]

    for i in range(0, len(seq) - 2, 3):
        codon = seq[i : i + 3]

        aa = "X" if "N" in codon else table.get(codon, "X")

        if aa == "*" and to_stop:
            break

        protein.append(aa)

    return "".join(protein)


def gc_content(sequence: str) -> float:
    """Calculate GC content of a sequence.

    Args:
        sequence: DNA or RNA sequence

    Returns:
        GC content as fraction (0-1)

    """
    sequence = sequence.upper()
    gc = sequence.count("G") + sequence.count("C")
    total = len(sequence)
    return gc / total if total > 0 else 0.0


def calculate_tm(
    sequence: str,
    method: str = "nearest_neighbor",
    na_conc: float = 50.0,  # mM Na+
    oligo_conc: float = 0.25,  # µM
) -> float:
    """Calculate melting temperature of DNA oligonucleotide.

    Args:
        sequence: DNA sequence
        method: Calculation method ('basic', 'salt_adjusted', 'nearest_neighbor')
        na_conc: Sodium concentration in mM
        oligo_conc: Oligonucleotide concentration in µM

    Returns:
        Melting temperature in Celsius

    """
    sequence = sequence.upper()
    n = len(sequence)

    if method == "basic":
        # Simple 2+4 rule for short oligos
        if n < 14:
            return 2 * (sequence.count("A") + sequence.count("T")) + 4 * (
                sequence.count("G") + sequence.count("C")
            )
        else:
            gc = gc_content(sequence)
            return 64.9 + 41 * (gc - 0.41) - 500 / n

    elif method == "salt_adjusted":
        gc = gc_content(sequence)
        return 81.5 + 16.6 * math.log10(na_conc / 1000) + 41 * gc - 500 / n

    elif method == "nearest_neighbor":
        # Nearest-neighbor thermodynamic parameters (SantaLucia, 1998)
        nn_params = {
            "AA": (-7.9, -22.2),
            "TT": (-7.9, -22.2),
            "AT": (-7.2, -20.4),
            "TA": (-7.2, -21.3),
            "CA": (-8.5, -22.7),
            "TG": (-8.5, -22.7),
            "GT": (-8.4, -22.4),
            "AC": (-8.4, -22.4),
            "CT": (-7.8, -21.0),
            "AG": (-7.8, -21.0),
            "GA": (-8.2, -22.2),
            "TC": (-8.2, -22.2),
            "CG": (-10.6, -27.2),
            "GC": (-9.8, -24.4),
            "GG": (-8.0, -19.9),
            "CC": (-8.0, -19.9),
        }

        # Initiation parameters
        delta_h = 0.0
        delta_s = 0.0

        # Sum up nearest-neighbor contributions
        for i in range(n - 1):
            dinuc = sequence[i : i + 2]
            if dinuc in nn_params:
                h, s = nn_params[dinuc]
                delta_h += h
                delta_s += s

        # Initiation correction
        delta_h += 0.2
        delta_s += -5.7

        # Salt correction
        delta_s += 0.368 * (n - 1) * math.log(na_conc / 1000)

        # Calculate Tm
        R = 1.987  # Gas constant cal/(mol·K)
        tm = (1000 * delta_h) / (delta_s + R * math.log(oligo_conc * 1e-6 / 4)) - 273.15

        return tm

    else:
        raise ValueError(f"Unknown method: {method}")


def find_orfs(
    sequence: str,
    min_length: int = 100,
    start_codons: list[str] = None,
    stop_codons: list[str] = None,
    both_strands: bool = True,
) -> list[dict]:
    """Find open reading frames in a DNA sequence.

    Args:
        sequence: DNA sequence
        min_length: Minimum ORF length in nucleotides
        start_codons: List of start codons
        stop_codons: List of stop codons
        both_strands: Search both strands

    Returns:
        List of ORF dictionaries with start, end, length, frame, strand, sequence

    """
    start_codons = start_codons or ["ATG"]
    stop_codons = stop_codons or ["TAA", "TAG", "TGA"]
    sequence = sequence.upper()

    orfs = []

    def find_orfs_in_strand(seq: str, strand: str):
        for frame in range(3):
            subseq = seq[frame:]
            i = 0

            while i < len(subseq) - 2:
                codon = subseq[i : i + 3]

                if codon in start_codons:
                    # Search for stop codon
                    for j in range(i + 3, len(subseq) - 2, 3):
                        stop_codon = subseq[j : j + 3]
                        if stop_codon in stop_codons:
                            orf_length = j - i + 3
                            if orf_length >= min_length:
                                if strand == "+":
                                    start_pos = i + frame
                                    end_pos = j + frame + 3
                                else:
                                    # Convert to original coordinates
                                    orig_len = len(seq)
                                    start_pos = orig_len - (j + frame + 3)
                                    end_pos = orig_len - (i + frame)

                                orfs.append(
                                    {
                                        "start": start_pos,
                                        "end": end_pos,
                                        "length": orf_length,
                                        "frame": frame,
                                        "strand": strand,
                                        "sequence": subseq[i : j + 3],
                                        "protein": translate(subseq[i : j + 3]),
                                    }
                                )
                            break
                i += 3

    # Forward strand
    find_orfs_in_strand(sequence, "+")

    # Reverse strand
    if both_strands:
        revcomp = reverse_complement(sequence)
        find_orfs_in_strand(revcomp, "-")

    return sorted(orfs, key=lambda x: x["start"])


def codon_usage(
    sequence: str,
    frame: int = 0,
) -> tuple[dict[str, int], dict[str, float]]:
    """Calculate codon usage statistics.

    Args:
        sequence: DNA/RNA sequence
        frame: Reading frame

    Returns:
        Tuple of (codon counts, codon frequencies)

    """
    sequence = sequence.upper().replace("U", "T")

    counts = Counter()
    seq = sequence[frame:]

    for i in range(0, len(seq) - 2, 3):
        codon = seq[i : i + 3]
        if "N" not in codon:
            counts[codon] += 1

    total = sum(counts.values())
    frequencies = {k: v / total for k, v in counts.items()} if total > 0 else {}

    return dict(counts), frequencies


def six_frame_translation(sequence: str) -> dict[str, str]:
    """Perform six-frame translation.

    Args:
        sequence: DNA sequence

    Returns:
        Dictionary with frame keys and protein sequences

    """
    sequence = sequence.upper()
    revcomp = reverse_complement(sequence)

    translations = {}

    for frame in range(3):
        translations[f"+{frame + 1}"] = translate(sequence, frame)
        translations[f"-{frame + 1}"] = translate(revcomp, frame)

    return translations


def calculate_molecular_weight(
    sequence: str,
    seq_type: str = "dna",
) -> float:
    """Calculate molecular weight of sequence.

    Args:
        sequence: Sequence string
        seq_type: 'dna', 'rna', or 'protein'

    Returns:
        Molecular weight in Daltons

    """
    sequence = sequence.upper()

    if seq_type == "dna":
        weights = {"A": 313.21, "T": 304.19, "G": 329.21, "C": 289.18}
        total = sum(weights.get(base, 0) for base in sequence)
        # Subtract water for phosphodiester bonds
        total -= (len(sequence) - 1) * 61.97
        return total

    elif seq_type == "rna":
        weights = {"A": 329.21, "U": 306.17, "G": 345.21, "C": 305.18}
        total = sum(weights.get(base, 0) for base in sequence)
        total -= (len(sequence) - 1) * 61.97
        return total

    elif seq_type == "protein":
        weights = {
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
        total = sum(weights.get(aa, 0) for aa in sequence)
        # Subtract water for peptide bonds
        total -= (len(sequence) - 1) * 18.015
        return total

    else:
        raise ValueError(f"Unknown sequence type: {seq_type}")


def find_repeats(
    sequence: str,
    min_length: int = 3,
    min_copies: int = 2,
) -> list[dict]:
    """Find tandem repeats in sequence.

    Args:
        sequence: DNA sequence
        min_length: Minimum repeat unit length
        min_copies: Minimum number of copies

    Returns:
        List of repeat dictionaries

    """
    sequence = sequence.upper()
    repeats = []

    for unit_len in range(min_length, len(sequence) // min_copies + 1):
        for start in range(len(sequence) - unit_len * min_copies + 1):
            unit = sequence[start : start + unit_len]

            # Count consecutive repeats
            copies = 1
            pos = start + unit_len

            while pos + unit_len <= len(sequence):
                if sequence[pos : pos + unit_len] == unit:
                    copies += 1
                    pos += unit_len
                else:
                    break

            if copies >= min_copies:
                repeats.append(
                    {
                        "start": start,
                        "end": start + unit_len * copies,
                        "unit": unit,
                        "unit_length": unit_len,
                        "copies": copies,
                    }
                )

    # Remove overlapping/redundant repeats
    repeats.sort(key=lambda x: (-x["copies"] * x["unit_length"], x["start"]))

    non_overlapping = []
    covered = set()

    for r in repeats:
        positions = set(range(r["start"], r["end"]))
        if not positions & covered:
            non_overlapping.append(r)
            covered.update(positions)

    return sorted(non_overlapping, key=lambda x: x["start"])


def find_palindromes(
    sequence: str,
    min_length: int = 4,
    max_length: int = 20,
    max_gap: int = 10,
) -> list[dict]:
    """Find palindromic sequences (potential restriction sites).

    Args:
        sequence: DNA sequence
        min_length: Minimum palindrome arm length
        max_length: Maximum palindrome arm length
        max_gap: Maximum gap between arms

    Returns:
        List of palindrome dictionaries

    """
    sequence = sequence.upper()
    palindromes = []

    for arm_len in range(min_length, max_length + 1):
        for gap in range(0, max_gap + 1, 2):  # Palindromes typically have even gaps
            for start in range(len(sequence) - 2 * arm_len - gap + 1):
                left_arm = sequence[start : start + arm_len]
                right_start = start + arm_len + gap
                right_arm = sequence[right_start : right_start + arm_len]

                # Check if right arm is reverse complement of left
                left_revcomp = reverse_complement(left_arm)

                if right_arm == left_revcomp:
                    palindromes.append(
                        {
                            "start": start,
                            "end": right_start + arm_len,
                            "left_arm": left_arm,
                            "right_arm": right_arm,
                            "arm_length": arm_len,
                            "gap": gap,
                            "sequence": sequence[start : right_start + arm_len],
                        }
                    )

    return palindromes


def calculate_cai(
    sequence: str,
    reference_table: dict[str, float],
) -> float:
    """Calculate Codon Adaptation Index (CAI).

    Args:
        sequence: Coding DNA sequence
        reference_table: Reference codon usage table (codon -> relative adaptiveness)

    Returns:
        CAI value (0-1)

    """
    sequence = sequence.upper()

    log_sum = 0.0
    codon_count = 0

    for i in range(0, len(sequence) - 2, 3):
        codon = sequence[i : i + 3]
        if codon in reference_table:
            w = reference_table[codon]
            if w > 0:
                log_sum += math.log(w)
                codon_count += 1

    if codon_count == 0:
        return 0.0

    return math.exp(log_sum / codon_count)


def sliding_window(
    sequence: str,
    window_size: int,
    step: int = 1,
    function: str = "gc",
) -> list[tuple[int, float]]:
    """Apply sliding window analysis.

    Args:
        sequence: Sequence string
        window_size: Window size
        step: Step size
        function: Analysis function ('gc', 'entropy', 'complexity')

    Returns:
        List of (position, value) tuples

    """
    sequence = sequence.upper()
    results = []

    for i in range(0, len(sequence) - window_size + 1, step):
        window = sequence[i : i + window_size]
        position = i + window_size // 2

        if function == "gc":
            value = gc_content(window)

        elif function == "entropy":
            # Shannon entropy
            freqs = Counter(window)
            total = len(window)
            value = -sum((c / total) * math.log2(c / total) for c in freqs.values() if c > 0)

        elif function == "complexity":
            # Linguistic complexity (unique k-mers / possible k-mers)
            k = 3
            kmers = {window[j : j + k] for j in range(len(window) - k + 1)}
            max_kmers = min(4**k, len(window) - k + 1)
            value = len(kmers) / max_kmers if max_kmers > 0 else 0

        else:
            raise ValueError(f"Unknown function: {function}")

        results.append((position, value))

    return results


def identify_promoter_elements(sequence: str) -> list[dict]:
    """Identify common promoter elements in DNA sequence.

    Args:
        sequence: DNA sequence

    Returns:
        List of identified elements

    """
    sequence = sequence.upper()
    elements = []

    # Common promoter motifs
    motifs = {
        "TATA_box": r"TATA[AT]A[AT]",
        "CAAT_box": r"GG[TC]CAATCT",
        "GC_box": r"GGGCGG",
        "initiator": r"[CT][CT]A[ACGT]T[CT][CT]",
        "BRE": r"[GC][GC][GA]CGCC",
        "DPE": r"[AG]G[AT][CT][GT]",
    }

    for name, pattern in motifs.items():
        for match in re.finditer(pattern, sequence):
            elements.append(
                {
                    "type": name,
                    "start": match.start(),
                    "end": match.end(),
                    "sequence": match.group(),
                }
            )

    return sorted(elements, key=lambda x: x["start"])


def calculate_gc_skew_cumulative(sequence: str) -> list[tuple[int, float]]:
    """Calculate cumulative GC skew for origin/terminus identification.

    Args:
        sequence: DNA sequence

    Returns:
        List of (position, cumulative_skew) tuples

    """
    sequence = sequence.upper()
    cumulative = []
    skew = 0.0

    for i, base in enumerate(sequence):
        if base == "G":
            skew += 1
        elif base == "C":
            skew -= 1
        cumulative.append((i, skew))

    return cumulative

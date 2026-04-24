"""Unit Tests for Sequence Classes.
===============================

Tests for DNASequence, RNASequence, ProteinSequence, and SequenceCollection.
"""

import pytest

from backend.bioinformatics.sequence import (
    DNASequence,
    ProteinSequence,
    RNASequence,
    SequenceCollection,
    SequenceQuality,
)


class TestDNASequence:
    """Tests for DNASequence class."""

    def test_creation(self, sample_dna_sequences):
        """Test basic DNA sequence creation."""
        seq = DNASequence(sample_dna_sequences["short"])
        assert str(seq) == sample_dna_sequences["short"].upper()
        assert len(seq) == len(sample_dna_sequences["short"])

    def test_gc_content(self, sample_dna_sequences):
        """Test GC content calculation."""
        gc_rich = DNASequence(sample_dna_sequences["gc_rich"])
        at_rich = DNASequence(sample_dna_sequences["at_rich"])

        assert gc_rich.gc_content() == 1.0
        assert at_rich.gc_content() == 0.0

        # Standard sequence should have intermediate GC
        standard = DNASequence(sample_dna_sequences["short"])
        gc = standard.gc_content()
        assert 0.0 < gc < 1.0

    def test_complement(self, sample_dna_sequences):
        """Test complement generation."""
        seq = DNASequence("ATGC")
        comp = seq.complement()
        assert str(comp) == "TACG"

    def test_reverse_complement(self, sample_dna_sequences):
        """Test reverse complement generation."""
        seq = DNASequence("ATGC")
        revcomp = seq.reverse_complement()
        assert str(revcomp) == "GCAT"

        # Double reverse complement should give original
        double_revcomp = revcomp.reverse_complement()
        assert str(double_revcomp) == str(seq)

    def test_transcription(self):
        """Test DNA to RNA transcription."""
        dna = DNASequence("ATGCGATCG")
        rna = dna.transcribe()

        assert isinstance(rna, RNASequence)
        assert str(rna) == "AUGCGAUCG"
        assert "T" not in str(rna)

    def test_translation(self):
        """Test DNA to protein translation."""
        # ATG = Met (M), AAA = Lys (K), GGG = Gly (G), CCC = Pro (P)
        dna = DNASequence("ATGAAAGGGCCC")
        protein = dna.translate()

        assert isinstance(protein, ProteinSequence)
        assert str(protein) == "MKGP"

    def test_translation_with_stop(self):
        """Test translation stops at stop codon."""
        dna = DNASequence("ATGAAATAGGGG")  # ATG AAA TAG GGG (TAG = stop)
        protein = dna.translate(to_stop=True)

        assert str(protein) == "MK"

    def test_translation_frames(self):
        """Test translation in different reading frames."""
        dna = DNASequence("AATGAAAGGGCCC")

        frame0 = dna.translate(frame=0)
        frame1 = dna.translate(frame=1)

        # Different frames should produce different proteins
        assert str(frame0) != str(frame1)
        # Frame 0 starts at position 0
        # Frame 1 starts at position 1 (ATG = M)

    def test_find_orfs(self):
        """Test ORF finding."""
        # Create sequence with a clear ORF
        # ATG (start) ... TAA (stop)
        dna = DNASequence("AAATGAAAGGGCCCTTTTAAGGGG" * 5)  # 120 bp
        orfs = dna.find_orfs(min_length=15)

        # Should find at least one ORF
        assert len(orfs) >= 1

        for orf in orfs:
            assert "start" in orf
            assert "end" in orf
            assert "strand" in orf
            assert orf["length"] >= 15

    def test_melting_temperature(self):
        """Test melting temperature calculation."""
        short_seq = DNASequence("ATGC")
        long_seq = DNASequence("ATGCGATCGATCGATCG")

        tm_short = short_seq.melting_temperature()
        tm_long = long_seq.melting_temperature()

        # Both should return positive temperatures
        assert tm_short > 0
        assert tm_long > 0

        # GC-rich sequence should have higher Tm
        gc_seq = DNASequence("GCGCGCGC")
        at_seq = DNASequence("ATATATAT")

        assert gc_seq.melting_temperature() > at_seq.melting_temperature()

    def test_find_restriction_sites(self):
        """Test restriction site finding."""
        # Create sequence with EcoRI site (GAATTC)
        dna = DNASequence("ATGCGAATTCGATCG")

        sites = dna.find_restriction_sites({"EcoRI": "GAATTC"})

        assert "EcoRI" in sites
        assert len(sites["EcoRI"]) == 1
        assert sites["EcoRI"][0] == 4

    def test_gc_skew(self):
        """Test GC skew calculation."""
        # Create sequence long enough for windowed analysis
        dna = DNASequence("GCGCGCGC" * 200 + "ATATAT" * 200)

        skews = dna.gc_skew(window=100, step=50)

        assert len(skews) > 0
        for _pos, skew in skews:
            assert -1.0 <= skew <= 1.0

    def test_cpg_islands(self):
        """Test CpG island detection."""
        # Create GC-rich sequence with CpG islands
        cpg_rich = "CG" * 150  # Very high CpG content
        flanking = "ATATAT" * 50
        dna = DNASequence(flanking + cpg_rich + flanking)

        islands = dna.cpg_islands(min_length=100, min_gc=0.5, min_obs_exp=0.6)

        # Should detect at least one island
        assert len(islands) >= 1

    def test_sequence_with_n(self, sample_dna_sequences):
        """Test handling of N bases."""
        seq = DNASequence(sample_dna_sequences["with_n"])

        # Should create successfully
        assert "N" in str(seq)

        # GC content should handle N
        gc = seq.gc_content()
        assert 0.0 <= gc <= 1.0

    def test_sequence_equality(self):
        """Test sequence equality comparison."""
        seq1 = DNASequence("ATGC")
        seq2 = DNASequence("ATGC")
        seq3 = DNASequence("GCTA")

        assert seq1 == seq2
        assert seq1 != seq3
        assert seq1 == "ATGC"

    def test_sequence_concatenation(self):
        """Test sequence concatenation."""
        seq1 = DNASequence("ATGC")
        seq2 = DNASequence("GCTA")

        combined = seq1 + seq2

        assert isinstance(combined, DNASequence)
        assert str(combined) == "ATGCGCTA"

    def test_sequence_slicing(self):
        """Test sequence slicing."""
        seq = DNASequence("ATGCGATCG")

        assert seq[0] == "A"
        assert seq[-1] == "G"
        assert seq[0:4] == "ATGC"
        # ATGCGATCG with step 2: positions 0,2,4,6,8 = A,G,G,T,G
        assert seq[::2] == "AGGTG"

    def test_subsequence(self):
        """Test subsequence extraction."""
        seq = DNASequence("ATGCGATCGATCG", id="test_seq")
        subseq = seq.subsequence(2, 8)

        assert isinstance(subseq, DNASequence)
        assert str(subseq) == "GCGATC"
        assert "test_seq" in subseq.id

    def test_pattern_finding(self):
        """Test pattern finding methods."""
        seq = DNASequence("ATGATGATGATG")

        # Count
        assert seq.count("ATG") == 4

        # Find first
        assert seq.find("ATG") == 0

        # Find all
        positions = seq.find_all("ATG")
        assert len(positions) == 4
        assert positions == [0, 3, 6, 9]

    def test_composition(self):
        """Test base composition."""
        seq = DNASequence("AATTGGCC")

        comp = seq.composition()

        assert comp["A"] == 2
        assert comp["T"] == 2
        assert comp["G"] == 2
        assert comp["C"] == 2

    def test_frequency(self):
        """Test base frequency calculation."""
        seq = DNASequence("AATTGGCC")

        freq = seq.frequency()

        assert freq["A"] == 0.25
        assert freq["T"] == 0.25
        assert sum(freq.values()) == pytest.approx(1.0)

    def test_to_fasta(self):
        """Test FASTA format output."""
        seq = DNASequence("ATGCGATCGATCG", id="test", description="Test sequence")

        fasta = seq.to_fasta()

        assert fasta.startswith(">test Test sequence")
        assert "ATGCGATCGATCG" in fasta

    def test_invalid_sequence_raises(self):
        """Test that invalid characters raise error."""
        with pytest.raises(ValueError):
            DNASequence("ATGCXYZ")


class TestRNASequence:
    """Tests for RNASequence class."""

    def test_creation(self, sample_rna_sequence):
        """Test RNA sequence creation."""
        rna = RNASequence(sample_rna_sequence)
        assert "U" in str(rna)
        assert "T" not in str(rna)

    def test_complement(self):
        """Test RNA complement."""
        rna = RNASequence("AUGC")
        comp = rna.complement()
        assert str(comp) == "UACG"

    def test_reverse_complement(self):
        """Test RNA reverse complement."""
        rna = RNASequence("AUGC")
        revcomp = rna.reverse_complement()
        assert str(revcomp) == "GCAU"

    def test_to_dna(self):
        """Test RNA to DNA conversion."""
        rna = RNASequence("AUGCGAUCG")
        dna = rna.to_dna()

        assert isinstance(dna, DNASequence)
        assert str(dna) == "ATGCGATCG"

    def test_translation(self):
        """Test RNA to protein translation."""
        rna = RNASequence("AUGAAAGGGCCC")
        protein = rna.translate()

        assert isinstance(protein, ProteinSequence)
        assert str(protein) == "MKGP"

    def test_gc_content(self):
        """Test GC content for RNA."""
        rna = RNASequence("GCGCGCGC")
        assert rna.gc_content() == 1.0

        rna_au = RNASequence("AUAUAUAU")
        assert rna_au.gc_content() == 0.0

    def test_secondary_structure_motifs(self):
        """Test secondary structure motif finding."""
        # Create sequence with potential stem-loop
        # GCGC....GCGC (inverted repeat)
        rna = RNASequence("AAAGCGCAAAAGCGCAAA" * 3)

        motifs = rna.find_secondary_structure_motifs()
        # This is a simplified finder, may not always find motifs
        assert isinstance(motifs, list)


class TestProteinSequence:
    """Tests for ProteinSequence class."""

    def test_creation(self, sample_protein_sequences):
        """Test protein sequence creation."""
        protein = ProteinSequence(sample_protein_sequences["short"])
        assert len(protein) == len(sample_protein_sequences["short"])

    def test_molecular_weight(self, sample_protein_sequences):
        """Test molecular weight calculation."""
        protein = ProteinSequence(sample_protein_sequences["short"])
        mw = protein.molecular_weight()

        assert mw > 0
        # Typical amino acid MW is ~110 Da
        expected_min = len(sample_protein_sequences["short"]) * 50
        expected_max = len(sample_protein_sequences["short"]) * 200
        assert expected_min < mw < expected_max

    def test_isoelectric_point(self, sample_protein_sequences):
        """Test isoelectric point calculation."""
        protein = ProteinSequence(sample_protein_sequences["short"])
        pi = protein.isoelectric_point()

        assert 0.0 < pi < 14.0

        # Basic protein (lots of K, R) should have high pI
        basic = ProteinSequence("KRKRKRKRKR")
        acidic = ProteinSequence("DEDEDEDEDE")

        assert basic.isoelectric_point() > acidic.isoelectric_point()

    def test_hydrophobicity_profile(self, sample_protein_sequences):
        """Test hydrophobicity profile calculation."""
        protein = ProteinSequence(sample_protein_sequences["medium"])
        profile = protein.hydrophobicity_profile(window=5)

        assert len(profile) > 0

        for _pos, hydro in profile:
            # Kyte-Doolittle values range roughly from -4.5 to 4.5
            assert -5.0 < hydro < 5.0

    def test_find_domains(self, sample_protein_sequences):
        """Test domain finding."""
        # Use sequence with signal peptide-like region
        protein = ProteinSequence(sample_protein_sequences["with_signal"])
        domains = protein.find_domains()

        # May or may not find domains depending on patterns
        assert isinstance(domains, list)

    def test_secondary_structure_propensity(self, sample_protein_sequences):
        """Test secondary structure propensity calculation."""
        protein = ProteinSequence(sample_protein_sequences["medium"])
        propensity = protein.secondary_structure_propensity()

        assert "helix_propensity" in propensity
        assert "sheet_propensity" in propensity
        assert "coil_propensity" in propensity

        # All should be positive
        assert all(v > 0 for v in propensity.values())

    def test_aromaticity(self, sample_protein_sequences):
        """Test aromaticity calculation."""
        protein = ProteinSequence(sample_protein_sequences["medium"])
        arom = protein.aromaticity()

        assert 0.0 <= arom <= 1.0

        # Aromatic-rich sequence
        aromatic = ProteinSequence("FWYFWYFWY")
        assert aromatic.aromaticity() == 1.0

    def test_instability_index(self, sample_protein_sequences):
        """Test instability index calculation."""
        protein = ProteinSequence(sample_protein_sequences["medium"])
        ii = protein.instability_index()

        # Should return a numeric value
        assert isinstance(ii, float)


class TestSequenceCollection:
    """Tests for SequenceCollection class."""

    def test_creation(self, sample_dna_sequences):
        """Test collection creation."""
        seqs = [DNASequence(s) for s in sample_dna_sequences.values() if "N" not in s]
        collection = SequenceCollection(seqs, name="test_collection")

        assert len(collection) == len(seqs)
        assert collection.name == "test_collection"

    def test_iteration(self, sample_dna_sequences):
        """Test collection iteration."""
        seqs = [DNASequence(s) for s in list(sample_dna_sequences.values())[:3]]
        collection = SequenceCollection(seqs)

        count = 0
        for seq in collection:
            assert isinstance(seq, DNASequence)
            count += 1

        assert count == 3

    def test_indexing(self, sample_dna_sequences):
        """Test collection indexing."""
        seqs = [
            DNASequence(s, id=f"seq_{i}")
            for i, s in enumerate(list(sample_dna_sequences.values())[:3])
        ]
        collection = SequenceCollection(seqs)

        # Numeric indexing
        assert collection[0] == seqs[0]

        # ID-based indexing
        assert collection["seq_0"] == seqs[0]

    def test_add_remove(self, sample_dna_sequences):
        """Test adding and removing sequences."""
        collection = SequenceCollection()
        seq = DNASequence(sample_dna_sequences["short"], id="test_seq")

        collection.add(seq)
        assert len(collection) == 1

        collection.remove("test_seq")
        assert len(collection) == 0

    def test_filter_by_length(self, sample_dna_sequences):
        """Test filtering by length."""
        seqs = [DNASequence(s) for s in sample_dna_sequences.values() if "N" not in s]
        collection = SequenceCollection(seqs)

        filtered = collection.filter_by_length(min_length=20)

        assert all(len(s) >= 20 for s in filtered)

    def test_filter_by_gc(self, sample_dna_sequences):
        """Test filtering by GC content."""
        seqs = [DNASequence(s) for s in sample_dna_sequences.values() if "N" not in s]
        collection = SequenceCollection(seqs)

        filtered = collection.filter_by_gc(min_gc=0.4, max_gc=0.6)

        for seq in filtered:
            gc = seq.gc_content()
            assert 0.4 <= gc <= 0.6

    def test_statistics(self, sample_dna_sequences):
        """Test collection statistics."""
        seqs = [DNASequence(s) for s in sample_dna_sequences.values() if "N" not in s]
        collection = SequenceCollection(seqs)

        stats = collection.statistics()

        assert "count" in stats
        assert "total_length" in stats
        assert "mean_length" in stats
        assert "n50" in stats
        assert stats["count"] == len(seqs)

    def test_consensus(self, aligned_sequences):
        """Test consensus sequence generation."""
        seqs = [DNASequence(s) for s in aligned_sequences]
        collection = SequenceCollection(seqs)

        consensus = collection.consensus()

        assert consensus is not None
        assert len(consensus) == len(aligned_sequences[0])

    def test_to_fasta(self, sample_dna_sequences):
        """Test FASTA export."""
        seqs = [
            DNASequence(s, id=f"seq_{i}")
            for i, s in enumerate(list(sample_dna_sequences.values())[:3])
        ]
        collection = SequenceCollection(seqs)

        fasta = collection.to_fasta()

        assert ">seq_0" in fasta
        assert ">seq_1" in fasta
        assert ">seq_2" in fasta


class TestSequenceQuality:
    """Tests for SequenceQuality class."""

    def test_creation(self):
        """Test quality score creation."""
        scores = [30, 35, 40, 38, 25, 20, 30]
        quality = SequenceQuality(scores)

        assert quality.scores == scores

    def test_mean_quality(self):
        """Test mean quality calculation."""
        scores = [30, 30, 30, 30]
        quality = SequenceQuality(scores)

        assert quality.mean_quality == 30.0

    def test_min_quality(self):
        """Test minimum quality."""
        scores = [30, 20, 40, 35]
        quality = SequenceQuality(scores)

        assert quality.min_quality == 20

    def test_trim_by_quality(self):
        """Test quality-based trimming positions."""
        scores = [10, 15, 30, 35, 40, 38, 15, 10]
        quality = SequenceQuality(scores)

        start, end = quality.trim_by_quality(min_qual=20)

        # Should trim low quality ends
        assert start == 2
        assert end == 6

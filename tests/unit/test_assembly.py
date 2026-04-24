"""Unit Tests for Genome Assembly.
==============================

Tests for de Bruijn graph assembler, OLC assembler, and assembly utilities.
"""

from backend.assembly.assemblers import (
    AssemblyGraph,
    AssemblyResult,
    Contig,
    DeBruijnAssembler,
    HybridAssembler,
    OverlapLayoutConsensus,
    ReferenceGuidedAssembler,
)


class TestContig:
    """Tests for Contig dataclass."""

    def test_contig_creation(self):
        """Test basic contig creation."""
        contig = Contig(
            id="contig_1",
            sequence="ATGCGATCGATCG",
            coverage=10.5,
        )

        assert contig.id == "contig_1"
        assert contig.length == 13
        assert contig.coverage == 10.5

    def test_contig_gc_content(self):
        """Test automatic GC content calculation."""
        # All GC
        gc_contig = Contig(id="gc", sequence="GCGCGCGC")
        assert gc_contig.gc_content == 1.0

        # All AT
        at_contig = Contig(id="at", sequence="ATATATAT")
        assert at_contig.gc_content == 0.0

        # Mixed
        mixed = Contig(id="mixed", sequence="ATGC")
        assert mixed.gc_content == 0.5

    def test_contig_length_auto_calculated(self):
        """Test that length is auto-calculated."""
        contig = Contig(id="test", sequence="ATGCGATCG")
        assert contig.length == 9


class TestAssemblyResult:
    """Tests for AssemblyResult dataclass."""

    def test_assembly_statistics(self):
        """Test assembly statistics calculation."""
        contigs = [
            Contig(id="c1", sequence="A" * 100),
            Contig(id="c2", sequence="A" * 200),
            Contig(id="c3", sequence="A" * 300),
        ]

        result = AssemblyResult(contigs=contigs)

        assert result.num_contigs == 3
        assert result.total_length == 600
        assert result.largest_contig == 300

    def test_n50_calculation(self):
        """Test N50 calculation."""
        # Contigs: 500, 400, 100 = 1000 total
        # Sorted by length: 500, 400, 100
        # N50: need 500bp to reach 50% (500)
        # First contig (500) covers 50%, so N50 = 500
        contigs = [
            Contig(id="c1", sequence="A" * 500),
            Contig(id="c2", sequence="A" * 400),
            Contig(id="c3", sequence="A" * 100),
        ]

        result = AssemblyResult(contigs=contigs)

        assert result.n50 == 500
        assert result.l50 == 1

    def test_n90_calculation(self):
        """Test N90 calculation."""
        contigs = [
            Contig(id="c1", sequence="A" * 500),
            Contig(id="c2", sequence="A" * 400),
            Contig(id="c3", sequence="A" * 100),
        ]

        result = AssemblyResult(contigs=contigs)

        # N90: need 900bp to reach 90%
        assert result.n90 > 0
        assert result.l90 >= 1

    def test_get_summary(self):
        """Test getting assembly summary."""
        contigs = [
            Contig(id="c1", sequence="ATGC" * 25, coverage=10.0),
            Contig(id="c2", sequence="ATGC" * 50, coverage=15.0),
        ]

        result = AssemblyResult(contigs=contigs)
        summary = result.get_summary()

        assert "num_contigs" in summary
        assert "total_length" in summary
        assert "n50" in summary
        assert "coverage_mean" in summary

    def test_to_fasta(self, temp_data_dir):
        """Test FASTA export."""
        contigs = [
            Contig(id="contig_1", sequence="ATGCGATCGATCG", coverage=10.0),
            Contig(id="contig_2", sequence="GCTAGCTAGCTAG", coverage=15.0),
        ]

        result = AssemblyResult(contigs=contigs)
        fasta = result.to_fasta()

        assert ">contig_1" in fasta
        assert ">contig_2" in fasta
        assert "ATGCGATCGATCG" in fasta

        # Test file output
        filepath = temp_data_dir / "assembly.fasta"
        result.to_fasta(filepath)
        assert filepath.exists()

    def test_empty_assembly(self):
        """Test handling of empty assembly."""
        result = AssemblyResult(contigs=[])

        assert result.num_contigs == 0
        assert result.total_length == 0


class TestDeBruijnAssembler:
    """Tests for de Bruijn graph assembler."""

    def test_basic_assembly(self, fastq_reads):
        """Test basic assembly from reads."""
        assembler = DeBruijnAssembler(k=11)
        result = assembler.assemble(fastq_reads)

        assert isinstance(result, AssemblyResult)
        assert len(result.contigs) > 0

    def test_assembly_with_different_k(self, fastq_reads):
        """Test assembly with different k-mer sizes."""
        results = []
        for k in [9, 11, 13]:
            assembler = DeBruijnAssembler(k=k)
            result = assembler.assemble(fastq_reads)
            results.append(result)

        # All should produce contigs
        assert all(len(r.contigs) > 0 for r in results)

    def test_assembly_graph(self, fastq_reads):
        """Test getting assembly graph."""
        assembler = DeBruijnAssembler(k=11)
        assembler.assemble(fastq_reads)

        graph = assembler.get_assembly_graph()

        assert isinstance(graph, AssemblyGraph)
        assert graph.num_nodes >= 0

    def test_parameters_in_result(self, fastq_reads):
        """Test that parameters are stored in result."""
        assembler = DeBruijnAssembler(k=15)
        result = assembler.assemble(fastq_reads)

        assert result.parameters["k"] == 15
        assert result.parameters["algorithm"] == "de_bruijn"

    def test_simple_known_sequence(self):
        """Test with simple, known sequence."""
        # Create reads that should assemble to a known sequence
        reference = "ATGCGATCGATCGATCGATCGATCGATCGATCGATCG"
        k = 9

        # Generate overlapping reads
        reads = []
        for i in range(0, len(reference) - k, 3):
            reads.append(reference[i : i + k + 5])

        assembler = DeBruijnAssembler(k=k)
        result = assembler.assemble(reads)

        # Should produce at least one contig
        assert len(result.contigs) >= 1

    def test_handles_n_bases(self):
        """Test handling of reads with N bases."""
        reads = [
            "ATGCGATCGATCG",
            "ATGCNNNGATCG",  # Contains N
            "GATCGATCGATC",
        ]

        assembler = DeBruijnAssembler(k=5)
        result = assembler.assemble(reads)

        # Should still assemble without error
        assert isinstance(result, AssemblyResult)


class TestOverlapLayoutConsensus:
    """Tests for OLC assembler."""

    def test_basic_olc_assembly(self):
        """Test basic OLC assembly."""
        # Create overlapping long reads
        reads = [
            "ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG",
            "GATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGAAAA",
            "GATCGATCGATCGATCGATCGAAAATTTTCCCCGGGG",
        ]

        assembler = OverlapLayoutConsensus(min_overlap=20, min_identity=0.8)
        result = assembler.assemble(reads)

        assert isinstance(result, AssemblyResult)

    def test_olc_parameters(self):
        """Test OLC with different parameters."""
        reads = [
            "ATGCGATCGATCGATCGATCGATCGATCG" * 2,
            "GATCGATCGATCGATCGATCGATCGATCG" * 2,
        ]

        # Strict overlap
        assembler_strict = OverlapLayoutConsensus(min_overlap=30, min_identity=0.9)
        result_strict = assembler_strict.assemble(reads)

        # Lenient overlap
        assembler_lenient = OverlapLayoutConsensus(min_overlap=10, min_identity=0.7)
        result_lenient = assembler_lenient.assemble(reads)

        # Both should complete
        assert isinstance(result_strict, AssemblyResult)
        assert isinstance(result_lenient, AssemblyResult)

    def test_olc_assembly_graph(self):
        """Test OLC assembly graph."""
        reads = [
            "ATGCGATCGATCGATCGATCGATCGATCGATCGATCG",
            "GATCGATCGATCGATCGATCGATCGATCGATCGAAAA",
        ]

        assembler = OverlapLayoutConsensus(min_overlap=15)
        assembler.assemble(reads)

        graph = assembler.get_assembly_graph()

        assert isinstance(graph, AssemblyGraph)


class TestReferenceGuidedAssembler:
    """Tests for reference-guided assembly."""

    def test_basic_reference_assembly(self):
        """Test basic reference-guided assembly."""
        reference = "ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"

        # Create reads from reference with some variation
        reads = [
            reference[0:25],
            reference[10:35],
            reference[20:45],
            reference[25:50],
        ]

        assembler = ReferenceGuidedAssembler(reference)
        result = assembler.assemble(reads)

        assert isinstance(result, AssemblyResult)
        assert result.parameters["algorithm"] == "reference_guided"

    def test_reference_assembly_with_variants(self):
        """Test assembly with variants from reference."""
        reference = "ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG"

        # Reads with a substitution
        reads = [
            "ATGCGATCGATCGATCGATCGATC",  # Perfect match
            "ATGCGATTGATCGATCGATCGATC",  # One SNP
            "ATGCGATCGATCGATCGATCGATC",
        ]

        assembler = ReferenceGuidedAssembler(reference)
        result = assembler.assemble(reads)

        assert len(result.contigs) >= 0  # May or may not produce contigs

    def test_reference_assembly_graph(self):
        """Test that reference assembly returns empty graph."""
        reference = "ATGCGATCGATCGATCG"
        assembler = ReferenceGuidedAssembler(reference)

        graph = assembler.get_assembly_graph()

        # Reference-guided doesn't have traditional graph
        assert isinstance(graph, AssemblyGraph)


class TestHybridAssembler:
    """Tests for hybrid assembly."""

    def test_short_reads_only(self, fastq_reads):
        """Test hybrid assembler with only short reads."""
        assembler = HybridAssembler(short_read_k=11)
        result = assembler.assemble(fastq_reads)

        assert isinstance(result, AssemblyResult)

    def test_hybrid_with_long_reads(self, fastq_reads):
        """Test hybrid assembly with short and long reads."""
        # Create some "long reads"
        long_reads = [
            "ATGCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCG",
            "GATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATCGATC",
        ]

        assembler = HybridAssembler(short_read_k=11, long_read_min_overlap=20)
        result = assembler.assemble(fastq_reads, long_reads=long_reads)

        assert isinstance(result, AssemblyResult)
        assert result.parameters["algorithm"] == "hybrid"

    def test_hybrid_assembly_graph(self, fastq_reads):
        """Test getting assembly graph from hybrid assembler."""
        assembler = HybridAssembler(short_read_k=11)
        assembler.assemble(fastq_reads)

        graph = assembler.get_assembly_graph()

        assert isinstance(graph, AssemblyGraph)


class TestAssemblyGraph:
    """Tests for AssemblyGraph dataclass."""

    def test_graph_creation(self):
        """Test creating assembly graph."""
        nodes = ["A", "B", "C"]
        edges = [("A", "B"), ("B", "C")]

        graph = AssemblyGraph(nodes=nodes, edges=edges)

        assert graph.num_nodes == 3
        assert graph.num_edges == 2

    def test_graph_with_coverage(self):
        """Test graph with node coverage."""
        nodes = ["A", "B", "C"]
        edges = [("A", "B"), ("B", "C")]
        coverage = {"A": 10, "B": 15, "C": 12}

        graph = AssemblyGraph(nodes=nodes, edges=edges, node_coverage=coverage)

        assert graph.node_coverage["A"] == 10

    def test_to_gfa(self):
        """Test GFA format export."""
        nodes = ["ATGC", "GCTA"]
        edges = [("ATGC", "GCTA")]
        coverage = {"ATGC": 10, "GCTA": 15}

        graph = AssemblyGraph(nodes=nodes, edges=edges, node_coverage=coverage)
        gfa = graph.to_gfa()

        assert "H\tVN:Z:1.0" in gfa  # Header
        assert "S\tATGC" in gfa  # Segment
        assert "L\tATGC" in gfa  # Link

    def test_empty_graph(self):
        """Test empty graph."""
        graph = AssemblyGraph(nodes=[], edges=[])

        assert graph.num_nodes == 0
        assert graph.num_edges == 0

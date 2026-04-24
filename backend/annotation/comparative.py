"""Comparative Genomics Module.
===========================

Comparative analysis including synteny, ortholog finding, and gene clustering.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Ortholog:
    """Ortholog relationship between genes."""

    gene1: str
    genome1: str
    gene2: str
    genome2: str
    identity: float
    alignment_length: int
    evalue: float
    score: float
    ortholog_type: str = "1:1"  # 1:1, 1:many, many:many


@dataclass
class OrthologGroup:
    """Group of orthologous genes."""

    group_id: str
    genes: list[tuple[str, str]]  # (genome_id, gene_id)
    core: bool = False  # Present in all genomes
    soft_core: bool = False  # Present in >95% of genomes
    accessory: bool = False  # Present in 15-95% of genomes
    unique: bool = False  # Present in <15% of genomes


@dataclass
class SyntenyBlock:
    """Syntenic block between genomes."""

    block_id: str
    genome1: str
    genome2: str
    start1: int
    end1: int
    start2: int
    end2: int
    orientation: str  # '+' or '-' (relative orientation)
    num_genes: int
    genes1: list[str]
    genes2: list[str]
    score: float = 0.0


@dataclass
class GeneCluster:
    """Gene cluster (e.g., biosynthetic gene cluster)."""

    cluster_id: str
    genome: str
    contig: str
    start: int
    end: int
    cluster_type: str  # e.g., 'NRPS', 'PKS', 'terpene'
    genes: list[str]
    core_genes: list[str]
    additional_genes: list[str]
    predicted_product: str = ""
    similarity_clusters: list[str] = field(default_factory=list)


class OrthologFinder:
    """Find orthologs between genomes."""

    def __init__(
        self,
        identity_threshold: float = 30.0,
        evalue_threshold: float = 1e-5,
        coverage_threshold: float = 50.0,
    ):
        self.identity_threshold = identity_threshold
        self.evalue_threshold = evalue_threshold
        self.coverage_threshold = coverage_threshold

    def find_orthologs(
        self,
        genome_proteins: dict[str, dict[str, str]],  # genome_id -> {gene_id: sequence}
    ) -> list[Ortholog]:
        """Find orthologs using reciprocal best hits."""
        logger.info(f"Finding orthologs in {len(genome_proteins)} genomes")

        orthologs = []
        genome_ids = list(genome_proteins.keys())

        # All-vs-all comparison
        for i, genome1 in enumerate(genome_ids):
            for genome2 in genome_ids[i + 1 :]:
                # Find best hits genome1 -> genome2
                hits_1to2 = self._find_best_hits(
                    genome_proteins[genome1],
                    genome_proteins[genome2],
                )

                # Find best hits genome2 -> genome1
                hits_2to1 = self._find_best_hits(
                    genome_proteins[genome2],
                    genome_proteins[genome1],
                )

                # Find reciprocal best hits
                for gene1, (gene2, score1) in hits_1to2.items():
                    if gene2 in hits_2to1 and hits_2to1[gene2][0] == gene1:
                        orthologs.append(
                            Ortholog(
                                gene1=gene1,
                                genome1=genome1,
                                gene2=gene2,
                                genome2=genome2,
                                identity=score1["identity"],
                                alignment_length=score1["alignment_length"],
                                evalue=score1["evalue"],
                                score=score1["score"],
                                ortholog_type="1:1",
                            )
                        )

        return orthologs

    def _find_best_hits(
        self,
        queries: dict[str, str],
        subjects: dict[str, str],
    ) -> dict[str, tuple[str, dict]]:
        """Find best hit for each query."""
        best_hits = {}

        for query_id, query_seq in queries.items():
            best_subject = None
            best_score = 0
            best_info = {}

            for subject_id, subject_seq in subjects.items():
                # Calculate similarity (simplified - would use BLAST in practice)
                score_info = self._calculate_similarity(query_seq, subject_seq)

                if score_info["identity"] >= self.identity_threshold:
                    if score_info["score"] > best_score:
                        best_score = score_info["score"]
                        best_subject = subject_id
                        best_info = score_info

            if best_subject:
                best_hits[query_id] = (best_subject, best_info)

        return best_hits

    def _calculate_similarity(self, seq1: str, seq2: str) -> dict:
        """Pairwise similarity via global alignment (Needleman–Wunsch) with a crude E-value proxy."""
        from backend.bioinformatics.algorithms import GlobalAligner, ScoringMatrix

        a = (seq1 or "").upper().replace(" ", "").replace("*", "")
        b = (seq2 or "").upper().replace(" ", "").replace("*", "")
        max_len = max(len(a), len(b), 1)
        min_len = min(len(a), len(b))

        # Keep alignment tractable for all-vs-all orthology screens
        cap = 600
        a_sub, b_sub = a[:cap], b[:cap]

        alphabet = set(a_sub + b_sub)
        dna_like = alphabet <= set("ATGCUN") and len(alphabet) <= 6
        matrix_type = "dna" if dna_like else "simple"
        aligner = GlobalAligner(scoring_matrix=ScoringMatrix(matrix_type))
        aln = aligner.align(a_sub, b_sub)

        identity_pct = float(aln.identity * 100.0)
        m, n = len(a), len(b)
        # Heuristic Karlin–Altschul–style tail (not BLAST-calibrated)
        lam, k_const = (0.28, 0.10) if dna_like else (0.22, 0.08)
        raw_score = max(float(aln.score), 1e-6)
        evalue = min(1.0, max(1e-120, k_const * m * n * np.exp(-lam * raw_score)))

        return {
            "identity": identity_pct,
            "alignment_length": int(aln.alignment_length),
            "evalue": float(evalue),
            "score": float(aln.score),
            "coverage": 100.0 * min_len / max_len,
        }

    def cluster_orthologs(
        self,
        orthologs: list[Ortholog],
        genome_ids: list[str],
    ) -> list[OrthologGroup]:
        """Cluster orthologs into ortholog groups."""
        # Build graph of ortholog relationships
        gene_to_orthologs = defaultdict(set)

        for orth in orthologs:
            key1 = (orth.genome1, orth.gene1)
            key2 = (orth.genome2, orth.gene2)
            gene_to_orthologs[key1].add(key2)
            gene_to_orthologs[key2].add(key1)

        # Find connected components
        visited = set()
        groups = []
        group_id = 0

        for gene_key in gene_to_orthologs:
            if gene_key in visited:
                continue

            # BFS to find component
            component = set()
            queue = [gene_key]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue

                visited.add(current)
                component.add(current)

                for neighbor in gene_to_orthologs.get(current, []):
                    if neighbor not in visited:
                        queue.append(neighbor)

            if component:
                # Determine ortholog group type
                genomes_in_group = {g[0] for g in component}
                num_genomes = len(genome_ids)
                coverage = len(genomes_in_group) / num_genomes

                group = OrthologGroup(
                    group_id=f"OG_{group_id:05d}",
                    genes=list(component),
                    core=(coverage == 1.0),
                    soft_core=(coverage >= 0.95),
                    accessory=(0.15 <= coverage < 0.95),
                    unique=(coverage < 0.15),
                )
                groups.append(group)
                group_id += 1

        return groups


class SyntenyAnalyzer:
    """Analyze synteny between genomes."""

    def __init__(
        self,
        min_genes: int = 3,
        max_gap: int = 5,
    ):
        self.min_genes = min_genes
        self.max_gap = max_gap

    def find_synteny(
        self,
        orthologs: list[Ortholog],
        gene_positions: dict[
            str, dict[str, tuple[str, int, int, str]]
        ],  # genome -> gene -> (contig, start, end, strand)
    ) -> list[SyntenyBlock]:
        """Find syntenic blocks between genomes."""
        logger.info("Finding syntenic blocks")

        synteny_blocks = []

        # Group orthologs by genome pair
        genome_pairs = defaultdict(list)
        for orth in orthologs:
            genome_pairs[(orth.genome1, orth.genome2)].append(orth)

        for (genome1, genome2), pair_orthologs in genome_pairs.items():
            blocks = self._find_blocks_between_genomes(
                pair_orthologs,
                gene_positions.get(genome1, {}),
                gene_positions.get(genome2, {}),
                genome1,
                genome2,
            )
            synteny_blocks.extend(blocks)

        return synteny_blocks

    def _find_blocks_between_genomes(
        self,
        orthologs: list[Ortholog],
        positions1: dict,
        positions2: dict,
        genome1: str,
        genome2: str,
    ) -> list[SyntenyBlock]:
        """Find syntenic blocks between two genomes."""
        blocks = []

        # Sort orthologs by position in genome1
        sorted_orthologs = []
        for orth in orthologs:
            if orth.gene1 in positions1 and orth.gene2 in positions2:
                pos1 = positions1[orth.gene1]
                pos2 = positions2[orth.gene2]
                sorted_orthologs.append((pos1[1], pos2[1], orth, pos1, pos2))

        sorted_orthologs.sort()

        if not sorted_orthologs:
            return blocks

        # Find collinear runs
        current_block = [sorted_orthologs[0]]

        for i in range(1, len(sorted_orthologs)):
            curr = sorted_orthologs[i]
            prev = current_block[-1]

            # Check if collinear
            pos1_diff = curr[0] - prev[0]
            pos2_diff = curr[1] - prev[1]

            # Same direction (both positive or both negative)
            same_direction = (pos1_diff > 0) == (pos2_diff > 0 if pos2_diff != 0 else True)

            # Not too far apart
            close_enough = abs(pos1_diff) < 100000 and abs(pos2_diff) < 100000

            if same_direction and close_enough:
                current_block.append(curr)
            else:
                # Save current block if large enough
                if len(current_block) >= self.min_genes:
                    blocks.append(self._create_block(current_block, genome1, genome2, len(blocks)))
                current_block = [curr]

        # Don't forget last block
        if len(current_block) >= self.min_genes:
            blocks.append(self._create_block(current_block, genome1, genome2, len(blocks)))

        return blocks

    def _create_block(
        self,
        ortholog_info: list,
        genome1: str,
        genome2: str,
        block_idx: int,
    ) -> SyntenyBlock:
        """Create SyntenyBlock from ortholog information."""
        genes1 = [info[2].gene1 for info in ortholog_info]
        genes2 = [info[2].gene2 for info in ortholog_info]

        start1 = min(info[3][1] for info in ortholog_info)
        end1 = max(info[3][2] for info in ortholog_info)
        start2 = min(info[4][1] for info in ortholog_info)
        end2 = max(info[4][2] for info in ortholog_info)

        # Determine orientation
        first_pos2 = ortholog_info[0][1]
        last_pos2 = ortholog_info[-1][1]
        orientation = "+" if last_pos2 > first_pos2 else "-"

        return SyntenyBlock(
            block_id=f"SYN_{genome1}_{genome2}_{block_idx}",
            genome1=genome1,
            genome2=genome2,
            start1=start1,
            end1=end1,
            start2=start2,
            end2=end2,
            orientation=orientation,
            num_genes=len(genes1),
            genes1=genes1,
            genes2=genes2,
            score=len(genes1) * 100,
        )

    def dot_plot(
        self,
        orthologs: list[Ortholog],
        gene_positions: dict,
        genome1: str,
        genome2: str,
    ) -> dict:
        """Generate dot plot data for visualization."""
        points = []

        positions1 = gene_positions.get(genome1, {})
        positions2 = gene_positions.get(genome2, {})

        for orth in orthologs:
            if orth.genome1 == genome1 and orth.genome2 == genome2:
                if orth.gene1 in positions1 and orth.gene2 in positions2:
                    pos1 = positions1[orth.gene1]
                    pos2 = positions2[orth.gene2]
                    points.append(
                        {
                            "x": (pos1[1] + pos1[2]) / 2,
                            "y": (pos2[1] + pos2[2]) / 2,
                            "gene1": orth.gene1,
                            "gene2": orth.gene2,
                        }
                    )

        return {
            "genome1": genome1,
            "genome2": genome2,
            "points": points,
        }


class GeneClusterFinder:
    """Find gene clusters (e.g., biosynthetic gene clusters)."""

    # Signature domains for different cluster types
    SIGNATURE_DOMAINS = {
        "NRPS": ["AMP-binding", "Condensation", "PP-binding"],
        "PKS": ["ketoacyl-synt", "Acyl_transf_1", "PP-binding"],
        "terpene": ["Terpene_synth", "Terpene_synth_C"],
        "RiPP": ["TIGR03793", "PF00881"],
        "siderophore": ["IucA_IucC"],
        "bacteriocin": ["Bacteriocin_IIa", "Bacteriocin_IIc"],
    }

    def __init__(
        self,
        min_genes: int = 5,
        max_intergenic: int = 10000,
    ):
        self.min_genes = min_genes
        self.max_intergenic = max_intergenic

    def find_clusters(
        self,
        genes: list["GenePrediction"],
        domain_annotations: dict[str, list[str]],  # gene_id -> domains
        contig_id: str = "contig",
        genome_id: str = "genome",
    ) -> list[GeneCluster]:
        """Find biosynthetic gene clusters."""
        clusters = []

        # Sort genes by position
        sorted_genes = sorted(genes, key=lambda g: g.start)

        for cluster_type, signature_domains in self.SIGNATURE_DOMAINS.items():
            # Find genes with signature domains
            signature_genes = []

            for gene in sorted_genes:
                gene_domains = domain_annotations.get(gene.id, [])

                if any(sig in " ".join(gene_domains) for sig in signature_domains):
                    signature_genes.append(gene)

            # Cluster nearby signature genes
            cluster_groups = self._cluster_nearby_genes(signature_genes)

            for group in cluster_groups:
                # Extend cluster to include neighboring genes
                extended = self._extend_cluster(group, sorted_genes)

                if len(extended) >= self.min_genes:
                    core_genes = [g.id for g in group]
                    additional_genes = [g.id for g in extended if g not in group]

                    clusters.append(
                        GeneCluster(
                            cluster_id=f"{genome_id}_{contig_id}_cluster_{len(clusters)}",
                            genome=genome_id,
                            contig=contig_id,
                            start=min(g.start for g in extended),
                            end=max(g.end for g in extended),
                            cluster_type=cluster_type,
                            genes=[g.id for g in extended],
                            core_genes=core_genes,
                            additional_genes=additional_genes,
                        )
                    )

        return clusters

    def _cluster_nearby_genes(
        self,
        genes: list["GenePrediction"],
    ) -> list[list["GenePrediction"]]:
        """Cluster genes that are near each other."""
        if not genes:
            return []

        clusters = []
        current_cluster = [genes[0]]

        for i in range(1, len(genes)):
            gap = genes[i].start - genes[i - 1].end

            if gap <= self.max_intergenic:
                current_cluster.append(genes[i])
            else:
                if current_cluster:
                    clusters.append(current_cluster)
                current_cluster = [genes[i]]

        if current_cluster:
            clusters.append(current_cluster)

        return clusters

    def _extend_cluster(
        self,
        core_genes: list["GenePrediction"],
        all_genes: list["GenePrediction"],
    ) -> list["GenePrediction"]:
        """Extend cluster to include neighboring genes."""
        if not core_genes:
            return []

        min(g.start for g in core_genes)
        max(g.end for g in core_genes)

        # Add 5 genes on each side
        extended = list(core_genes)

        # Find position of first core gene
        for i, gene in enumerate(all_genes):
            if gene in core_genes:
                # Add upstream genes
                for j in range(max(0, i - 5), i):
                    if all_genes[j] not in extended:
                        extended.append(all_genes[j])
                break

        # Find position of last core gene
        for i in range(len(all_genes) - 1, -1, -1):
            if all_genes[i] in core_genes:
                # Add downstream genes
                for j in range(i + 1, min(len(all_genes), i + 6)):
                    if all_genes[j] not in extended:
                        extended.append(all_genes[j])
                break

        return sorted(extended, key=lambda g: g.start)

    def compare_clusters(
        self,
        cluster1: GeneCluster,
        cluster2: GeneCluster,
        gene_similarity: dict[tuple[str, str], float],
    ) -> float:
        """Compare two gene clusters for similarity."""
        genes1 = set(cluster1.genes)
        genes2 = set(cluster2.genes)

        # Find matching genes
        matched = 0
        for g1 in genes1:
            for g2 in genes2:
                sim = gene_similarity.get((g1, g2), 0) or gene_similarity.get((g2, g1), 0)
                if sim > 0.5:
                    matched += 1
                    break

        # Jaccard-like similarity
        union_size = len(genes1) + len(genes2) - matched
        similarity = matched / union_size if union_size > 0 else 0

        return similarity

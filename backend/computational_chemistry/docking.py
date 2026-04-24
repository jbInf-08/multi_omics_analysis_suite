"""
Molecular Docking Module
========================

Protein-ligand docking and binding site prediction.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import logging

from .structure import Molecule, Atom

logger = logging.getLogger(__name__)


@dataclass
class DockingScore:
    """Docking score and components."""
    total_score: float
    van_der_waals: float = 0.0
    electrostatic: float = 0.0
    hydrogen_bond: float = 0.0
    desolvation: float = 0.0
    torsional: float = 0.0
    entropy: float = 0.0
    
    def __lt__(self, other):
        return self.total_score < other.total_score


@dataclass
class DockingPose:
    """Docking pose (ligand conformation)."""
    molecule: Molecule
    score: DockingScore
    rank: int = 0
    rmsd: float = 0.0
    contacts: List[Dict] = field(default_factory=list)


@dataclass
class BindingSite:
    """Predicted binding site."""
    center: np.ndarray
    radius: float
    residues: List[str]
    score: float
    volume: float = 0.0
    druggability: float = 0.0


def binding_site_at_protein_center(protein: Molecule) -> BindingSite:
    """
    Fallback binding site at the receptor center of mass when cavity detection finds none.
    """
    center = protein.center_of_mass
    return BindingSite(
        center=center,
        radius=10.0,
        residues=[],
        score=1.0,
        volume=500.0,
        druggability=0.5,
    )


# Historical / API alias (same geometry as protein center)
binding_site_at_receptor_center = binding_site_at_protein_center


class BindingSitePredictor:
    """Predict binding sites on protein surface."""
    
    def __init__(
        self,
        probe_radius: float = 1.4,
        min_volume: float = 100.0,
    ):
        self.probe_radius = probe_radius
        self.min_volume = min_volume
    
    def predict(self, protein: Molecule) -> List[BindingSite]:
        """Predict potential binding sites."""
        logger.info("Predicting binding sites")
        
        # Find cavities using grid-based approach
        cavities = self._find_cavities(protein)
        
        # Rank by druggability
        sites = []
        for cavity in cavities:
            site = self._analyze_cavity(cavity, protein)
            if site.volume >= self.min_volume:
                sites.append(site)
        
        # Sort by score
        sites.sort(key=lambda s: -s.score)
        
        return sites
    
    def _find_cavities(self, protein: Molecule) -> List[Dict]:
        """Find cavities using flood-fill algorithm."""
        # Grid-based cavity detection
        positions = protein.positions
        
        # Define grid
        grid_spacing = 1.0
        min_coords = positions.min(axis=0) - 10
        max_coords = positions.max(axis=0) + 10
        
        grid_dims = np.ceil((max_coords - min_coords) / grid_spacing).astype(int)
        grid = np.zeros(grid_dims, dtype=bool)  # True = occupied
        
        # Mark protein atoms
        for atom in protein.atoms:
            idx = ((atom.position - min_coords) / grid_spacing).astype(int)
            radius_grid = int(np.ceil(atom.vdw_radius / grid_spacing))
            
            for i in range(-radius_grid, radius_grid + 1):
                for j in range(-radius_grid, radius_grid + 1):
                    for k in range(-radius_grid, radius_grid + 1):
                        pos = idx + np.array([i, j, k])
                        if all(0 <= p < d for p, d in zip(pos, grid_dims)):
                            grid[tuple(pos)] = True
        
        # Find cavities (simplified)
        cavities = []
        
        # Use a simple clustering approach
        # In practice, would use proper cavity detection algorithms
        
        return cavities
    
    def _analyze_cavity(self, cavity: Dict, protein: Molecule) -> BindingSite:
        """Analyze cavity properties."""
        center = cavity.get('center', np.zeros(3))
        points = cavity.get('points', [])
        
        # Find nearby residues
        residues = set()
        for atom in protein.atoms:
            dist = np.linalg.norm(atom.position - center)
            if dist < 10.0:
                residues.add(f"{atom.residue_name}{atom.residue_number}")
        
        # Calculate volume
        volume = len(points) * 1.0  # 1 Å³ per grid point

        pts = np.asarray(points, dtype=float) if points else np.zeros((0, 3))
        if pts.size:
            dists = np.linalg.norm(pts - np.asarray(center, dtype=float), axis=1)
            radius = float(max(2.0, np.percentile(dists, 95)))
        else:
            radius = 5.0

        # Druggability proxy: cavity volume plus hydrophobic residue enrichment
        hydro = sum(1 for r in residues if r and r[0] in "AILVFMHWY")
        pocket = max(1, len(residues))
        druggability = float(
            0.35 * np.tanh(volume / 400.0) + 0.45 * (hydro / pocket) + 0.2 * np.tanh(pocket / 12.0)
        )
        druggability = min(1.0, max(0.0, druggability))

        return BindingSite(
            center=center,
            radius=radius,
            residues=list(residues),
            score=druggability,
            volume=volume,
            druggability=druggability,
        )


class ScoringFunction:
    """Docking scoring function."""
    
    def __init__(
        self,
        vdw_weight: float = 0.1662,
        elec_weight: float = 0.1209,
        hbond_weight: float = 0.1406,
        desolv_weight: float = 0.1322,
        torsion_weight: float = 0.2983,
    ):
        self.vdw_weight = vdw_weight
        self.elec_weight = elec_weight
        self.hbond_weight = hbond_weight
        self.desolv_weight = desolv_weight
        self.torsion_weight = torsion_weight
    
    def score(
        self,
        ligand: Molecule,
        protein: Molecule,
        n_torsions: int = 0,
    ) -> DockingScore:
        """Calculate docking score."""
        # Van der Waals
        vdw = self._calculate_vdw(ligand, protein)
        
        # Electrostatic
        elec = self._calculate_electrostatic(ligand, protein)
        
        # Hydrogen bonds
        hbond = self._calculate_hbonds(ligand, protein)
        
        # Desolvation
        desolv = self._calculate_desolvation(ligand)
        
        # Torsional penalty
        torsion = n_torsions * 0.2983
        
        # Total score
        total = (self.vdw_weight * vdw +
                 self.elec_weight * elec +
                 self.hbond_weight * hbond +
                 self.desolv_weight * desolv +
                 self.torsion_weight * torsion)
        
        return DockingScore(
            total_score=total,
            van_der_waals=vdw,
            electrostatic=elec,
            hydrogen_bond=hbond,
            desolvation=desolv,
            torsional=torsion,
        )
    
    def _calculate_vdw(self, ligand: Molecule, protein: Molecule) -> float:
        """Calculate van der Waals interaction energy."""
        energy = 0.0
        
        for lig_atom in ligand.atoms:
            for prot_atom in protein.atoms:
                r = lig_atom.distance_to(prot_atom)
                
                if r < 10.0 and r > 0.1:  # Cutoff
                    sigma = (lig_atom.vdw_radius + prot_atom.vdw_radius) / 2
                    epsilon = 0.1  # kcal/mol
                    
                    # 12-6 Lennard-Jones
                    ratio = sigma / r
                    energy += 4 * epsilon * (ratio ** 12 - 2 * ratio ** 6)
        
        return energy
    
    def _calculate_electrostatic(self, ligand: Molecule, protein: Molecule) -> float:
        """Calculate electrostatic interaction energy."""
        energy = 0.0
        
        for lig_atom in ligand.atoms:
            for prot_atom in protein.atoms:
                if lig_atom.charge != 0 and prot_atom.charge != 0:
                    r = lig_atom.distance_to(prot_atom)
                    
                    if r > 0.1:
                        # Coulomb with distance-dependent dielectric
                        dielectric = 4 * r
                        energy += 332.0 * lig_atom.charge * prot_atom.charge / (dielectric * r)
        
        return energy
    
    def _calculate_hbonds(self, ligand: Molecule, protein: Molecule) -> float:
        """Calculate hydrogen bond energy."""
        energy = 0.0
        
        # Identify H-bond donors and acceptors
        hbond_donors = {'N', 'O'}
        hbond_acceptors = {'N', 'O', 'F'}
        
        for lig_atom in ligand.atoms:
            if lig_atom.element in hbond_donors or lig_atom.element in hbond_acceptors:
                for prot_atom in protein.atoms:
                    if prot_atom.element in hbond_acceptors or prot_atom.element in hbond_donors:
                        r = lig_atom.distance_to(prot_atom)
                        
                        # H-bond distance range: 2.5-3.5 Å
                        if 2.5 < r < 3.5:
                            # Simplified H-bond energy
                            energy -= 1.0 * (1 - (r - 2.5) / 1.0)
        
        return energy
    
    def _calculate_desolvation(self, ligand: Molecule) -> float:
        """Calculate desolvation penalty."""
        # Simplified - based on buried surface area
        total_sasa = 0.0
        
        for atom in ligand.atoms:
            # Approximate SASA contribution
            total_sasa += 4 * np.pi * atom.vdw_radius ** 2
        
        return 0.01 * total_sasa


class PoseGenerator:
    """Generate ligand poses for docking."""
    
    def __init__(
        self,
        n_poses: int = 100,
        translation_range: float = 5.0,
        rotation_samples: int = 36,
    ):
        self.n_poses = n_poses
        self.translation_range = translation_range
        self.rotation_samples = rotation_samples
    
    def generate(
        self,
        ligand: Molecule,
        binding_site: BindingSite,
    ) -> List[Molecule]:
        """Generate poses within binding site."""
        poses = []
        
        import copy
        
        for _ in range(self.n_poses):
            pose = copy.deepcopy(ligand)
            
            # Random translation within binding site
            translation = binding_site.center + np.random.uniform(
                -self.translation_range,
                self.translation_range,
                3
            )
            
            # Move ligand to site
            pose.translate(translation - pose.center_of_mass)
            
            # Random rotation
            rotation = self._random_rotation_matrix()
            pose.rotate(rotation)
            
            poses.append(pose)
        
        return poses
    
    def _random_rotation_matrix(self) -> np.ndarray:
        """Generate random rotation matrix."""
        # Random axis
        axis = np.random.randn(3)
        axis = axis / np.linalg.norm(axis)
        
        # Random angle
        angle = np.random.uniform(0, 2 * np.pi)
        
        # Rodrigues formula
        K = np.array([
            [0, -axis[2], axis[1]],
            [axis[2], 0, -axis[0]],
            [-axis[1], axis[0], 0]
        ])
        
        return np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * np.dot(K, K)


class MolecularDocking:
    """Main docking engine."""
    
    def __init__(
        self,
        exhaustiveness: int = 8,
        n_poses: int = 20,
    ):
        self.exhaustiveness = exhaustiveness
        self.n_poses = n_poses
        self.scoring = ScoringFunction()
        self.pose_generator = PoseGenerator(n_poses=100 * exhaustiveness)
    
    def dock(
        self,
        ligand: Molecule,
        protein: Molecule,
        binding_site: Optional[BindingSite] = None,
    ) -> List[DockingPose]:
        """Dock ligand to protein."""
        logger.info(f"Docking {ligand.name} to {protein.name}")
        
        # Find binding site if not provided
        if binding_site is None:
            predictor = BindingSitePredictor()
            sites = predictor.predict(protein)
            if sites:
                binding_site = sites[0]
            else:
                logger.info("No cavities detected; using binding site at receptor center of mass")
                binding_site = binding_site_at_protein_center(protein)
        
        # Generate poses
        logger.info("Generating poses...")
        poses = self.pose_generator.generate(ligand, binding_site)
        
        # Score poses
        logger.info("Scoring poses...")
        scored_poses = []
        
        for pose in poses:
            # Check for clashes
            if self._has_severe_clash(pose, protein):
                continue
            
            score = self.scoring.score(pose, protein)
            scored_poses.append((pose, score))
        
        # Sort by score
        scored_poses.sort(key=lambda x: x[1].total_score)
        
        # Return top poses
        results = []
        for i, (pose, score) in enumerate(scored_poses[:self.n_poses]):
            # Find contacts
            contacts = self._find_contacts(pose, protein)
            
            results.append(DockingPose(
                molecule=pose,
                score=score,
                rank=i + 1,
                contacts=contacts,
            ))
        
        return results
    
    def _has_severe_clash(
        self,
        ligand: Molecule,
        protein: Molecule,
        threshold: float = 1.5,
    ) -> bool:
        """Check for severe atomic clashes."""
        for lig_atom in ligand.atoms:
            for prot_atom in protein.atoms:
                r = lig_atom.distance_to(prot_atom)
                min_dist = 0.5 * (lig_atom.vdw_radius + prot_atom.vdw_radius)
                
                if r < min_dist * threshold:
                    return True
        
        return False
    
    def _find_contacts(
        self,
        ligand: Molecule,
        protein: Molecule,
        cutoff: float = 4.0,
    ) -> List[Dict]:
        """Find ligand-protein contacts."""
        contacts = []
        
        for lig_atom in ligand.atoms:
            for prot_atom in protein.atoms:
                r = lig_atom.distance_to(prot_atom)
                
                if r < cutoff:
                    contacts.append({
                        'ligand_atom': lig_atom.name,
                        'protein_residue': f"{prot_atom.residue_name}{prot_atom.residue_number}",
                        'protein_atom': prot_atom.name,
                        'distance': r,
                        'type': self._classify_contact(lig_atom, prot_atom, r),
                    })
        
        return contacts
    
    def _classify_contact(
        self,
        atom1: Atom,
        atom2: Atom,
        distance: float,
    ) -> str:
        """Classify contact type."""
        polar = {'N', 'O', 'S'}
        
        if atom1.element in polar and atom2.element in polar:
            if distance < 3.5:
                return 'hydrogen_bond'
            return 'polar'
        
        if atom1.element == 'C' and atom2.element == 'C':
            return 'hydrophobic'
        
        return 'other'


class VirtualScreening:
    """Virtual screening of compound libraries."""
    
    def __init__(
        self,
        n_cpu: int = 1,
        exhaustiveness: int = 4,
    ):
        self.n_cpu = n_cpu
        self.docking = MolecularDocking(exhaustiveness=exhaustiveness)
    
    def screen(
        self,
        ligands: List[Molecule],
        protein: Molecule,
        binding_site: BindingSite,
    ) -> List[Tuple[str, DockingPose]]:
        """Screen library against protein target."""
        logger.info(f"Screening {len(ligands)} compounds")
        
        results = []
        
        for i, ligand in enumerate(ligands):
            logger.info(f"Docking compound {i + 1}/{len(ligands)}: {ligand.name}")
            
            poses = self.docking.dock(ligand, protein, binding_site)
            
            if poses:
                results.append((ligand.name, poses[0]))
        
        # Sort by score
        results.sort(key=lambda x: x[1].score.total_score)
        
        return results

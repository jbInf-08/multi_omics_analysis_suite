"""Molecular Structure Module.
==========================

Molecular structure representation and manipulation.
"""

import contextlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


# Atomic properties
ATOMIC_MASSES = {
    "H": 1.008,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "S": 32.065,
    "P": 30.974,
    "F": 18.998,
    "Cl": 35.453,
    "Br": 79.904,
    "I": 126.904,
    "Na": 22.990,
    "K": 39.098,
    "Ca": 40.078,
    "Mg": 24.305,
    "Zn": 65.38,
    "Fe": 55.845,
    "Cu": 63.546,
}

VDW_RADII = {
    "H": 1.20,
    "C": 1.70,
    "N": 1.55,
    "O": 1.52,
    "S": 1.80,
    "P": 1.80,
    "F": 1.47,
    "Cl": 1.75,
    "Br": 1.85,
    "I": 1.98,
}

COVALENT_RADII = {
    "H": 0.31,
    "C": 0.76,
    "N": 0.71,
    "O": 0.66,
    "S": 1.05,
    "P": 1.07,
    "F": 0.57,
    "Cl": 1.02,
    "Br": 1.20,
    "I": 1.39,
}


@dataclass
class Atom:
    """Atom representation."""

    index: int
    element: str
    x: float
    y: float
    z: float
    charge: float = 0.0
    mass: float = 0.0
    name: str = ""
    residue_name: str = ""
    residue_number: int = 0
    chain_id: str = "A"

    def __post_init__(self):
        if self.mass == 0:
            self.mass = ATOMIC_MASSES.get(self.element, 0.0)

    @property
    def position(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z])

    @position.setter
    def position(self, coords: np.ndarray):
        self.x, self.y, self.z = coords

    @property
    def vdw_radius(self) -> float:
        return VDW_RADII.get(self.element, 1.5)

    @property
    def covalent_radius(self) -> float:
        return COVALENT_RADII.get(self.element, 0.77)

    def distance_to(self, other: "Atom") -> float:
        """Calculate distance to another atom."""
        return np.linalg.norm(self.position - other.position)


@dataclass
class Bond:
    """Chemical bond."""

    atom1_idx: int
    atom2_idx: int
    order: int = 1  # 1=single, 2=double, 3=triple, 4=aromatic
    is_aromatic: bool = False
    length: float = 0.0

    @property
    def is_rotatable(self) -> bool:
        """Check if bond is rotatable."""
        return self.order == 1 and not self.is_aromatic


@dataclass
class Residue:
    """Residue (amino acid or nucleotide)."""

    name: str
    number: int
    chain_id: str
    atoms: list[int] = field(default_factory=list)

    # Standard amino acid properties
    AMINO_ACIDS = {
        "ALA": {"code": "A", "type": "hydrophobic"},
        "ARG": {"code": "R", "type": "positive"},
        "ASN": {"code": "N", "type": "polar"},
        "ASP": {"code": "D", "type": "negative"},
        "CYS": {"code": "C", "type": "special"},
        "GLN": {"code": "Q", "type": "polar"},
        "GLU": {"code": "E", "type": "negative"},
        "GLY": {"code": "G", "type": "special"},
        "HIS": {"code": "H", "type": "positive"},
        "ILE": {"code": "I", "type": "hydrophobic"},
        "LEU": {"code": "L", "type": "hydrophobic"},
        "LYS": {"code": "K", "type": "positive"},
        "MET": {"code": "M", "type": "hydrophobic"},
        "PHE": {"code": "F", "type": "aromatic"},
        "PRO": {"code": "P", "type": "special"},
        "SER": {"code": "S", "type": "polar"},
        "THR": {"code": "T", "type": "polar"},
        "TRP": {"code": "W", "type": "aromatic"},
        "TYR": {"code": "Y", "type": "aromatic"},
        "VAL": {"code": "V", "type": "hydrophobic"},
    }

    @property
    def one_letter_code(self) -> str:
        """Get one-letter amino acid code."""
        info = self.AMINO_ACIDS.get(self.name.upper())
        return info["code"] if info else "X"

    @property
    def residue_type(self) -> str:
        """Get residue type."""
        info = self.AMINO_ACIDS.get(self.name.upper())
        return info["type"] if info else "unknown"

    @property
    def is_amino_acid(self) -> bool:
        return self.name.upper() in self.AMINO_ACIDS


@dataclass
class Molecule:
    """Molecular structure."""

    name: str = "molecule"
    atoms: list[Atom] = field(default_factory=list)
    bonds: list[Bond] = field(default_factory=list)
    residues: list[Residue] = field(default_factory=list)

    # Adjacency list for fast lookup
    _adjacency: dict[int, set[int]] = field(default_factory=lambda: defaultdict(set))

    @property
    def num_atoms(self) -> int:
        return len(self.atoms)

    @property
    def num_bonds(self) -> int:
        return len(self.bonds)

    @property
    def num_residues(self) -> int:
        return len(self.residues)

    @property
    def molecular_weight(self) -> float:
        """Calculate molecular weight."""
        return sum(atom.mass for atom in self.atoms)

    @property
    def formula(self) -> str:
        """Get molecular formula."""
        element_counts = defaultdict(int)
        for atom in self.atoms:
            element_counts[atom.element] += 1

        # Standard ordering: C, H, then alphabetical
        formula = ""
        for element in ["C", "H"]:
            if element in element_counts:
                formula += element
                if element_counts[element] > 1:
                    formula += str(element_counts[element])

        for element in sorted(element_counts.keys()):
            if element not in ["C", "H"]:
                formula += element
                if element_counts[element] > 1:
                    formula += str(element_counts[element])

        return formula

    @property
    def center_of_mass(self) -> np.ndarray:
        """Calculate center of mass."""
        if not self.atoms:
            return np.zeros(3)

        total_mass = sum(atom.mass for atom in self.atoms)
        if total_mass == 0:
            return np.zeros(3)

        com = np.zeros(3)
        for atom in self.atoms:
            com += atom.position * atom.mass

        return com / total_mass

    @property
    def positions(self) -> np.ndarray:
        """Get all atom positions as array."""
        return np.array([atom.position for atom in self.atoms])

    @positions.setter
    def positions(self, coords: np.ndarray):
        """Set all atom positions."""
        for i, atom in enumerate(self.atoms):
            atom.position = coords[i]

    def add_atom(self, atom: Atom):
        """Add atom to molecule."""
        atom.index = len(self.atoms)
        self.atoms.append(atom)

    def add_bond(self, bond: Bond):
        """Add bond to molecule."""
        self.bonds.append(bond)
        self._adjacency[bond.atom1_idx].add(bond.atom2_idx)
        self._adjacency[bond.atom2_idx].add(bond.atom1_idx)

    def get_bonded_atoms(self, atom_idx: int) -> set[int]:
        """Get atoms bonded to given atom."""
        return self._adjacency.get(atom_idx, set())

    def get_bond(self, atom1_idx: int, atom2_idx: int) -> Bond | None:
        """Get bond between two atoms."""
        for bond in self.bonds:
            if (bond.atom1_idx == atom1_idx and bond.atom2_idx == atom2_idx) or (
                bond.atom1_idx == atom2_idx and bond.atom2_idx == atom1_idx
            ):
                return bond
        return None

    def translate(self, vector: np.ndarray):
        """Translate molecule."""
        for atom in self.atoms:
            atom.position = atom.position + vector

    def rotate(self, rotation_matrix: np.ndarray, center: np.ndarray | None = None):
        """Rotate molecule around center."""
        if center is None:
            center = self.center_of_mass

        for atom in self.atoms:
            # Translate to origin
            pos = atom.position - center
            # Rotate
            pos = np.dot(rotation_matrix, pos)
            # Translate back
            atom.position = pos + center

    def distance_matrix(self) -> np.ndarray:
        """Calculate pairwise distance matrix."""
        n = self.num_atoms
        dist = np.zeros((n, n))

        for i in range(n):
            for j in range(i + 1, n):
                d = self.atoms[i].distance_to(self.atoms[j])
                dist[i, j] = d
                dist[j, i] = d

        return dist

    def detect_bonds(self, tolerance: float = 0.4):
        """Auto-detect bonds based on distances."""
        self.bonds = []
        self._adjacency = defaultdict(set)

        for i, atom1 in enumerate(self.atoms):
            for j, atom2 in enumerate(self.atoms[i + 1 :], i + 1):
                distance = atom1.distance_to(atom2)
                max_dist = atom1.covalent_radius + atom2.covalent_radius + tolerance

                if distance < max_dist:
                    bond = Bond(atom1_idx=i, atom2_idx=j, length=distance)
                    self.add_bond(bond)

    def to_pdb(self) -> str:
        """Convert to PDB format."""
        lines = []

        for i, atom in enumerate(self.atoms):
            line = f"ATOM  {i+1:5d} {atom.name:4s} {atom.residue_name:3s} {atom.chain_id}{atom.residue_number:4d}    "
            line += f"{atom.x:8.3f}{atom.y:8.3f}{atom.z:8.3f}"
            line += f"  1.00  0.00          {atom.element:>2s}"
            lines.append(line)

        for bond in self.bonds:
            lines.append(f"CONECT{bond.atom1_idx+1:5d}{bond.atom2_idx+1:5d}")

        lines.append("END")
        return "\n".join(lines)

    @classmethod
    def from_pdb(cls, pdb_content: str) -> "Molecule":
        """Parse molecule from PDB format."""
        mol = cls()

        for line in pdb_content.strip().split("\n"):
            if line.startswith(("ATOM", "HETATM")):
                atom = Atom(
                    index=int(line[6:11].strip()),
                    name=line[12:16].strip(),
                    residue_name=line[17:20].strip(),
                    chain_id=line[21],
                    residue_number=int(line[22:26].strip()),
                    x=float(line[30:38]),
                    y=float(line[38:46]),
                    z=float(line[46:54]),
                    element=line[76:78].strip() if len(line) >= 78 else line[12:14].strip()[0],
                )
                mol.add_atom(atom)

            elif line.startswith("CONECT"):
                atoms = [
                    int(line[i : i + 5].strip()) - 1
                    for i in range(6, len(line), 5)
                    if line[i : i + 5].strip()
                ]
                if len(atoms) >= 2:
                    for bonded in atoms[1:]:
                        if bonded > atoms[0]:  # Avoid duplicates
                            mol.add_bond(Bond(atom1_idx=atoms[0], atom2_idx=bonded))

        return mol

    def get_sequence(self) -> str:
        """Get amino acid sequence."""
        return "".join(r.one_letter_code for r in self.residues if r.is_amino_acid)


class MoleculeBuilder:
    """Build molecules from scratch."""

    def __init__(self):
        self.molecule = Molecule()

    def add_atom(
        self,
        element: str,
        x: float,
        y: float,
        z: float,
        **kwargs,
    ) -> int:
        """Add atom and return its index."""
        atom = Atom(
            index=len(self.molecule.atoms),
            element=element,
            x=x,
            y=y,
            z=z,
            **kwargs,
        )
        self.molecule.add_atom(atom)
        return atom.index

    def add_bond(self, atom1: int, atom2: int, order: int = 1):
        """Add bond between atoms."""
        self.molecule.add_bond(Bond(atom1_idx=atom1, atom2_idx=atom2, order=order))

    def build(self) -> Molecule:
        """Return built molecule."""
        return self.molecule

    def build_from_smiles(self, smiles: str) -> Molecule:
        """Build 3D structure from SMILES when RDKit is installed; otherwise return an empty molecule."""
        try:
            from rdkit import Chem
            from rdkit.Chem import AllChem
        except ImportError:
            logger.warning("RDKit not installed; cannot build from SMILES")
            return Molecule()

        mol = Chem.MolFromSmiles(smiles or "")
        if mol is None:
            logger.warning("RDKit could not parse SMILES: %s", smiles)
            return Molecule()

        mol = Chem.AddHs(mol)
        try:
            params = AllChem.ETKDGv3()
        except AttributeError:
            params = AllChem.ETKDG()
        if hasattr(params, "randomSeed"):
            params.randomSeed = 0xC0FFEE
        if AllChem.EmbedMolecule(mol, params) != 0 and AllChem.EmbedMolecule(mol) != 0:
            AllChem.Compute2DCoords(mol)
        with contextlib.suppress(Exception):
            AllChem.MMFFOptimizeMolecule(mol, maxIters=200)

        conf = mol.GetConformer()
        out = Molecule(name=(smiles or "ligand")[:80])
        for atom in mol.GetAtoms():
            idx = atom.GetIdx()
            pos = conf.GetAtomPosition(idx)
            sym = atom.GetSymbol()
            out.add_atom(
                Atom(
                    index=idx,
                    element=sym,
                    x=float(pos.x),
                    y=float(pos.y),
                    z=float(pos.z),
                    name=f"{sym}{idx}",
                )
            )
        for bond in mol.GetBonds():
            out.add_bond(
                Bond(
                    atom1_idx=bond.GetBeginAtomIdx(),
                    atom2_idx=bond.GetEndAtomIdx(),
                    order=int(round(bond.GetBondTypeAsDouble())) or 1,
                )
            )
        return out


class MoleculeOptimizer:
    """Geometry optimization."""

    def __init__(self, force_field: str = "UFF"):
        self.force_field = force_field

    def optimize(
        self,
        molecule: Molecule,
        max_iterations: int = 1000,
        tolerance: float = 0.001,
    ) -> tuple[Molecule, float]:
        """Optimize molecular geometry."""
        logger.info(f"Optimizing geometry with {self.force_field}")

        # Simplified steepest descent optimization
        positions = molecule.positions.copy()

        for iteration in range(max_iterations):
            # Calculate energy and gradients
            energy, gradient = self._calculate_energy_gradient(molecule, positions)

            # Update positions
            step_size = 0.01
            positions -= step_size * gradient

            # Check convergence
            max_force = np.max(np.abs(gradient))
            if max_force < tolerance:
                logger.info(f"Converged after {iteration + 1} iterations")
                break

        # Update molecule
        molecule.positions = positions

        return molecule, energy

    def _calculate_energy_gradient(
        self,
        molecule: Molecule,
        positions: np.ndarray,
    ) -> tuple[float, np.ndarray]:
        """Calculate energy and gradient (simplified)."""
        energy = 0.0
        gradient = np.zeros_like(positions)

        # Bond stretching
        for bond in molecule.bonds:
            i, j = bond.atom1_idx, bond.atom2_idx

            r = positions[j] - positions[i]
            dist = np.linalg.norm(r)

            # Harmonic potential
            k = 500.0  # Force constant
            r0 = molecule.atoms[i].covalent_radius + molecule.atoms[j].covalent_radius

            energy += 0.5 * k * (dist - r0) ** 2

            # Gradient
            if dist > 0:
                force = -k * (dist - r0) * r / dist
                gradient[i] -= force
                gradient[j] += force

        # Van der Waals (simplified)
        for i in range(molecule.num_atoms):
            for j in range(i + 1, molecule.num_atoms):
                if j in molecule.get_bonded_atoms(i):
                    continue

                r = positions[j] - positions[i]
                dist = np.linalg.norm(r)

                if dist < 10.0:  # Cutoff
                    sigma = (molecule.atoms[i].vdw_radius + molecule.atoms[j].vdw_radius) / 2
                    epsilon = 0.1  # kcal/mol

                    # Lennard-Jones
                    if dist > 0.1:
                        ratio = sigma / dist
                        energy += 4 * epsilon * (ratio**12 - ratio**6)

                        force_mag = 24 * epsilon / dist * (2 * ratio**12 - ratio**6)
                        force = force_mag * r / dist
                        gradient[i] -= force
                        gradient[j] += force

        return energy, gradient


class ConformerGenerator:
    """Generate molecular conformers."""

    def __init__(self, num_conformers: int = 10):
        self.num_conformers = num_conformers

    def generate(self, molecule: Molecule) -> list[Molecule]:
        """Generate conformers by rotating rotatable bonds."""
        conformers = []

        # Find rotatable bonds
        rotatable = [b for b in molecule.bonds if b.is_rotatable]

        if not rotatable:
            conformers.append(molecule)
            return conformers

        # Generate conformers
        import copy

        for _i in range(self.num_conformers):
            conf = copy.deepcopy(molecule)

            # Randomly rotate each rotatable bond
            for bond in rotatable:
                angle = np.random.uniform(0, 2 * np.pi)
                self._rotate_around_bond(conf, bond, angle)

            conformers.append(conf)

        return conformers

    def _rotate_around_bond(self, molecule: Molecule, bond: Bond, angle: float):
        """Rotate atoms around a bond."""
        # Get rotation axis
        atom1 = molecule.atoms[bond.atom1_idx]
        atom2 = molecule.atoms[bond.atom2_idx]

        axis = atom2.position - atom1.position
        axis = axis / np.linalg.norm(axis)

        # Find atoms to rotate (on atom2 side)
        atoms_to_rotate = self._get_atoms_on_side(molecule, bond.atom1_idx, bond.atom2_idx)

        # Create rotation matrix (Rodrigues formula)
        K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
        R = np.eye(3) + np.sin(angle) * K + (1 - np.cos(angle)) * np.dot(K, K)

        # Rotate atoms
        for idx in atoms_to_rotate:
            atom = molecule.atoms[idx]
            pos = atom.position - atom1.position
            pos = np.dot(R, pos)
            atom.position = pos + atom1.position

    def _get_atoms_on_side(
        self,
        molecule: Molecule,
        fixed_atom: int,
        moving_atom: int,
    ) -> set[int]:
        """Get atoms on the moving side of a bond."""
        visited = {fixed_atom}
        to_visit = [moving_atom]
        result = set()

        while to_visit:
            current = to_visit.pop()
            if current in visited:
                continue

            visited.add(current)
            result.add(current)

            for neighbor in molecule.get_bonded_atoms(current):
                if neighbor not in visited:
                    to_visit.append(neighbor)

        return result

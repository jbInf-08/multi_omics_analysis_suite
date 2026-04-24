"""
Computational Chemistry Module
==============================

Molecular modeling, simulation, and drug discovery tools.
"""

from .molecular_dynamics import (
    MDSimulation,
    ForceField,
    Integrator,
    Thermostat,
    BerendsenThermostat,
    NoseHooverThermostat,
    VelocityVerletIntegrator,
    Barostat,
    TrajectoryAnalyzer,
)
from .docking import (
    MolecularDocking,
    DockingScore,
    BindingSite,
    BindingSitePredictor,
    PoseGenerator,
    ScoringFunction,
    binding_site_at_protein_center,
    binding_site_at_receptor_center,
)
from .structure import (
    Molecule,
    Atom,
    Bond,
    Residue,
    MoleculeBuilder,
    MoleculeOptimizer,
    ConformerGenerator,
)

__all__ = [
    # MD
    "MDSimulation",
    "ForceField",
    "Integrator",
    "Thermostat",
    "BerendsenThermostat",
    "NoseHooverThermostat",
    "VelocityVerletIntegrator",
    "Barostat",
    "TrajectoryAnalyzer",
    # Docking
    "MolecularDocking",
    "DockingScore",
    "BindingSite",
    "BindingSitePredictor",
    "binding_site_at_protein_center",
    "binding_site_at_receptor_center",
    "PoseGenerator",
    "ScoringFunction",
    # Structure
    "Molecule",
    "Atom",
    "Bond",
    "Residue",
    "MoleculeBuilder",
    "MoleculeOptimizer",
    "ConformerGenerator",
]

try:
    from .descriptors import (
        MolecularDescriptors,
        Fingerprints,
        SMILES,
        InChI,
    )

    __all__.extend(
        [
            "MolecularDescriptors",
            "Fingerprints",
            "SMILES",
            "InChI",
        ]
    )
except ImportError:
    pass

try:
    from .qsar import (
        QSARModel,
        ActivityPredictor,
        ToxicityPredictor,
        ADMETPredictor,
    )

    __all__.extend(
        [
            "QSARModel",
            "ActivityPredictor",
            "ToxicityPredictor",
            "ADMETPredictor",
        ]
    )
except ImportError:
    pass

try:
    from .visualization import (
        MoleculeVisualizer,
        TrajectoryVisualizer,
        InteractionVisualizer,
    )

    __all__.extend(
        [
            "MoleculeVisualizer",
            "TrajectoryVisualizer",
            "InteractionVisualizer",
        ]
    )
except ImportError:
    pass

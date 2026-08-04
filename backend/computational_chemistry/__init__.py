"""Computational Chemistry Module.
==============================

Molecular modeling, simulation, and drug discovery tools.
"""

from .docking import (
    BindingSite,
    BindingSitePredictor,
    DockingScore,
    MolecularDocking,
    PoseGenerator,
    ScoringFunction,
    binding_site_at_protein_center,
    binding_site_at_receptor_center,
)
from .molecular_dynamics import (
    Barostat,
    BerendsenThermostat,
    ForceField,
    Integrator,
    MDSimulation,
    NoseHooverThermostat,
    Thermostat,
    TrajectoryAnalyzer,
    VelocityVerletIntegrator,
)
from .structure import (
    Atom,
    Bond,
    ConformerGenerator,
    Molecule,
    MoleculeBuilder,
    MoleculeOptimizer,
    Residue,
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
        SMILES,
        Fingerprints,
        InChI,
        MolecularDescriptors,
    )

    __all__.extend(
        [
            "MolecularDescriptors",
            "Fingerprints",
            "SMILES",
            "InChI",
        ]
    )
# Optional extra: these names are exported when the dependency is installed
# and absent otherwise, which is what the __all__ additions above express.
except ImportError:
    pass

try:
    from .qsar import (
        ActivityPredictor,
        ADMETPredictor,
        QSARModel,
        ToxicityPredictor,
    )

    __all__.extend(
        [
            "QSARModel",
            "ActivityPredictor",
            "ToxicityPredictor",
            "ADMETPredictor",
        ]
    )
# Optional extra: these names are exported when the dependency is installed
# and absent otherwise, which is what the __all__ additions above express.
except ImportError:
    pass

try:
    from .visualization import (
        InteractionVisualizer,
        MoleculeVisualizer,
        TrajectoryVisualizer,
    )

    __all__.extend(
        [
            "MoleculeVisualizer",
            "TrajectoryVisualizer",
            "InteractionVisualizer",
        ]
    )
# Optional extra: these names are exported when the dependency is installed
# and absent otherwise, which is what the __all__ additions above express.
except ImportError:
    pass

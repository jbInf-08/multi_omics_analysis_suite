"""
Molecular Dynamics Module
=========================

MD simulation and trajectory analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
import numpy as np
import logging

from .structure import Molecule, Atom

logger = logging.getLogger(__name__)


@dataclass
class MDState:
    """Molecular dynamics simulation state."""
    positions: np.ndarray
    velocities: np.ndarray
    forces: np.ndarray
    box: np.ndarray  # Box vectors
    step: int = 0
    time: float = 0.0  # ps
    potential_energy: float = 0.0
    kinetic_energy: float = 0.0
    temperature: float = 0.0
    pressure: float = 0.0
    
    @property
    def total_energy(self) -> float:
        return self.potential_energy + self.kinetic_energy


@dataclass
class TrajectoryFrame:
    """Single frame from MD trajectory."""
    step: int
    time: float
    positions: np.ndarray
    velocities: Optional[np.ndarray] = None
    box: Optional[np.ndarray] = None
    energy: float = 0.0
    temperature: float = 0.0


class ForceField(ABC):
    """Abstract force field."""
    
    @abstractmethod
    def calculate_forces(
        self,
        positions: np.ndarray,
        molecule: Molecule,
        box: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """Calculate forces and potential energy."""
        pass


class SimpleLJForceField(ForceField):
    """Simple Lennard-Jones force field."""
    
    def __init__(
        self,
        epsilon: float = 0.1,  # kcal/mol
        sigma: float = 3.4,    # Angstrom
        cutoff: float = 12.0,
    ):
        self.epsilon = epsilon
        self.sigma = sigma
        self.cutoff = cutoff
    
    def calculate_forces(
        self,
        positions: np.ndarray,
        molecule: Molecule,
        box: np.ndarray,
    ) -> Tuple[np.ndarray, float]:
        """Calculate LJ forces."""
        n_atoms = len(positions)
        forces = np.zeros_like(positions)
        energy = 0.0
        
        for i in range(n_atoms):
            for j in range(i + 1, n_atoms):
                # Distance vector with periodic boundary
                r_vec = positions[j] - positions[i]
                r_vec = self._apply_pbc(r_vec, box)
                r = np.linalg.norm(r_vec)
                
                if r < self.cutoff and r > 0.1:
                    # LJ potential
                    ratio = self.sigma / r
                    ratio6 = ratio ** 6
                    ratio12 = ratio6 ** 2
                    
                    energy += 4 * self.epsilon * (ratio12 - ratio6)
                    
                    # Force magnitude
                    force_mag = 24 * self.epsilon / r * (2 * ratio12 - ratio6)
                    
                    # Force vector
                    force = force_mag * r_vec / r
                    forces[i] -= force
                    forces[j] += force
        
        return forces, energy
    
    def _apply_pbc(self, r_vec: np.ndarray, box: np.ndarray) -> np.ndarray:
        """Apply periodic boundary conditions."""
        # Minimum image convention
        for i in range(3):
            if box[i] > 0:
                while r_vec[i] > box[i] / 2:
                    r_vec[i] -= box[i]
                while r_vec[i] < -box[i] / 2:
                    r_vec[i] += box[i]
        return r_vec


class Integrator(ABC):
    """Abstract integrator."""
    
    def __init__(self, dt: float = 0.002):  # 2 fs
        self.dt = dt
    
    @abstractmethod
    def step(
        self,
        state: MDState,
        molecule: Molecule,
        force_field: ForceField,
    ) -> MDState:
        """Perform one integration step."""
        pass


class VelocityVerletIntegrator(Integrator):
    """Velocity Verlet integrator."""
    
    def step(
        self,
        state: MDState,
        molecule: Molecule,
        force_field: ForceField,
    ) -> MDState:
        """Velocity Verlet integration step."""
        masses = np.array([atom.mass for atom in molecule.atoms])
        
        # Half step velocity
        v_half = state.velocities + 0.5 * self.dt * state.forces / masses[:, np.newaxis]
        
        # Full step position
        new_positions = state.positions + self.dt * v_half
        
        # Calculate new forces
        new_forces, energy = force_field.calculate_forces(
            new_positions, molecule, state.box
        )
        
        # Complete velocity step
        new_velocities = v_half + 0.5 * self.dt * new_forces / masses[:, np.newaxis]
        
        # Calculate kinetic energy
        kinetic = 0.5 * np.sum(masses[:, np.newaxis] * new_velocities ** 2)
        
        # Temperature
        n_atoms = len(molecule.atoms)
        temperature = 2 * kinetic / (3 * n_atoms * 0.001987)  # kB in kcal/mol/K
        
        return MDState(
            positions=new_positions,
            velocities=new_velocities,
            forces=new_forces,
            box=state.box,
            step=state.step + 1,
            time=state.time + self.dt,
            potential_energy=energy,
            kinetic_energy=kinetic,
            temperature=temperature,
        )


class Thermostat(ABC):
    """Abstract thermostat."""
    
    def __init__(self, target_temperature: float = 300.0):
        self.target_temperature = target_temperature
    
    @abstractmethod
    def apply(self, state: MDState, molecule: Molecule) -> MDState:
        """Apply thermostat."""
        pass


class BerendsenThermostat(Thermostat):
    """Berendsen thermostat."""
    
    def __init__(self, target_temperature: float = 300.0, tau: float = 0.1):
        super().__init__(target_temperature)
        self.tau = tau  # Coupling time constant
    
    def apply(self, state: MDState, molecule: Molecule) -> MDState:
        """Apply Berendsen velocity scaling."""
        if state.temperature > 0:
            lambda_scale = np.sqrt(
                1 + (0.002 / self.tau) * (self.target_temperature / state.temperature - 1)
            )
            
            state.velocities *= lambda_scale
            
            # Recalculate temperature
            masses = np.array([atom.mass for atom in molecule.atoms])
            kinetic = 0.5 * np.sum(masses[:, np.newaxis] * state.velocities ** 2)
            state.kinetic_energy = kinetic
            state.temperature = 2 * kinetic / (3 * len(molecule.atoms) * 0.001987)
        
        return state


class NoseHooverThermostat(Thermostat):
    """Nose-Hoover thermostat."""
    
    def __init__(
        self,
        target_temperature: float = 300.0,
        tau: float = 1.0,
    ):
        super().__init__(target_temperature)
        self.tau = tau
        self.xi = 0.0  # Thermostat variable
        self.Q = 1.0   # Thermostat mass
    
    def apply(self, state: MDState, molecule: Molecule) -> MDState:
        """Apply Nose-Hoover thermostat."""
        n_atoms = len(molecule.atoms)
        kT = 0.001987 * self.target_temperature
        
        # Update thermostat variable
        self.xi += 0.002 * (state.temperature - self.target_temperature) / (self.Q * kT)
        
        # Scale velocities
        scale = np.exp(-0.002 * self.xi)
        state.velocities *= scale
        
        # Recalculate
        masses = np.array([atom.mass for atom in molecule.atoms])
        kinetic = 0.5 * np.sum(masses[:, np.newaxis] * state.velocities ** 2)
        state.kinetic_energy = kinetic
        state.temperature = 2 * kinetic / (3 * n_atoms * 0.001987)
        
        return state


class Barostat(ABC):
    """Abstract barostat."""
    
    def __init__(self, target_pressure: float = 1.0):
        self.target_pressure = target_pressure  # atm
    
    @abstractmethod
    def apply(self, state: MDState, molecule: Molecule) -> MDState:
        """Apply barostat."""
        pass


class BerendsenBarostat(Barostat):
    """Berendsen barostat."""
    
    def __init__(
        self,
        target_pressure: float = 1.0,
        tau: float = 1.0,
        compressibility: float = 4.5e-5,
    ):
        super().__init__(target_pressure)
        self.tau = tau
        self.compressibility = compressibility
    
    def apply(self, state: MDState, molecule: Molecule) -> MDState:
        """Apply Berendsen pressure coupling."""
        # Calculate instantaneous pressure (simplified)
        volume = np.prod(state.box)
        pressure = state.temperature * len(molecule.atoms) * 0.001987 / volume
        
        # Scale factor
        mu = 1 - (0.002 / self.tau) * self.compressibility * (self.target_pressure - pressure)
        mu = mu ** (1/3)
        
        # Scale box and positions
        state.box *= mu
        state.positions *= mu
        state.pressure = pressure
        
        return state


class MDSimulation:
    """Molecular dynamics simulation."""
    
    def __init__(
        self,
        molecule: Molecule,
        force_field: ForceField = None,
        integrator: Integrator = None,
        thermostat: Thermostat = None,
        barostat: Barostat = None,
    ):
        self.molecule = molecule
        self.force_field = force_field or SimpleLJForceField()
        self.integrator = integrator or VelocityVerletIntegrator()
        self.thermostat = thermostat
        self.barostat = barostat
        
        self.state: Optional[MDState] = None
        self.trajectory: List[TrajectoryFrame] = []
    
    def initialize(
        self,
        box_size: float = 50.0,
        temperature: float = 300.0,
    ):
        """Initialize simulation."""
        logger.info("Initializing MD simulation")
        
        positions = self.molecule.positions.copy()
        n_atoms = len(positions)
        
        # Random velocities from Maxwell-Boltzmann
        masses = np.array([atom.mass for atom in self.molecule.atoms])
        kT = 0.001987 * temperature  # kcal/mol
        
        velocities = np.random.randn(n_atoms, 3)
        for i in range(n_atoms):
            velocities[i] *= np.sqrt(kT / masses[i])
        
        # Remove center of mass motion
        total_mass = np.sum(masses)
        com_velocity = np.sum(masses[:, np.newaxis] * velocities, axis=0) / total_mass
        velocities -= com_velocity
        
        # Box
        box = np.array([box_size, box_size, box_size])
        
        # Initial forces
        forces, energy = self.force_field.calculate_forces(positions, self.molecule, box)
        
        # Kinetic energy and temperature
        kinetic = 0.5 * np.sum(masses[:, np.newaxis] * velocities ** 2)
        actual_temp = 2 * kinetic / (3 * n_atoms * 0.001987)
        
        self.state = MDState(
            positions=positions,
            velocities=velocities,
            forces=forces,
            box=box,
            step=0,
            time=0.0,
            potential_energy=energy,
            kinetic_energy=kinetic,
            temperature=actual_temp,
        )
        
        logger.info(f"Initial temperature: {actual_temp:.1f} K")
    
    def run(
        self,
        n_steps: int,
        save_interval: int = 100,
        print_interval: int = 1000,
    ):
        """Run simulation."""
        logger.info(f"Running {n_steps} MD steps")
        
        for step in range(n_steps):
            # Integration step
            self.state = self.integrator.step(
                self.state, self.molecule, self.force_field
            )
            
            # Apply thermostat
            if self.thermostat:
                self.state = self.thermostat.apply(self.state, self.molecule)
            
            # Apply barostat
            if self.barostat:
                self.state = self.barostat.apply(self.state, self.molecule)
            
            # Save trajectory
            if step % save_interval == 0:
                self.trajectory.append(TrajectoryFrame(
                    step=self.state.step,
                    time=self.state.time,
                    positions=self.state.positions.copy(),
                    velocities=self.state.velocities.copy(),
                    box=self.state.box.copy(),
                    energy=self.state.total_energy,
                    temperature=self.state.temperature,
                ))
            
            # Print progress
            if step % print_interval == 0:
                logger.info(
                    f"Step {step}: T={self.state.temperature:.1f} K, "
                    f"E={self.state.total_energy:.2f} kcal/mol"
                )
    
    def minimize_energy(self, max_steps: int = 1000, tolerance: float = 0.01):
        """Energy minimization using steepest descent."""
        logger.info("Running energy minimization")
        
        positions = self.state.positions.copy()
        step_size = 0.01
        
        for step in range(max_steps):
            forces, energy = self.force_field.calculate_forces(
                positions, self.molecule, self.state.box
            )
            
            max_force = np.max(np.abs(forces))
            
            if max_force < tolerance:
                logger.info(f"Minimization converged after {step} steps")
                break
            
            # Steepest descent step
            positions += step_size * forces / np.linalg.norm(forces, axis=1, keepdims=True)
        
        self.state.positions = positions
        self.state.forces = forces
        self.state.potential_energy = energy


class TrajectoryAnalyzer:
    """Analyze MD trajectory."""
    
    def __init__(self, trajectory: List[TrajectoryFrame]):
        self.trajectory = trajectory
    
    def calculate_rmsd(
        self,
        reference_positions: np.ndarray,
        selection: Optional[List[int]] = None,
    ) -> np.ndarray:
        """Calculate RMSD over trajectory."""
        if selection is None:
            selection = list(range(len(reference_positions)))
        
        rmsds = []
        ref = reference_positions[selection]
        
        for frame in self.trajectory:
            pos = frame.positions[selection]
            
            # Center both
            pos_centered = pos - pos.mean(axis=0)
            ref_centered = ref - ref.mean(axis=0)
            
            # Calculate RMSD
            diff = pos_centered - ref_centered
            rmsd = np.sqrt(np.mean(np.sum(diff ** 2, axis=1)))
            rmsds.append(rmsd)
        
        return np.array(rmsds)
    
    def calculate_rmsf(
        self,
        selection: Optional[List[int]] = None,
    ) -> np.ndarray:
        """Calculate RMSF (root mean square fluctuation)."""
        positions = np.array([f.positions for f in self.trajectory])
        
        if selection:
            positions = positions[:, selection]
        
        # Average structure
        mean_pos = positions.mean(axis=0)
        
        # RMSF per atom
        diff = positions - mean_pos
        rmsf = np.sqrt(np.mean(np.sum(diff ** 2, axis=2), axis=0))
        
        return rmsf
    
    def calculate_radius_of_gyration(self) -> np.ndarray:
        """Calculate radius of gyration over trajectory."""
        rg_values = []
        
        for frame in self.trajectory:
            pos = frame.positions
            com = pos.mean(axis=0)
            
            # Rg = sqrt(mean(r^2))
            diff = pos - com
            rg = np.sqrt(np.mean(np.sum(diff ** 2, axis=1)))
            rg_values.append(rg)
        
        return np.array(rg_values)
    
    def calculate_distance(
        self,
        atom1: int,
        atom2: int,
    ) -> np.ndarray:
        """Calculate distance between two atoms over trajectory."""
        distances = []
        
        for frame in self.trajectory:
            d = np.linalg.norm(frame.positions[atom1] - frame.positions[atom2])
            distances.append(d)
        
        return np.array(distances)
    
    def energy_statistics(self) -> Dict:
        """Calculate energy statistics."""
        energies = np.array([f.energy for f in self.trajectory])
        temperatures = np.array([f.temperature for f in self.trajectory])
        
        return {
            'energy_mean': float(np.mean(energies)),
            'energy_std': float(np.std(energies)),
            'temperature_mean': float(np.mean(temperatures)),
            'temperature_std': float(np.std(temperatures)),
        }

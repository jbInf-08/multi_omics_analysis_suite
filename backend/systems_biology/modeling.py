"""Systems Biology Modeling Module.
===============================

ODE-based modeling, steady-state analysis, and parameter estimation.
"""

import ast
import logging
import re
import xml.sax.saxutils as xml_esc
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


def _rate_law_to_mathml(rate_law: str, id_for_name: dict[str, str]) -> str | None:
    """Map a small Python-like rate expression to Content MathML (subset).

    Supports ``+ - * / **``, unary ``-``, numeric constants, and names present
    in ``id_for_name``. Returns None if parsing fails or unsupported nodes appear.
    """

    def walk(node: ast.AST) -> str | None:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return f'<cn type="real">{node.value}</cn>'
            return None
        if isinstance(node, ast.Name):
            if node.id not in id_for_name:
                return None
            cid = xml_esc.escape(id_for_name[node.id])
            return f"<ci>{cid}</ci>"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            inner = walk(node.operand)
            if inner is None:
                return None
            return f"<apply><minus/>{inner}</apply>"
        if isinstance(node, ast.BinOp):
            la, ra = walk(node.left), walk(node.right)
            if la is None or ra is None:
                return None
            if isinstance(node.op, ast.Mult):
                tag = "times"
            elif isinstance(node.op, ast.Add):
                tag = "plus"
            elif isinstance(node.op, ast.Sub):
                tag = "minus"
            elif isinstance(node.op, ast.Div):
                tag = "divide"
            elif isinstance(node.op, ast.Pow):
                tag = "power"
            else:
                return None
            return f"<apply><{tag}/>{la}{ra}</apply>"
        return None

    try:
        tree = ast.parse(rate_law.strip(), mode="eval")
    except SyntaxError:
        return None
    body = walk(tree)
    return body


@dataclass
class Species:
    """Model species (variable)."""

    name: str
    initial_value: float = 0.0
    compartment: str = "default"
    is_constant: bool = False


@dataclass
class Parameter:
    """Model parameter."""

    name: str
    value: float
    bounds: tuple[float, float] = (0.0, float("inf"))
    is_fitted: bool = False


@dataclass
class Reaction:
    """Model reaction."""

    name: str
    reactants: dict[str, int]  # species -> stoichiometry
    products: dict[str, int]
    rate_law: str  # Expression as string
    parameters: list[str]


class ODEModel:
    """ODE-based kinetic model."""

    def __init__(self, name: str = "model"):
        self.name = name
        self.species: dict[str, Species] = {}
        self.parameters: dict[str, Parameter] = {}
        self.reactions: list[Reaction] = []
        self._compiled_rates: list[Callable] = []

    def add_species(self, species: Species):
        """Add species to model."""
        self.species[species.name] = species

    def add_parameter(self, parameter: Parameter):
        """Add parameter to model."""
        self.parameters[parameter.name] = parameter

    def add_reaction(self, reaction: Reaction):
        """Add reaction to model."""
        self.reactions.append(reaction)

    def get_initial_state(self) -> np.ndarray:
        """Get initial species concentrations."""
        return np.array([s.initial_value for s in self.species.values()])

    def get_parameter_values(self) -> dict[str, float]:
        """Get parameter values."""
        return {p.name: p.value for p in self.parameters.values()}

    def compile(self):
        """Compile rate expressions."""
        logger.info("Compiling model")

        self._compiled_rates = []
        species_names = list(self.species.keys())
        param_names = list(self.parameters.keys())

        for reaction in self.reactions:
            # Create rate function
            expr = reaction.rate_law

            # Replace species and parameter names
            for i, name in enumerate(species_names):
                expr = expr.replace(name, f"y[{i}]")

            for name in param_names:
                expr = expr.replace(name, f"params['{name}']")

            # Compile
            rate_func = eval(f"lambda y, params: {expr}")
            self._compiled_rates.append(rate_func)

    def derivatives(
        self,
        y: np.ndarray,
        t: float,
        params: dict[str, float],
    ) -> np.ndarray:
        """Calculate derivatives (dy/dt)."""
        species_names = list(self.species.keys())
        n = len(species_names)

        dydt = np.zeros(n)

        for i, reaction in enumerate(self.reactions):
            # Calculate rate
            rate = self._compiled_rates[i](y, params) if self._compiled_rates else 0.0

            # Apply stoichiometry
            for species, stoich in reaction.reactants.items():
                idx = species_names.index(species)
                dydt[idx] -= stoich * rate

            for species, stoich in reaction.products.items():
                idx = species_names.index(species)
                dydt[idx] += stoich * rate

        return dydt

    def simulate(
        self,
        time_points: np.ndarray,
        params: dict[str, float] | None = None,
    ) -> dict[str, np.ndarray]:
        """Simulate model."""
        if params is None:
            params = self.get_parameter_values()

        y0 = self.get_initial_state()

        # Simple Euler integration
        dt = time_points[1] - time_points[0] if len(time_points) > 1 else 0.1

        results = {s: [y0[i]] for i, s in enumerate(self.species.keys())}
        results["time"] = [time_points[0]]

        y = y0.copy()
        t = time_points[0]

        for t_next in time_points[1:]:
            while t < t_next:
                dydt = self.derivatives(y, t, params)

                # RK4 integration
                k1 = dydt
                k2 = self.derivatives(y + 0.5 * dt * k1, t + 0.5 * dt, params)
                k3 = self.derivatives(y + 0.5 * dt * k2, t + 0.5 * dt, params)
                k4 = self.derivatives(y + dt * k3, t + dt, params)

                y = y + (dt / 6) * (k1 + 2 * k2 + 2 * k3 + k4)
                y = np.maximum(y, 0)  # Ensure non-negative
                t += dt

            for i, s in enumerate(self.species.keys()):
                results[s].append(y[i])
            results["time"].append(t_next)

        return {k: np.array(v) for k, v in results.items()}

    def to_sbml(self) -> str:
        """Export SBML Level 3 Version 2 (minimal valid skeleton).

        Kinetic ``math`` is Content MathML when the rate law parses as a simple
        arithmetic expression over known species/parameters; otherwise a neutral
        constant is used and the full expression is kept in ``notes``. Strict SBML
        validators and simulators often expect libSBML-built models with complete
        MathML or SBML-specific function definitions.
        """

        def sid(name: str) -> str:
            raw = re.sub(r"[^0-9a-zA-Z_]", "_", (name or "model")[:240])
            if not raw or raw[0].isdigit():
                raw = "s_" + raw
            return raw or "s"

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<sbml xmlns="http://www.sbml.org/sbml/level3/version2/core" level="3" version="2">',
            f'<model id="{sid(self.name)}" name="{xml_esc.escape(self.name)}">',
            "<listOfCompartments>"
            '<compartment id="c1" spatialDimensions="3" size="1" constant="true"/>'
            "</listOfCompartments>",
            "<listOfSpecies>",
        ]
        for sp in self.species.values():
            lines.append(
                f'<species id="{sid(sp.name)}" compartment="c1" '
                f'initialConcentration="{sp.initial_value:g}" '
                f'hasOnlySubstanceUnits="true" boundaryCondition="false" constant="false"/>'
            )
        lines.append("</listOfSpecies><listOfParameters>")
        for p in self.parameters.values():
            lines.append(f'<parameter id="{sid(p.name)}" value="{p.value:g}" constant="true"/>')
        lines.append("</listOfParameters><listOfReactions>")
        id_for_name = {s.name: sid(s.name) for s in self.species.values()}
        id_for_name.update({p.name: sid(p.name) for p in self.parameters.values()})
        for rx in self.reactions:
            lines.append(f'<reaction id="{sid(rx.name)}" reversible="false">')
            lines.append("<listOfReactants>")
            for species, stoich in rx.reactants.items():
                lines.append(
                    f'<speciesReference species="{sid(species)}" stoichiometry="{stoich}" constant="true"/>'
                )
            lines.append("</listOfReactants><listOfProducts>")
            for species, stoich in rx.products.items():
                lines.append(
                    f'<speciesReference species="{sid(species)}" stoichiometry="{stoich}" constant="true"/>'
                )
            mm = _rate_law_to_mathml(rx.rate_law, id_for_name)
            if mm is None:
                mm = '<cn type="integer">1</cn>'
            lines.append(
                "</listOfProducts><kineticLaw>"
                f'<math xmlns="http://www.w3.org/1998/Math/MathML">{mm}</math>'
                f'<notes><body xmlns="http://www.w3.org/1999/xhtml">'
                f"<p>{xml_esc.escape(rx.rate_law)}</p></body></notes>"
                "</kineticLaw></reaction>"
            )
        lines.extend(["</listOfReactions>", "</model></sbml>"])
        return "\n".join(lines)


class SteadyStateAnalysis:
    """Steady-state analysis of ODE models."""

    def __init__(self, model: ODEModel):
        self.model = model

    def find_steady_state(
        self,
        params: dict[str, float] | None = None,
        initial_guess: np.ndarray | None = None,
        max_iterations: int = 10000,
        tolerance: float = 1e-8,
    ) -> tuple[np.ndarray, bool]:
        """Find steady state using Newton's method."""
        if params is None:
            params = self.model.get_parameter_values()

        y = self.model.get_initial_state() if initial_guess is None else initial_guess.copy()

        # Run simulation to approach steady state
        dt = 0.01

        for _i in range(max_iterations):
            dydt = self.model.derivatives(y, 0, params)

            # Check convergence
            if np.max(np.abs(dydt)) < tolerance:
                return y, True

            # Update
            y = y + dt * dydt
            y = np.maximum(y, 0)

        return y, False

    def stability_analysis(
        self,
        steady_state: np.ndarray,
        params: dict[str, float] | None = None,
    ) -> dict:
        """Analyze stability of steady state."""
        if params is None:
            params = self.model.get_parameter_values()

        # Calculate Jacobian numerically
        n = len(steady_state)
        jacobian = np.zeros((n, n))

        epsilon = 1e-6
        f0 = self.model.derivatives(steady_state, 0, params)

        for j in range(n):
            y_perturbed = steady_state.copy()
            y_perturbed[j] += epsilon
            f1 = self.model.derivatives(y_perturbed, 0, params)
            jacobian[:, j] = (f1 - f0) / epsilon

        # Calculate eigenvalues
        eigenvalues = np.linalg.eigvals(jacobian)

        # Check stability
        is_stable = all(np.real(ev) < 0 for ev in eigenvalues)

        return {
            "jacobian": jacobian,
            "eigenvalues": eigenvalues,
            "is_stable": is_stable,
            "dominant_eigenvalue": eigenvalues[np.argmax(np.real(eigenvalues))],
        }


class SensitivityAnalysis:
    """Parameter sensitivity analysis."""

    def __init__(self, model: ODEModel):
        self.model = model

    def local_sensitivity(
        self,
        time_points: np.ndarray,
        output_species: str,
        params: dict[str, float] | None = None,
        delta: float = 0.01,
    ) -> dict[str, np.ndarray]:
        """Calculate local sensitivities."""
        if params is None:
            params = self.model.get_parameter_values()

        # Baseline simulation
        baseline = self.model.simulate(time_points, params)
        baseline_output = baseline[output_species]

        sensitivities = {}

        for param_name in params:
            # Perturbed simulation
            perturbed_params = params.copy()
            perturbed_params[param_name] *= 1 + delta

            perturbed = self.model.simulate(time_points, perturbed_params)
            perturbed_output = perturbed[output_species]

            # Calculate sensitivity
            param_value = params[param_name]
            if param_value != 0:
                sensitivity = (perturbed_output - baseline_output) / (delta * param_value)
                sensitivity *= param_value / (baseline_output + 1e-10)  # Normalized
            else:
                sensitivity = np.zeros_like(baseline_output)

            sensitivities[param_name] = sensitivity

        return sensitivities

    def global_sensitivity(
        self,
        time_point: float,
        output_species: str,
        n_samples: int = 1000,
    ) -> dict[str, float]:
        """Global sensitivity using Sobol indices (simplified)."""
        params = self.model.get_parameter_values()
        param_names = list(params.keys())

        # Sample parameter space
        samples = []
        for _ in range(n_samples):
            sample = {}
            for name in param_names:
                base_value = params[name]
                # Sample from uniform distribution around base value
                sample[name] = base_value * np.random.uniform(0.5, 1.5)
            samples.append(sample)

        # Simulate for each sample
        outputs = []
        for sample in samples:
            result = self.model.simulate(np.array([0, time_point]), sample)
            outputs.append(result[output_species][-1])

        outputs = np.array(outputs)

        # Calculate variance-based sensitivity (simplified)
        total_variance = np.var(outputs)

        sensitivities = {}
        for param_name in param_names:
            param_values = np.array([s[param_name] for s in samples])

            # Correlation as proxy for sensitivity
            if total_variance > 0:
                correlation = np.corrcoef(param_values, outputs)[0, 1]
                sensitivities[param_name] = correlation**2
            else:
                sensitivities[param_name] = 0.0

        return sensitivities


class ParameterEstimation:
    """Parameter estimation from experimental data."""

    def __init__(self, model: ODEModel):
        self.model = model

    def fit(
        self,
        experimental_data: dict[str, tuple[np.ndarray, np.ndarray]],  # species -> (time, values)
        parameter_bounds: dict[str, tuple[float, float]] | None = None,
        max_iterations: int = 1000,
    ) -> tuple[dict[str, float], float]:
        """Fit parameters to experimental data."""
        logger.info("Fitting parameters to experimental data")

        params = self.model.get_parameter_values()
        param_names = list(params.keys())

        if parameter_bounds is None:
            parameter_bounds = {
                name: (0.001 * params[name], 100 * params[name]) for name in param_names
            }

        # Simple gradient descent optimization
        best_params = params.copy()
        best_cost = self._calculate_cost(params, experimental_data)

        learning_rate = 0.1

        for _iteration in range(max_iterations):
            # Calculate gradient numerically
            gradient = {}
            delta = 0.01

            for name in param_names:
                params_plus = params.copy()
                params_plus[name] *= 1 + delta
                cost_plus = self._calculate_cost(params_plus, experimental_data)

                params_minus = params.copy()
                params_minus[name] *= 1 - delta
                cost_minus = self._calculate_cost(params_minus, experimental_data)

                gradient[name] = (cost_plus - cost_minus) / (2 * delta * params[name])

            # Update parameters
            for name in param_names:
                params[name] -= learning_rate * gradient[name] * params[name]

                # Apply bounds
                bounds = parameter_bounds.get(name, (0, float("inf")))
                params[name] = max(bounds[0], min(bounds[1], params[name]))

            # Check improvement
            cost = self._calculate_cost(params, experimental_data)

            if cost < best_cost:
                best_cost = cost
                best_params = params.copy()

            # Reduce learning rate
            learning_rate *= 0.999

        return best_params, best_cost

    def _calculate_cost(
        self,
        params: dict[str, float],
        experimental_data: dict[str, tuple[np.ndarray, np.ndarray]],
    ) -> float:
        """Calculate cost (sum of squared errors)."""
        total_cost = 0.0

        for species, (times, values) in experimental_data.items():
            simulation = self.model.simulate(times, params)

            if species in simulation:
                predicted = simulation[species]
                residuals = predicted - values
                total_cost += np.sum(residuals**2)

        return total_cost


class Bifurcation:
    """Bifurcation analysis."""

    def __init__(self, model: ODEModel):
        self.model = model
        self.ss_analyzer = SteadyStateAnalysis(model)

    def one_parameter(
        self,
        parameter_name: str,
        parameter_range: np.ndarray,
        output_species: str,
    ) -> dict:
        """One-parameter bifurcation analysis."""
        logger.info(f"Bifurcation analysis for {parameter_name}")

        params = self.model.get_parameter_values()

        steady_states = []
        stability = []

        for param_value in parameter_range:
            params[parameter_name] = param_value

            # Find steady state
            ss, converged = self.ss_analyzer.find_steady_state(params)

            if converged:
                species_names = list(self.model.species.keys())
                ss_value = ss[species_names.index(output_species)]

                # Check stability
                stab = self.ss_analyzer.stability_analysis(ss, params)

                steady_states.append(ss_value)
                stability.append(stab["is_stable"])
            else:
                steady_states.append(np.nan)
                stability.append(False)

        return {
            "parameter_values": parameter_range,
            "steady_states": np.array(steady_states),
            "stability": stability,
        }

    def detect_bifurcation_points(
        self,
        bifurcation_data: dict,
    ) -> list[float]:
        """Detect bifurcation points from bifurcation diagram."""
        stability = bifurcation_data["stability"]
        param_values = bifurcation_data["parameter_values"]

        bifurcation_points = []

        for i in range(1, len(stability)):
            if stability[i] != stability[i - 1]:
                # Interpolate bifurcation point
                bp = (param_values[i - 1] + param_values[i]) / 2
                bifurcation_points.append(bp)

        return bifurcation_points

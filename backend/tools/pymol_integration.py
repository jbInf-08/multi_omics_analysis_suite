"""PyMOL Integration Module.
========================

Integration with PyMOL for molecular structure visualization.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StructureVisualization:
    """Configuration for structure visualization."""

    pdb_id: str | None = None
    pdb_file: Path | None = None
    chain: str | None = None
    representation: str = "cartoon"  # cartoon, surface, sticks, spheres
    color_by: str = "chain"  # chain, secondary, residue, bfactor
    highlight_residues: list[int] = field(default_factory=list)
    highlight_color: str = "red"
    background_color: str = "white"
    width: int = 800
    height: int = 600


class PyMOLController:
    """Controller for PyMOL molecular visualization.

    Supports:
    - Loading structures (PDB, CIF)
    - Various representations
    - Highlighting mutations/residues
    - Rendering images
    """

    def __init__(self, use_gui: bool = False):
        """Initialize PyMOL controller.

        Args:
            use_gui: Whether to use PyMOL GUI

        """
        self.use_gui = use_gui
        self._pymol = None
        self._cmd = None

    def _ensure_pymol(self):
        """Ensure PyMOL is initialized."""
        if self._pymol is None:
            try:
                import pymol
                from pymol import cmd

                if self.use_gui:
                    pymol.finish_launching()
                else:
                    pymol.finish_launching(["-cq"])  # Quiet, no GUI

                self._pymol = pymol
                self._cmd = cmd

            except ImportError:
                raise ImportError(
                    "PyMOL not installed. Install with: pip install pymol-open-source"
                )

    def load_structure(
        self,
        pdb_id: str | None = None,
        pdb_file: Path | None = None,
        name: str | None = None,
    ) -> str:
        """Load a structure into PyMOL.

        Args:
            pdb_id: PDB ID to fetch
            pdb_file: Local PDB file
            name: Object name

        Returns:
            Object name

        """
        self._ensure_pymol()

        if pdb_id:
            name = name or pdb_id
            self._cmd.fetch(pdb_id, name)
        elif pdb_file:
            name = name or pdb_file.stem
            self._cmd.load(str(pdb_file), name)
        else:
            raise ValueError("Must provide pdb_id or pdb_file")

        return name

    def set_representation(
        self,
        representation: str = "cartoon",
        selection: str = "all",
    ):
        """Set the molecular representation.

        Args:
            representation: Type (cartoon, surface, sticks, spheres, ribbon, lines)
            selection: PyMOL selection

        """
        self._ensure_pymol()

        # Hide all first
        self._cmd.hide("all", selection)

        # Show requested representation
        self._cmd.show(representation, selection)

    def color_structure(
        self,
        color_by: str = "chain",
        selection: str = "all",
    ):
        """Color the structure.

        Args:
            color_by: Coloring scheme (chain, secondary, residue, bfactor, spectrum)
            selection: PyMOL selection

        """
        self._ensure_pymol()

        if color_by == "chain":
            self._cmd.util.cbc(selection)
        elif color_by == "secondary":
            self._cmd.color("red", f"{selection} and ss h")  # Helix
            self._cmd.color("yellow", f"{selection} and ss s")  # Sheet
            self._cmd.color("green", f"{selection} and ss l+''")  # Loop
        elif color_by == "residue":
            self._cmd.util.cbag(selection)
        elif color_by == "bfactor":
            self._cmd.spectrum("b", "blue_white_red", selection)
        elif color_by == "spectrum":
            self._cmd.spectrum("count", "rainbow", selection)

    def highlight_residues(
        self,
        residues: list[int],
        chain: str | None = None,
        color: str = "red",
        representation: str = "sticks",
    ):
        """Highlight specific residues.

        Args:
            residues: Residue numbers to highlight
            chain: Chain ID
            color: Highlight color
            representation: Representation for highlighted residues

        """
        self._ensure_pymol()

        residue_str = "+".join(str(r) for r in residues)
        selection = f"resi {residue_str}"
        if chain:
            selection += f" and chain {chain}"

        self._cmd.show(representation, selection)
        self._cmd.color(color, selection)

    def highlight_mutation(
        self,
        position: int,
        chain: str | None = None,
        wild_type: str | None = None,
        mutant: str | None = None,
        color: str = "magenta",
    ):
        """Highlight a mutation site.

        Args:
            position: Residue position
            chain: Chain ID
            wild_type: Wild-type residue (for labeling)
            mutant: Mutant residue (for labeling)
            color: Highlight color

        """
        self._ensure_pymol()

        selection = f"resi {position}"
        if chain:
            selection += f" and chain {chain}"

        # Show as sticks
        self._cmd.show("sticks", selection)
        self._cmd.color(color, selection)

        # Add label
        if wild_type and mutant:
            label = f"{wild_type}{position}{mutant}"
            self._cmd.label(f"{selection} and name CA", f'"{label}"')

    def set_view(
        self,
        zoom_selection: str | None = None,
        orient_selection: str | None = None,
    ):
        """Set the view.

        Args:
            zoom_selection: Selection to zoom to
            orient_selection: Selection to orient to

        """
        self._ensure_pymol()

        if orient_selection:
            self._cmd.orient(orient_selection)

        if zoom_selection:
            self._cmd.zoom(zoom_selection, buffer=5)
        else:
            self._cmd.zoom("all", buffer=5)

    def render_image(
        self,
        output_path: Path,
        width: int = 800,
        height: int = 600,
        ray: bool = True,
        background_color: str = "white",
    ) -> Path:
        """Render an image.

        Args:
            output_path: Output file path
            width: Image width
            height: Image height
            ray: Use ray tracing
            background_color: Background color

        Returns:
            Path to rendered image

        """
        self._ensure_pymol()

        # Set background
        self._cmd.bg_color(background_color)

        # Set viewport
        self._cmd.viewport(width, height)

        # Ray trace if requested
        if ray:
            self._cmd.ray(width, height)

        # Save image
        self._cmd.png(str(output_path), width, height, dpi=300)

        return output_path

    def create_visualization(
        self,
        config: StructureVisualization,
        output_path: Path | None = None,
    ) -> Path | None:
        """Create a complete visualization from configuration.

        Args:
            config: Visualization configuration
            output_path: Optional output path for image

        Returns:
            Path to rendered image if output_path provided

        """
        self._ensure_pymol()

        # Clear existing
        self._cmd.delete("all")

        # Load structure
        self.load_structure(config.pdb_id, config.pdb_file)

        # Select chain if specified
        if config.chain:
            self._cmd.remove(f"not chain {config.chain}")

        # Set representation
        self.set_representation(config.representation)

        # Color
        self.color_structure(config.color_by)

        # Highlight residues
        if config.highlight_residues:
            self.highlight_residues(
                config.highlight_residues,
                config.chain,
                config.highlight_color,
            )

        # Set view
        self.set_view()

        # Render if output path provided
        if output_path:
            return self.render_image(
                output_path,
                config.width,
                config.height,
                background_color=config.background_color,
            )

        return None

    def visualize_mutations(
        self,
        pdb_id: str,
        mutations: list[tuple[str, int, str]],  # (wild_type, position, mutant)
        chain: str | None = None,
        output_path: Path | None = None,
    ) -> Path | None:
        """Visualize mutations on a structure.

        Args:
            pdb_id: PDB ID
            mutations: List of mutations as (wt, pos, mut) tuples
            chain: Chain ID
            output_path: Output image path

        Returns:
            Path to rendered image

        """
        self._ensure_pymol()

        # Clear and load
        self._cmd.delete("all")
        self.load_structure(pdb_id=pdb_id)

        # Set base representation
        self.set_representation("cartoon")
        self.color_structure("chain")

        # Highlight each mutation
        for wt, pos, mut in mutations:
            self.highlight_mutation(pos, chain, wt, mut)

        # Zoom to mutations
        positions = [str(m[1]) for m in mutations]
        selection = f"resi {'+'.join(positions)}"
        self.set_view(zoom_selection=selection)

        if output_path:
            return self.render_image(output_path)

        return None

    def close(self):
        """Close PyMOL."""
        if self._pymol:
            self._cmd.quit()
            self._pymol = None
            self._cmd = None

"""
Omics Module Registry
=====================

Central registry for discovering and managing omics modules.
"""

from typing import Dict, List, Optional, Type, Set
import importlib
import pkgutil
from pathlib import Path

from backend.omics.base.omics_base import OmicsModuleBase, OmicsCategory


class OmicsRegistry:
    """
    Registry for omics modules.
    
    Provides:
    - Auto-discovery of modules
    - Module registration
    - Module lookup by name or category
    """
    
    _instance = None
    _modules: Dict[str, OmicsModuleBase] = {}
    _categories: Dict[OmicsCategory, List[str]] = {}
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._modules = {}
            cls._categories = {cat: [] for cat in OmicsCategory}
        return cls._instance
    
    def register(self, module: OmicsModuleBase) -> None:
        """
        Register an omics module.
        
        Args:
            module: Module instance to register
        """
        name = module.name.lower()
        
        if name in self._modules:
            raise ValueError(f"Module '{name}' is already registered")
        
        self._modules[name] = module
        self._categories[module.category].append(name)
    
    def unregister(self, name: str) -> None:
        """
        Unregister an omics module.
        
        Args:
            name: Module name
        """
        name = name.lower()
        
        if name not in self._modules:
            return
        
        module = self._modules[name]
        self._categories[module.category].remove(name)
        del self._modules[name]
    
    def get_module(self, name: str) -> Optional[OmicsModuleBase]:
        """
        Get module by name.
        
        Args:
            name: Module name
            
        Returns:
            Module instance or None
        """
        return self._modules.get(name.lower())
    
    def list_modules(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
    ) -> List[OmicsModuleBase]:
        """
        List registered modules.
        
        Args:
            category: Filter by category
            active_only: Only return active modules
            
        Returns:
            List of module instances
        """
        if category:
            try:
                cat = OmicsCategory(category.lower())
                names = self._categories.get(cat, [])
            except ValueError:
                return []
        else:
            names = list(self._modules.keys())
        
        modules = [self._modules[n] for n in names]
        
        if active_only:
            modules = [m for m in modules if m.is_active]
        
        return modules
    
    def list_categories(self) -> List[OmicsCategory]:
        """List all categories."""
        return list(OmicsCategory)
    
    def get_modules_by_category(self, category: OmicsCategory) -> List[str]:
        """Get module names by category."""
        return self._categories.get(category, [])
    
    async def discover_and_register_modules(self) -> int:
        """
        Discover and register all omics modules.
        
        Scans the omics package for modules and registers them.
        
        Returns:
            Number of modules registered
        """
        from backend.omics.core import (
            genomics,
            transcriptomics,
            proteomics,
            metabolomics,
            epigenomics,
            metagenomics,
            pharmacogenomics,
            lipidomics,
        )
        from backend.omics.modifications import (
            phosphoproteomics,
            glycomics,
            acetylomics,
            methylomics,
            ubiquitomics,
            kinomics,
            chromatomics,
        )
        from backend.omics.interactions import (
            interactomics,
            connectomics,
            synaptomics,
            regulomics,
            secretomics,
            degradomics,
            membranomics,
        )
        from backend.omics.clinical import (
            immunogenomics,
            pharmacoproteomics as pharmaco_prot,
            toxicogenomics,
            nutrigenomics,
            neurogenomics,
            allergomics,
        )
        from backend.omics.specialized import (
            spatialomics,
            singlecell,
            structuromics,
            exposomics,
            radiomics,
            phenomics,
            fluxomics,
            foodomics,
            ionomics,
            volatilomics,
            glycoproteomics,
            metallomics,
            microbiomics,
            paleogenomics,
            multiomics_single_cell,
            # Additional specialized modules
            bibliomics,
            cytomics,
            editomics,
            hologenomics,
            obesomics,
            organomics,
            parvomics,
            physiomics,
            speechomics,
            synthetomics,
            toponomics,
            toxomics,
            antibodyomics,
            embryomics,
            interferomics,
            mechanomics,
            researchomics,
            trialomics,
            dynomics,
        )
        
        # Core modules
        core_modules = [
            genomics.GenomicsModule(),
            transcriptomics.TranscriptomicsModule(),
            proteomics.ProteomicsModule(),
            metabolomics.MetabolomicsModule(),
            epigenomics.EpigenomicsModule(),
            metagenomics.MetagenomicsModule(),
            pharmacogenomics.PharmacogenomicsModule(),
            lipidomics.LipidomicsModule(),
        ]
        
        # Modification modules
        modification_modules = [
            phosphoproteomics.PhosphoproteomicsModule(),
            glycomics.GlycomicsModule(),
            acetylomics.AcetylomicsModule(),
            methylomics.MethylomicsModule(),
            ubiquitomics.UbiquitomicsModule(),
            kinomics.KinomicsModule(),
            chromatomics.ChromatomicsModule(),
        ]
        
        # Interaction modules
        interaction_modules = [
            interactomics.InteractomicsModule(),
            connectomics.ConnectomicsModule(),
            synaptomics.SynaptomicsModule(),
            regulomics.RegulomicsModule(),
            secretomics.SecretomicsModule(),
            degradomics.DegradomicsModule(),
            membranomics.MembranomicsModule(),
        ]
        
        # Clinical modules
        clinical_modules = [
            immunogenomics.ImmunogenomicsModule(),
            pharmaco_prot.PharmacoproteomicsModule(),
            toxicogenomics.ToxicogenomicsModule(),
            nutrigenomics.NutrigenomicsModule(),
            neurogenomics.NeurogenomicsModule(),
            allergomics.AllergomicsModule(),
        ]
        
        # Specialized modules
        specialized_modules = [
            spatialomics.SpatialomicsModule(),
            singlecell.SingleCellModule(),
            structuromics.StructuromicsModule(),
            exposomics.ExposomicsModule(),
            radiomics.RadiomicsModule(),
            phenomics.PhenomicsModule(),
            fluxomics.FluxomicsModule(),
            foodomics.FoodomicsModule(),
            ionomics.IonomicsModule(),
            volatilomics.VolatilomicsModule(),
            glycoproteomics.GlycoproteomicsModule(),
            metallomics.MetallomicsModule(),
            microbiomics.MicrobiomicsModule(),
            paleogenomics.PaleogenomicsModule(),
            multiomics_single_cell.MultiomicsSingleCellModule(),
            # Additional specialized modules
            bibliomics.BibliomicsModule(),
            cytomics.CytomicsModule(),
            editomics.EditomicsModule(),
            hologenomics.HologenomicsModule(),
            obesomics.ObesomicsModule(),
            organomics.OrganomicsModule(),
            parvomics.ParvomicsModule(),
            physiomics.PhysiomicsModule(),
            speechomics.SpeechomicsModule(),
            synthetomics.SynthetomicsModule(),
            toponomics.ToponomicsModule(),
            toxomics.ToxomicsModule(),
            antibodyomics.AntibodyomicsModule(),
            embryomics.EmbryomicsModule(),
            interferomics.InterferomicsModule(),
            mechanomics.MechanomicsModule(),
            researchomics.ResearchomicsModule(),
            trialomics.TrialomicsModule(),
            dynomics.DynomicsModule(),
        ]
        
        # Register all modules
        all_modules = (
            core_modules
            + modification_modules
            + interaction_modules
            + clinical_modules
            + specialized_modules
        )
        
        count = 0
        for module in all_modules:
            try:
                self.register(module)
                count += 1
            except ValueError:
                pass  # Already registered
        
        return count
    
    def discover_modules(self) -> int:
        """
        Synchronous wrapper for module discovery.
        
        Returns:
            Number of modules registered
        """
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # If we're in an async context, create a task
            return loop.run_until_complete(self.discover_and_register_modules())
        except RuntimeError:
            # No running loop, create one
            return asyncio.run(self.discover_and_register_modules())
    
    def list_all_modules(self) -> List[str]:
        """
        List all registered module names.
        
        Returns:
            List of module names
        """
        return list(self._modules.keys())
    
    def __len__(self) -> int:
        return len(self._modules)
    
    def __contains__(self, name: str) -> bool:
        return name.lower() in self._modules

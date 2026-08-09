"""Composition Root for Synthetic Biology Plugin.

This module provides the ServiceFactory which centralizes the instantiation
and wiring of all domain and infrastructure services, adhering to the
Dependency Inversion Principle.
"""

from typing import Any

from biopro.plugins.synthetic_biology.analysis.state import SynBioState


class ServiceFactory:
    """Manages creation and dependency injection of all core services."""

    def __init__(self, state: SynBioState, parent_widget: Any = None):
        """Initialize the factory with the root state and UI parent.

        Args:
            state: The global SynBio state object.
            parent_widget: The main UI panel (used as QWidget parent for dialogs).
        """
        self.state = state
        self.parent_widget = parent_widget
        self._services: dict[str, Any] = {}

    def build_all(self) -> None:
        """Instantiates all services and wires them up."""
        from analysis.api.client import IGemClient, SynBioHubClient
        import os
        from analysis.catalogue.repository import JsonPartRepository
        from analysis.catalogue.service import PartsCatalogueService

        self._services["igem_client"] = IGemClient()
        self._services["synbiohub_client"] = SynBioHubClient()
        
        # Setup the Parts Catalogue
        from pathlib import Path
        
        # os.getcwd() evaluates to '/' when running inside a macOS app bundle.
        # Instead, we should save it relative to the plugin's root directory,
        # or inside the user's ~/.biopro data folder. For now, we'll keep it in the plugin root.
        plugin_root = Path(__file__).parent.parent
        catalogue_path = str(plugin_root / "catalogue.json")
        
        repo = JsonPartRepository(catalogue_path)
        catalogue_service = PartsCatalogueService(repo)
        catalogue_service.initialize_cello_parts()
        self._services["parts_catalogue"] = catalogue_service

    def get(self, service_name: str) -> Any:
        """Retrieve a registered service by name.

        Args:
            service_name: The internal name of the service.

        Returns:
            The service instance, or None if not found.
        """
        return self._services.get(service_name)

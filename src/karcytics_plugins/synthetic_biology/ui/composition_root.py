"""Composition Root for Synthetic Biology Plugin.

This module provides the ServiceFactory which centralizes the instantiation
and wiring of all domain and infrastructure services, adhering to the
Dependency Inversion Principle.
"""

from pathlib import Path
from typing import Any

from ..analysis.api.client import IGemClient, SynBioHubClient
from ..analysis.catalogue.repository import JsonPartRepository
from ..analysis.catalogue.service import PartsCatalogueService
from ..analysis.state import SynBioState


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

    def build_all(self, catalogue_path: str | Path | None = None) -> None:
        """Instantiates all services and wires them up."""
        self._services["igem_client"] = IGemClient()
        self._services["synbiohub_client"] = SynBioHubClient()

        # Setup the Parts Catalogue anchored to plugin directory
        if not catalogue_path:
            plugin_dir = Path(__file__).resolve().parents[1]
            catalogue_path = plugin_dir / "catalogue.json"
        else:
            catalogue_path = Path(catalogue_path)
            if not catalogue_path.is_absolute():
                plugin_dir = Path(__file__).resolve().parents[1]
                catalogue_path = plugin_dir / catalogue_path

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

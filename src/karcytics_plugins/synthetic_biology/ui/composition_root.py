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

        # The shipped catalogue stays read-only inside the signed payload and
        # runtime writes go to the per-user directory; JsonPartRepository()
        # with no arguments resolves both layers. An explicit path means one
        # exact file and no shipped layer (tests, and anyone pointing the
        # plugin at a prepared catalogue).
        repo = JsonPartRepository(catalogue_path) if catalogue_path else JsonPartRepository()
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

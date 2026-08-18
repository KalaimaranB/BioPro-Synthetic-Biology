"""Composition Root for Synthetic Biology Plugin.

This module provides the ServiceFactory which centralizes the instantiation
and wiring of all domain and infrastructure services, adhering to the
Dependency Inversion Principle.
"""

import os
from typing import Any

from analysis.state import SynBioState
from analysis.api.client import IGemClient, SynBioHubClient
from analysis.catalogue.repository import JsonPartRepository
from analysis.catalogue.service import PartsCatalogueService


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

    def build_all(self, catalogue_path: str | None = None) -> None:
        """Instantiates all services and wires them up."""
        self._services["igem_client"] = IGemClient()
        self._services["synbiohub_client"] = SynBioHubClient()

        # Setup the Parts Catalogue
        if not catalogue_path:
            cwd = os.getcwd()
            if cwd != "/" and not cwd.startswith("/System") and os.access(cwd, os.W_OK):
                catalogue_path = os.path.join(cwd, "catalogue.json")
            else:
                user_data_dir = os.path.expanduser("~/.biopro/synthetic_biology")
                try:
                    os.makedirs(user_data_dir, exist_ok=True)
                    catalogue_path = os.path.join(user_data_dir, "catalogue.json")
                except OSError:
                    catalogue_path = os.path.expanduser("~/catalogue.json")

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

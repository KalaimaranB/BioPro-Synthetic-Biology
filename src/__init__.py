"""Synthetic Biology Workspace — BioPro plugin entry point.

A scientist-centric environment for designing, validating, and simulating
biological logic gates and synthetic genetic circuits.
"""

__version__ = "0.1.0"
__plugin_id__ = "synthetic_biology"

import os
import sys

# Ensure the plugin's root directory is in sys.path
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

try:
    from karcytics_sdk.core import PluginBase as SDKPluginBase
except ImportError:
    try:
        from biopro_sdk.plugin import PluginBase as SDKPluginBase
    except ImportError:
        from PyQt6.QtWidgets import QWidget as SDKPluginBase


class BioProPlugin(SDKPluginBase):
    """BioPro Synthetic Biology plugin implementation for Karcytics SDK host.

    Exposes the required plugin contract: get_panel_class, create_panel, get_state,
    set_state, cleanup, and shutdown for host ModuleManager integration.
    """

    def __init__(
        self, plugin_id: str = "synthetic_biology", parent: object | None = None
    ):
        if hasattr(SDKPluginBase, "__init__") and SDKPluginBase is not object:
            try:
                pid = plugin_id if isinstance(plugin_id, str) else "synthetic_biology"
                super().__init__(pid, parent=parent)
            except Exception:
                super().__init__()
        self.plugin_id = "synthetic_biology"
        self._panel = None

    @classmethod
    def get_panel_class(cls):
        """Returns the main PyQt6 QWidget panel class to be mounted into host."""
        from .ui.main_panel import SynBioPanel

        return SynBioPanel

    def create_panel(self, parent=None):
        """Instantiates and mounts the main PyQt6 SynBioPanel onto host app."""
        from .ui.main_panel import SynBioPanel
        from .ui.composition_root import ServiceFactory
        from .analysis.state import SynBioState

        state = SynBioState()
        factory = ServiceFactory(state, parent_widget=parent)
        factory.build_all()
        self._panel = SynBioPanel(state, service_factory=factory, parent=parent)
        return self._panel

    def get_state(self) -> dict:
        """Return a shallow dictionary representing the plugin's current state."""
        if self._panel and hasattr(self._panel, "state"):
            return self._panel.state.to_dict()
        return {}

    def set_state(self, state: dict) -> None:
        """Restore internal state from dictionary."""
        if self._panel and hasattr(self._panel, "state"):
            self._panel.state.from_dict(state)

    def cleanup(self) -> None:
        """Perform plugin teardown: stop active workers and release resources."""
        if self._panel and hasattr(self._panel, "teardown"):
            self._panel.teardown()

    def shutdown(self) -> None:
        """Shutdown plugin resources."""
        self.cleanup()


SynBioPlugin = BioProPlugin


def get_plugin() -> BioProPlugin:
    """Factory function invoked by ModuleManager to instantiate the plugin."""
    return BioProPlugin()


def get_panel_class():
    """Returns the main QWidget class that should be injected into the host UI.

    Standard BioPro entry point. The core ModuleManager calls this function to
    obtain the class and instantiate it into the central workspace container.
    """
    from .ui.main_panel import SynBioPanel

    return SynBioPanel


def initialize(context=None):
    """V3 Architecture Entry Point."""
    return BioProPlugin(parent=context)


def cleanup():
    """Module-level cleanup."""
    pass


def shutdown():
    """Module-level shutdown."""
    pass

"""Synthetic Biology Workspace — Karcytics plugin entry point.

A scientist-centric environment for designing, validating, and simulating
biological logic gates and synthetic genetic circuits.
"""

from __future__ import annotations

__version__ = "0.1.0"
__plugin_id__ = "synthetic_biology"


def initialize(context=None):
    """Karcytics SDK entry point — called by ModuleManager on plugin load.

    Parameters
    ----------
    context:
        The host context object supplied by the Karcytics core (may be None
        during headless / test invocations).

    Returns:
    -------
    BioProPlugin
        A fully-constructed plugin instance ready to be mounted by the host.
    """
    return BioProPlugin(parent=context)


class BioProPlugin:
    """Karcytics plugin implementation for the Synthetic Biology module.

    Exposes the standard plugin contract expected by the host ModuleManager:
    ``initialize``, ``create_panel``, ``get_state``, ``set_state``,
    ``cleanup``, and ``shutdown``.
    """

    def __init__(self, plugin_id: str = "synthetic_biology", parent: object | None = None):
        self.plugin_id = plugin_id
        self._parent = parent
        self._panel = None

    def create_panel(self, parent=None):
        """Instantiate and return the main SynBioPanel widget.

        SynBioPanel builds its own ``SynBioState`` and ``ServiceFactory``
        internally (see ``_setup_services``), so construction only needs
        the plugin id and the Qt parent.
        """
        from .ui.main_panel import SynBioPanel

        self._panel = SynBioPanel(self.plugin_id, parent=parent)
        return self._panel

    def get_state(self) -> dict:
        """Return a shallow dictionary representing the plugin's current state."""
        if self._panel and hasattr(self._panel, "state"):
            return self._panel.state.to_dict()
        return {}

    def set_state(self, state: dict) -> None:
        """Restore internal state from a dictionary."""
        if self._panel and hasattr(self._panel, "state"):
            self._panel.state.from_dict(state)

    def cleanup(self) -> None:
        """Perform plugin teardown: stop active workers and release resources."""
        if self._panel and hasattr(self._panel, "teardown"):
            self._panel.teardown()

    def shutdown(self) -> None:
        """Shut down plugin resources (delegates to cleanup)."""
        self.cleanup()

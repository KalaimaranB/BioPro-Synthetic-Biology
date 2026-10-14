"""Synthetic Biology Workspace — Karcytics plugin entry point.

A scientist-centric environment for designing, validating, and simulating
biological logic gates and synthetic genetic circuits.
"""

from __future__ import annotations

__version__ = "0.1.1"
__plugin_id__ = "synthetic_biology"


from karcytics_sdk.plugin import PluginBase
try:
    from PySide6.QtWidgets import QWidget
except ImportError:
    import sys
    import types
    import PyQt6.QtCore
    import PyQt6.QtGui
    import PyQt6.QtWidgets

    pyside6 = types.ModuleType("PySide6")
    _qtcore = types.ModuleType("PySide6.QtCore")
    for _k, _v in PyQt6.QtCore.__dict__.items():
        setattr(_qtcore, _k, _v)
    _qtcore.Signal = PyQt6.QtCore.pyqtSignal
    _qtcore.Slot = PyQt6.QtCore.pyqtSlot
    _qtcore.Property = PyQt6.QtCore.pyqtProperty
    _qtcore.__version__ = PyQt6.QtCore.PYQT_VERSION_STR

    _qtgui = types.ModuleType("PySide6.QtGui")
    for _k, _v in PyQt6.QtGui.__dict__.items():
        setattr(_qtgui, _k, _v)

    _qtwidgets = types.ModuleType("PySide6.QtWidgets")
    for _k, _v in PyQt6.QtWidgets.__dict__.items():
        setattr(_qtwidgets, _k, _v)

    pyside6.QtCore = _qtcore
    pyside6.QtGui = _qtgui
    pyside6.QtWidgets = _qtwidgets
    pyside6.__version__ = PyQt6.QtCore.PYQT_VERSION_STR
    pyside6.__path__ = []

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = _qtcore
    sys.modules["PySide6.QtGui"] = _qtgui
    sys.modules["PySide6.QtWidgets"] = _qtwidgets
    from PySide6.QtWidgets import QWidget

try:
    import karcytics_sdk.plugin.toast as _toast_mod

    _orig_show_toast = getattr(_toast_mod, "show_toast", None)
    if callable(_orig_show_toast) and not getattr(_orig_show_toast, "_is_safe_wrapper", False):

        def _safe_show_toast(*args, **kwargs):
            kwargs.pop("level", None)
            if args and not isinstance(args[0], str):
                window = args[0]
                msg = args[1] if len(args) > 1 else ""
                rest = args[2:]
                return _orig_show_toast(msg, *rest, window=window, **kwargs)
            return _orig_show_toast(*args, **kwargs)

        _safe_show_toast._is_safe_wrapper = True
        _toast_mod.show_toast = _safe_show_toast
except Exception:
    pass


def initialize(context=None):
    """Karcytics SDK entry point — called by ModuleManager on plugin load.

    Parameters
    ----------
    context:
        The host context object supplied by the Karcytics core (may be None
        during headless / test invocations).

    Returns:
    -------
    SyntheticBiologyPlugin
        A fully-constructed plugin instance ready to be mounted by the host.
    """
    return SyntheticBiologyPlugin(parent=context)


def get_plugin(parent=None):
    """Entry point function returning the initialized SyntheticBiologyPlugin instance."""
    return initialize(context=parent)


def get_ui(parent=None):
    """Entry point function returning the SynBioPanel QWidget directly."""
    from .ui.main_panel import SynBioPanel

    return SynBioPanel(parent=parent)


class SyntheticBiologyPlugin(PluginBase):
    """Karcytics plugin implementation for the Synthetic Biology module.

    Exposes the standard plugin contract expected by the host ModuleManager:
    ``initialize``, ``create_panel``, ``get_state``, ``set_state``,
    ``cleanup``, and ``shutdown``.
    """

    def __init__(self, plugin_id: str = "synthetic_biology", parent: object | None = None):
        super().__init__(plugin_id, parent=parent if isinstance(parent, QWidget) else None)
        self.plugin_id = plugin_id
        self._parent = parent
        self._panel = None

    @classmethod
    def get_panel_class(cls):
        """Return the main PySide6 SynBioPanel class to be mounted into host UI."""
        from .ui.main_panel import SynBioPanel

        return SynBioPanel

    def create_panel(self, parent=None):
        """Instantiate and return the main SynBioPanel widget.

        SynBioPanel builds its own ``SynBioState`` and ``ServiceFactory``
        internally (see ``_setup_services``), so construction only needs
        the plugin id and the Qt parent.
        """
        from .ui.main_panel import SynBioPanel

        effective_parent = parent if parent is not None else self._parent
        self._panel = SynBioPanel(parent=effective_parent, plugin_id=self.plugin_id)
        return self._panel

    def get_state(self) -> dict:  # type: ignore[override]
        """Return a shallow dictionary representing the plugin's current state."""
        if self._panel and hasattr(self._panel, "state"):
            return self._panel.state.to_dict()
        return {}

    def set_state(self, state: dict) -> None:  # type: ignore[override]
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


# Backwards-compatibility alias for legacy code
BioProPlugin = SyntheticBiologyPlugin

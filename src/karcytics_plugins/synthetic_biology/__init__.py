"""Synthetic Biology Workspace — Karcytics plugin entry point.

A scientist-centric environment for designing, validating, and simulating
biological logic gates and synthetic genetic circuits.
"""

from __future__ import annotations

__version__ = "0.1.1"
__plugin_id__ = "synthetic_biology"


from karcytics_sdk.plugin import PluginBase
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

        _safe_show_toast._is_safe_wrapper = True  # type: ignore[attr-defined]
        _toast_mod.show_toast = _safe_show_toast
except Exception:
    pass

try:
    import karcytics_sdk.plugin.dialogs as _dialogs_mod

    for _fn_name in ("show_error", "show_warning", "show_info"):
        _orig_fn = getattr(_dialogs_mod, _fn_name, None)
        if callable(_orig_fn) and not getattr(_orig_fn, "_is_safe_wrapper", False):

            def _make_safe_dialog(orig):
                def _safe_dialog(*args, **kwargs):
                    # If called as fn(parent, message, title="...")
                    if len(args) == 2 and "title" in kwargs and "message" not in kwargs:  # noqa: PLR2004
                        return orig(args[0], title=kwargs["title"], message=args[1])
                    return orig(*args, **kwargs)

                _safe_dialog._is_safe_wrapper = True
                return _safe_dialog

            setattr(_dialogs_mod, _fn_name, _make_safe_dialog(_orig_fn))
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

"""Synthetic Biology UI Daemon — hosts the module's own window in its own process.

Run by `karcytics_sdk.plugin.PluginUIDaemon` from this plugin's own `.venv`
interpreter (never imported into the Hub's process). Owns its own
`QApplication` and its own copies of numpy/scipy/PyQt6, so switching to or
from this module never touches the Hub's `sys.modules`.

Everything protocol-related (frame transport, the ready handshake, request
dispatch, noticing a native window close) lives in the SDK's
`karcytics_sdk.plugin.run_ui_daemon` and is identical for every isolated
plugin (see `karcytics_plugins.flow_cytometry.ui_daemon` for the sister
module this file is modeled on); this file only does what's genuinely
plugin-specific: sys.path setup and building this plugin's panel via its
own `initialize()`/`create_panel()` entry points.
"""

from __future__ import annotations

import faulthandler
import sys
import traceback
from pathlib import Path
from typing import Any

faulthandler.enable(file=sys.stderr, all_threads=True)


def global_exception_handler(exctype, value, tb):
    sys.stderr.write("CRITICAL ERROR CAUGHT BY QT HOOK:\n")
    traceback.print_exception(exctype, value, tb)
    sys.exit(1)


sys.excepthook = global_exception_handler


_GLOBAL_PANEL_ANCHOR = None

# Run directly as `python ui_daemon.py` by PluginUIDaemon rather than
# imported as part of the `karcytics_plugins` package — nothing else puts
# this plugin's own src/ on sys.path for a freestanding subprocess, so it
# has to do that for itself before it can import itself.
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# CRITICAL: must happen before run_ui_daemon() (below, via main()) is ever
# called — that starts the SDK's background stdin-reader thread
# (ui_daemon_runtime.run()'s _RequestReader), and importing numpy while
# another thread is blocked on a concurrent sys.stdin.buffer.read() call can
# deadlock on Windows (see karcytics_sdk.plugin.ui_daemon_runtime and
# karcytics_plugins.flow_cytometry.ui_daemon for the documented repro).
# Importing numpy/scipy here, before that thread exists, means any later
# import inside this plugin's own modules is just a sys.modules cache hit.
try:
    import numpy  # noqa: E402, F401
except ImportError:
    pass

try:
    import scipy  # noqa: E402, F401
except ImportError:
    pass

try:
    import matplotlib  # noqa: E402, F401
    import matplotlib.pyplot  # noqa: E402, F401
except ImportError:
    pass

try:
    import pyqtgraph  # noqa: E402, F401
except ImportError:
    pass

try:
    import tellurium  # noqa: E402, F401
except ImportError:
    pass

try:
    import msgpack  # type: ignore[import-untyped]  # noqa: E402, F401
except ImportError:
    pass


def _build_plugin_context() -> Any:
    from karcytics_sdk.plugin.context import PluginContext
    from karcytics_sdk.plugin.manifest import PluginManifest
    from karcytics_sdk.plugin.runtime_services import event_bus, task_scheduler

    manifest = PluginManifest(
        name="synthetic_biology",
        entry_point="karcytics_plugins.synthetic_biology:initialize",
        sdk_version="2.0",
        requires=["task_scheduler", "logger", "event_bus"],
    )
    services = {
        "task_scheduler": task_scheduler,
        "logger": __import__("logging").getLogger("plugin.synthetic_biology"),
        "event_bus": event_bus,
    }
    return PluginContext(services=services, manifest=manifest)


_ACTIVE_PLUGIN: Any = None
_ACTIVE_PANEL: Any = None


def main() -> int | None:
    import os

    import karcytics_sdk.plugin.ui_daemon_runtime as _ui_runtime
    from karcytics_sdk.plugin import run_ui_daemon
    from karcytics_sdk.plugin.ui_daemon_runtime import send_event

    if not os.environ.get("KARCYTICS_CORE_SERVICES_PORT") or not os.environ.get(
        "KARCYTICS_CORE_SERVICES_TOKEN"
    ):
        if hasattr(_ui_runtime, "_confirm_hub_theme_or_exit"):
            _orig_confirm_theme = _ui_runtime._confirm_hub_theme_or_exit

            def _safe_confirm_theme(logger: Any, plugin_id: str) -> None:
                port = os.environ.get("KARCYTICS_CORE_SERVICES_PORT")
                token = os.environ.get("KARCYTICS_CORE_SERVICES_TOKEN")
                if not port or not token:
                    logger.warning(
                        "CoreServices port/token not configured; using fallback dynamic theme colors."
                    )
                    return
                _orig_confirm_theme(logger, plugin_id)

            _ui_runtime._confirm_hub_theme_or_exit = _safe_confirm_theme

    def _build_panel() -> Any:
        global _ACTIVE_PLUGIN, _ACTIVE_PANEL, _GLOBAL_PANEL_ANCHOR
        from karcytics_sdk.plugin import get_logger
        from PyQt6.QtGui import QFont

        # Pre-register standard font family substitutions using valid CSS generic / cross-platform names
        QFont.insertSubstitutions("sans-serif", ["Segoe UI", "Helvetica Neue", "Arial"])
        QFont.insertSubstitutions("monospace", ["Menlo", "Monaco", "Consolas", "Courier New"])

        from karcytics_plugins.synthetic_biology import initialize

        logger = get_logger(__name__, "synthetic_biology")

        context = _build_plugin_context()
        logger.info("[phase1] _build_panel: initialize() -> SyntheticBiologyPlugin")
        _ACTIVE_PLUGIN = initialize(context)

        logger.info("[phase1] _build_panel: create_panel()")
        _ACTIVE_PANEL = _ACTIVE_PLUGIN.create_panel(parent=None)
        panel = _ACTIVE_PANEL
        _GLOBAL_PANEL_ANCHOR = panel
        logger.info("[phase1] _build_panel: panel constructed")

        if hasattr(panel, "state_changed"):
            panel.state_changed.connect(lambda: send_event("state_changed", {}))
        if hasattr(panel, "status_message"):
            panel.status_message.connect(lambda msg: send_event("status_message", msg))

        return panel

    def _on_panel_ready(window: Any, panel: Any) -> None:
        from karcytics_sdk.plugin.components import apply_global_sdk_styles
        from karcytics_sdk.plugin.theme_fallback import theme_manager

        def _on_theme_update():
            apply_global_sdk_styles()
            if hasattr(panel, "_apply_theme_styles"):
                panel._apply_theme_styles()

        theme_manager.theme_changed.connect(_on_theme_update)
        _on_theme_update()

    run_ui_daemon(
        _build_panel,
        window_title="Synthetic Biology",
        window_size=(1400, 900),
        on_panel_ready=_on_panel_ready,
        plugin_id="synthetic_biology",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

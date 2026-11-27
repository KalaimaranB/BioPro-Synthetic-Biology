"""Synthetic Biology UI Daemon — hosts the module's own window in its own process.

Run by `karcytics_sdk.plugin.PluginUIDaemon` from this plugin's own `.venv`
interpreter (never imported into the Hub's process). Owns its own
`QApplication` and its own copies of numpy/scipy/PySide6, so switching to or
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

faulthandler.enable(file=sys.stderr, all_threads=True)

import logging  # noqa: E402
import traceback  # noqa: E402


def global_exception_handler(exctype, value, tb):
    """Report a fatal unhandled exception to the log file as well as stderr.

    stderr alone is not enough. The host keeps only a short tail of it and
    surfaces that tail on a *startup* failure, so an exception that kills the
    daemon mid-session left the plugin log ending mid-sentence with no
    traceback anywhere a log reader would look. A crash from a tail box took
    an hour to find for exactly that reason, so the traceback now also goes
    through logging, which is already writing to
    ``~/.karcytics/logs/plugin_workers/synthetic_biology.log``.
    """
    print("CRITICAL ERROR CAUGHT BY QT HOOK:", file=sys.stderr)  # noqa: T201
    traceback.print_exception(exctype, value, tb)
    try:
        logging.getLogger(__name__).critical(
            "Unhandled exception; the plugin UI daemon is exiting.",
            exc_info=(exctype, value, tb),
        )
    except Exception:  # noqa: BLE001 - never let reporting mask the real fault
        pass
    sys.exit(1)


sys.excepthook = global_exception_handler


_GLOBAL_PANEL_ANCHOR = None


from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

# Run directly as `python ui_daemon.py` by PluginUIDaemon rather than
# imported as part of the `karcytics_plugins` package — nothing else puts
# this plugin's own src/ on sys.path for a freestanding subprocess, so it
# has to do that for itself before it can import itself.
_SRC_DIR = Path(__file__).resolve().parents[2]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# Dependency imports, all of them, before `run_ui_daemon()` is called.
#
# Two reasons they are here and in this order, and both have bitten:
#
# 1. numpy must be imported before run_ui_daemon() starts the SDK's background
#    stdin-reader thread (ui_daemon_runtime's _RequestReader): importing while
#    another thread is blocked on a concurrent sys.stdin.buffer.read() can
#    deadlock. `startup.EAGER_MODULES` has numpy first for that reason. Doing
#    this before the reader exists makes every later import a sys.modules hit.
#
#    This is also why none of it is moved to a thread to overlap with the
#    handshake, tempting as that is: tried, and it hung the worker. See
#    `startup`'s module docstring.
#
# 2. `PluginUIDaemon` allows 30 seconds for the ready frame, and all of this is
#    spent against it. A cold matplotlib font cache is ~12 s on its own, which
#    with uncompiled bytecode and macOS verifying each shared library on first
#    load is what pushed a real first launch past 30 s: "Virtual Environment
#    connection failed! Stderr: Matplotlib is building the font cache".
#
#    What keeps this inside budget is `analysis/daemon_worker.py`, which the
#    Hub runs after installing dependencies with a 120-second budget and does
#    exactly these imports. By the time this line runs on a real machine, the
#    font cache exists and the bytecode is compiled.
from karcytics_plugins.synthetic_biology.analysis.startup import (  # noqa: E402
    EAGER_MODULES,
    WARM_MODULES,
    warm_imports,
)

warm_imports(EAGER_MODULES + WARM_MODULES)


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
        from PySide6.QtGui import QFont

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

    run_ui_daemon(
        _build_panel,
        window_title="Synthetic Biology",
        window_size=(1400, 900),
        plugin_id="synthetic_biology",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

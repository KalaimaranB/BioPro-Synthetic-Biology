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

import sys
from pathlib import Path
from typing import Any

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
import numpy  # noqa: E402, F401
import scipy  # noqa: E402, F401


def _build_plugin_context() -> Any:
    from karcytics_sdk.plugin.context import PluginContext
    from karcytics_sdk.plugin.manifest import PluginManifest

    manifest = PluginManifest(
        name="synthetic_biology",
        entry_point="karcytics_plugins.synthetic_biology:initialize",
        sdk_version="2.0",
    )
    return PluginContext(services={}, manifest=manifest)


def main() -> None:
    from karcytics_sdk.plugin import run_ui_daemon
    from karcytics_sdk.plugin.ui_daemon_runtime import send_event

    def _build_panel() -> Any:
        from karcytics_sdk.plugin import get_logger

        from karcytics_plugins.synthetic_biology import initialize

        logger = get_logger(__name__, "synthetic_biology")

        context = _build_plugin_context()
        logger.info("[phase1] _build_panel: initialize() -> BioProPlugin")
        plugin = initialize(context)

        logger.info("[phase1] _build_panel: create_panel()")
        panel = plugin.create_panel(parent=None)
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


if __name__ == "__main__":
    main()

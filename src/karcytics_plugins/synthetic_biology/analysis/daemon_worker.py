"""Headless worker that proves this plugin's venv works, and warms it.

The Hub looks for this exact path after installing a plugin's dependencies::

    <plugin>/src/karcytics_plugins/<plugin_id>/analysis/daemon_worker.py

and, when it exists, starts it over the real worker protocol and sends it a
``ping`` (``karcytics.core.package_manager._run_isolated_daemon_selftest``).
Until this file existed the Hub logged "No self-test script found ... skipping
self-test" and declared the install complete, so an install was reported as
successful without the venv ever having been started once.

That gap is what made a real onboarding failure so hard to read. The install
said it had worked; the first launch of the UI daemon then died on a 30-second
ready-handshake timeout, with matplotlib's "building the font cache" line as
the only hint, because the cold font-cache build alone is ~12 s of it. See
``analysis/startup.py`` for the measurements.

So this script does two jobs:

* **Verification.** It speaks the protocol the plugin uses at runtime, from the
  plugin's own interpreter, so a broken interpreter or a dependency that
  installed but cannot import fails at install time with a clear message
  instead of at first launch with a timeout.
* **Warming.** It imports the heavy dependencies before answering ready. The
  Hub allows 120 s here against the UI daemon's 30 s, and tells the user it
  "may take a minute on first install" — which is the right place to spend the
  font-cache build and the first bytecode compile of eighteen packages.

Protocol, as ``karcytics_sdk.plugin.daemon.PluginDaemon`` speaks it: frames are
a four-byte big-endian length followed by a msgpack map, over stdin/stdout. The
first frame out must be ``{"status": "ready"}``; a request is
``{"method": ..., "kwargs": ...}``; ``ping`` must answer ``{"status": "pong"}``.

Headless on purpose: no Qt, no QApplication, no window. Only
``ui_daemon.py`` builds UI.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path
from typing import Any

# Run directly as `python daemon_worker.py` from the plugin's venv, not
# imported as part of the package, so nothing else has put this plugin's src/
# on sys.path. Same reasoning as ui_daemon.py.
_SRC_DIR = Path(__file__).resolve().parents[3]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from karcytics_plugins.synthetic_biology.analysis.startup import (  # noqa: E402
    EAGER_MODULES,
    WARM_MODULES,
    missing_required,
    warm_imports,
)

#: Length prefix format, as PluginDaemon packs and unpacks it.
_HEADER = ">I"
_HEADER_BYTES = 4


def _send(frame: dict[str, Any]) -> None:
    import msgpack  # type: ignore[import-untyped]

    payload = msgpack.packb(frame, use_bin_type=True)
    sys.stdout.buffer.write(struct.pack(_HEADER, len(payload)) + payload)
    sys.stdout.buffer.flush()


def _read_exact(count: int) -> bytes | None:
    """Read exactly `count` bytes, or None if the stream closed first."""
    buf = bytearray()
    while len(buf) < count:
        chunk = sys.stdin.buffer.read(count - len(buf))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def _receive() -> dict[str, Any] | None:
    import msgpack  # type: ignore[import-untyped]

    header = _read_exact(_HEADER_BYTES)
    if header is None:
        return None
    payload = _read_exact(struct.unpack(_HEADER, header)[0])
    if payload is None:
        return None
    frame = msgpack.unpackb(payload, raw=False)
    return frame if isinstance(frame, dict) else None


def _handle(method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
    if method == "ping":
        # The Hub's self-test asserts status == "pong" and fails the install on
        # anything else, so this is the one moment a missing dependency can be
        # reported to someone able to fix it. Answering "pong" while numpy is
        # absent would install a module that opens and then dies at the first
        # analysis.
        if _MISSING:
            return {
                "error": (
                    "this plugin's virtual environment is incomplete: "
                    + ", ".join(_MISSING)
                    + f" could not be imported by {sys.executable}"
                ),
                "missing": list(_MISSING),
            }
        # The extra fields are for the install log: which interpreter ran, and
        # what it managed to warm.
        return {
            "status": "pong",
            "python": sys.version.split()[0],
            "executable": sys.executable,
            "warmed": list(_WARMED),
        }
    if method == "shutdown":
        return {"status": "ok"}
    return {"error": f"unknown method: {method!r}", "kwargs": sorted(kwargs)}


_WARMED: list[str] = []
_MISSING: list[str] = []


def main() -> int:
    global _WARMED, _MISSING

    # Everything expensive, on this one thread, before ready is sent. Here that
    # is the right order round: the Hub is waiting with a 120 s budget and has
    # told the user to expect a minute, so this is where a cold font cache and
    # a first bytecode compile should be paid -- once, at install, rather than
    # on every launch against a 30 s limit.
    _WARMED = warm_imports(EAGER_MODULES + WARM_MODULES)

    # Checked after warming, so it reports what is genuinely absent rather than
    # what simply had not been imported yet. Reported through ping rather than
    # by refusing to send ready: a worker that never answers fails the
    # self-test with a timeout, and a timeout says nothing about the cause.
    _MISSING = missing_required()

    _send({"status": "ready"})

    while True:
        frame = _receive()
        if frame is None:
            return 0
        method = str(frame.get("method", ""))
        kwargs = frame.get("kwargs") or {}
        try:
            response = _handle(method, kwargs if isinstance(kwargs, dict) else {})
        except Exception as exc:  # noqa: BLE001 - a bad request must not kill the worker
            response = {"error": f"{type(exc).__name__}: {exc}"}
        _send(response)
        if method == "shutdown":
            return 0


if __name__ == "__main__":
    sys.exit(main())

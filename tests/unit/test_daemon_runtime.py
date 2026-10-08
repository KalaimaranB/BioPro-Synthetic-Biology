"""Unit tests for RequestDispatcher error resilience.

These test the dispatcher in isolation (no subprocess, no Qt). The real
regression test for the `import time` scoping bug lives in
test_daemon_integration.py (TestDaemonRegressionImportTime), which proves it
by spawning the actual worker process and observing the NameError on stderr.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any


def _import_runtime():
    """Import ui_daemon_runtime from the real SDK source, bypassing conftest mocks."""
    saved = {}
    keys_to_restore = [k for k in sys.modules if k.startswith("karcytics_sdk")]
    for k in keys_to_restore:
        saved[k] = sys.modules.pop(k)
    try:
        mod = importlib.import_module("karcytics_sdk.plugin.ui_daemon_runtime")
        return mod
    finally:
        for k, v in saved.items():
            sys.modules[k] = v


_rt = _import_runtime()
RequestDispatcher = _rt.RequestDispatcher


class TestRequestDispatcher:
    """Unit tests for RequestDispatcher error resilience."""

    def test_unknown_method_returns_error(self):
        """Dispatching an unregistered method returns an error dict, not an exception."""
        d = RequestDispatcher()
        result = d.dispatch({"method": "nonexistent", "kwargs": {}})
        assert isinstance(result, dict)
        assert "error" in result
        assert "nonexistent" in result["error"]

    def test_handler_exception_returns_error_dict(self):
        """When a registered handler raises, dispatch catches it and returns a
        structured error dict.
        """
        d = RequestDispatcher()

        def _boom(_kwargs: dict[str, Any]) -> dict[str, Any]:
            msg = "kaboom"
            raise RuntimeError(msg)

        d.register("explode", _boom)
        result = d.dispatch({"method": "explode", "kwargs": {}})
        assert isinstance(result, dict)
        assert "error" in result
        assert "kaboom" in result["error"]

    def test_handler_success_returns_result(self):
        """A well-behaved handler's return value passes through unchanged."""
        d = RequestDispatcher()
        d.register("ping", lambda _kw: {"status": "pong"})
        result = d.dispatch({"method": "ping", "kwargs": {}})
        assert result == {"status": "pong"}

    def test_worker_survives_multiple_errors(self):
        """Dispatching several failing requests in a row doesn't break later calls."""
        d = RequestDispatcher()

        def _fail(_kw: dict[str, Any]) -> dict[str, Any]:
            msg = "boom"
            raise ValueError(msg)

        d.register("fail", _fail)
        d.register("ok", lambda _kw: {"status": "ok"})

        for _ in range(5):
            r = d.dispatch({"method": "fail", "kwargs": {}})
            assert "error" in r

        assert d.dispatch({"method": "ok", "kwargs": {}}) == {"status": "ok"}

    def test_error_response_contains_traceback(self):
        """The error dict includes a traceback string so the Hub can log it."""
        d = RequestDispatcher()

        def _raise_with_context(_kw: dict[str, Any]) -> None:
            msg = "unique-sentinel-string"
            raise RuntimeError(msg)

        d.register("ctx", _raise_with_context)
        result = d.dispatch({"method": "ctx", "kwargs": {}})
        assert "unique-sentinel-string" in result["error"]
        assert "RuntimeError" in result["error"]

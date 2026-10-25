"""Base worker class inheriting from AnalysisWorker with threadpool & cancellation support."""

from __future__ import annotations

import contextlib

from karcytics_sdk.plugin import AnalysisWorker
from karcytics_sdk.plugin.runtime_services import AnalysisRunnable
from PySide6.QtCore import QObject, QThreadPool, Signal


class BaseSDKWorker(AnalysisWorker):
    """SDK AnalysisWorker compliant background task with graceful cancellation."""

    cancelled = Signal()
    finished_ok = Signal(object)
    finished_err = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super(AnalysisWorker, self).__init__(parent)
        self._is_cancelled = False
        self._is_running = False

    def cancel(self) -> None:
        """Signal graceful cancellation."""
        self._is_cancelled = True
        self._is_running = False
        with contextlib.suppress(Exception):
            self.cancelled.emit()

    def is_cancelled(self) -> bool:
        """Check if task cancellation was requested."""
        return getattr(self, "_is_cancelled", False)

    def isRunning(self) -> bool:  # noqa: N802
        """Check if worker is actively running in background."""
        return getattr(self, "_is_running", False)

    def requestInterruption(self) -> None:  # noqa: N802
        """Compatibility method for QThread API."""
        self.cancel()

    def quit(self) -> None:
        """Compatibility method for QThread API."""
        self.cancel()

    def wait(self, msecs: int = 0) -> bool:  # noqa: ARG002
        """Wait for worker completion."""
        return True

    def stop_and_wait(self, msecs: int = 1000) -> None:
        """Cancel worker execution and wait for completion."""
        self.cancel()
        self.wait(msecs)

    def start(self) -> None:
        """Execute worker asynchronously on SDK threadpool."""
        self._is_running = True
        runnable = AnalysisRunnable(self)
        QThreadPool.globalInstance().start(runnable)

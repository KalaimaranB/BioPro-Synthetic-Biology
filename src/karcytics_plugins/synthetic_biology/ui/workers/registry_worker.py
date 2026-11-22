"""Asynchronous worker for part lookups against remote registries.

``IGemClient.fetch_part`` is a blocking HTTP call with a 10 s timeout. Run from
a slot it freezes the whole application for as long as the registry takes to
answer, which on a teaching network is routinely the full timeout.
"""

from __future__ import annotations

from typing import Any

from karcytics_sdk.plugin import OneShotWorkerThread
from PySide6.QtCore import Signal


class RegistryFetchWorker(OneShotWorkerThread):
    """Granular QThread worker dedicated strictly to remote part retrieval."""

    # `object` rather than BiologicalPart: a miss is a legitimate result and
    # has to travel as None, which a typed signal would coerce.
    part_fetched = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, client: Any, part_id: str, parent: Any = None):
        # Production callers always pass a parent (it anchors the thread's
        # lifetime); None is only for tests that call run() synchronously.
        super().__init__(parent)  # type: ignore[arg-type]
        self.finished_err.connect(self.error_occurred)
        self.client = client
        self.part_id = part_id

    def _execute(self) -> None:
        """Executes the blocking registry lookup off the GUI thread."""
        self.part_fetched.emit(self.client.fetch_part(self.part_id))

"""Controller managing CRISPR Design View interactions, workers, and SynBioState."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from ...analysis.citations import crispr_step
from ...analysis.models.domain import gRNACandidate
from ...analysis.state import SynBioState
from ..workers import CRISPRWorker


class CRISPRDesignController(QObject):
    """Explicit Controller handling gRNA target discovery and the module's
    rule-based on- and off-target scoring (not the published CFD matrix).
    """

    grna_results_ready = Signal(list)  # Emits List[gRNACandidate]
    error_raised = Signal(str)

    def __init__(self, state: SynBioState, parent=None):
        super().__init__(parent)
        self.state = state
        self._active_worker: CRISPRWorker | None = None
        # (pam_type, spacer_length, target_length) of the scan in flight.
        self._pending_scan: tuple[str, int, int] | None = None

    @Slot(str, str, int)
    def handle_scan_request(
        self,
        target_sequence: str,
        pam_type: str = "SpCas9 (NGG)",
        spacer_length: int = 20,
    ) -> None:
        """Launches background CRISPR scanning worker."""
        self._pending_scan = (pam_type, spacer_length, len(target_sequence or ""))
        self._active_worker = CRISPRWorker(
            target_sequence=target_sequence,
            pam_type=pam_type,
            spacer_length=spacer_length,
            parent=self,
        )
        self._active_worker.scan_finished.connect(self._on_scan_finished)
        self._active_worker.error_occurred.connect(self.error_raised.emit)
        self._active_worker.start()

    def _on_scan_finished(self, candidates: list[gRNACandidate]) -> None:
        """Updates SynBioState and notifies View with results."""
        self.state.set_grna_candidates(candidates)
        if self._pending_scan is not None:
            pam_type, spacer_length, target_length = self._pending_scan
            self._pending_scan = None
            self.state.record_method(
                crispr_step(pam_type, spacer_length, target_length, len(candidates))
            )
        self.grna_results_ready.emit(candidates)

    def teardown(self) -> None:
        """Stops active background worker thread if running."""
        if self._active_worker is not None:
            self._active_worker.stop_and_wait(1000)
            self._active_worker = None

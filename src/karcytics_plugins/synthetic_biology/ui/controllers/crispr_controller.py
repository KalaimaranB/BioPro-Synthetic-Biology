"""Controller managing CRISPR Design View interactions, workers, and SynBioState."""

from __future__ import annotations

from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from analysis.crispr.async_worker import CRISPRWorker
from analysis.models.domain import gRNACandidate
from analysis.state import SynBioState


class CRISPRDesignController(QObject):
    """Explicit Controller handling gRNA target discovery and CFD off-target
    calculations.
    """

    grna_results_ready = pyqtSignal(list)  # Emits List[gRNACandidate]
    error_raised = pyqtSignal(str)

    def __init__(self, state: SynBioState, parent=None):
        super().__init__(parent)
        self.state = state
        self._active_worker: Optional[CRISPRWorker] = None

    @pyqtSlot(str, str, int)
    def handle_scan_request(
        self,
        target_sequence: str,
        pam_type: str = "SpCas9 (NGG)",
        spacer_length: int = 20,
    ) -> None:
        """Launches background CRISPR scanning worker."""
        self._active_worker = CRISPRWorker(
            target_sequence=target_sequence,
            pam_type=pam_type,
            spacer_length=spacer_length,
        )
        self._active_worker.scan_finished.connect(self._on_scan_finished)
        self._active_worker.error_occurred.connect(self.error_raised.emit)
        self._active_worker.start()

    def _on_scan_finished(self, candidates: List[gRNACandidate]) -> None:
        """Updates SynBioState and notifies View with results."""
        self.state.set_grna_candidates(candidates)
        self.grna_results_ready.emit(candidates)

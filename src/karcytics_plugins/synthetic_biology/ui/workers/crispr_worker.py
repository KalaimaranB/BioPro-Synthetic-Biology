"""Asynchronous worker for CRISPR/Cas9 target scanning and off-target scoring."""

from __future__ import annotations

from karcytics_sdk.plugin import OneShotWorkerThread
from PySide6.QtCore import Signal

from ...analysis.crispr.grna_designer import CRISPRDesignEngine
from ...analysis.models.domain import gRNACandidate


class CRISPRWorker(OneShotWorkerThread):
    """Granular QThread worker dedicated strictly to CRISPR gRNA candidate
    discovery and CFD scoring.
    """

    scan_finished = Signal(list)  # Emits List[gRNACandidate]
    error_occurred = Signal(str)

    def __init__(
        self,
        target_sequence: str,
        pam_type: str = "SpCas9 (NGG)",
        spacer_length: int = 20,
        parent=None,
    ):
        # Production callers always pass a parent (it anchors the thread's
        # lifetime); None is only for tests that call run() synchronously.
        super().__init__(parent)  # type: ignore[arg-type]
        self.finished_err.connect(self.error_occurred)
        self.target_sequence = target_sequence
        self.pam_type = pam_type
        self.spacer_length = spacer_length

    def _execute(self) -> None:
        """Executes non-blocking PAM scan and CFD off-target calculation."""
        candidates: list[gRNACandidate] = CRISPRDesignEngine.find_grna_candidates(
            target_sequence=self.target_sequence,
            pam_type=self.pam_type,
            spacer_length=self.spacer_length,
        )
        self.scan_finished.emit(candidates)

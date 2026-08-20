"""Asynchronous worker for CRISPR/Cas9 target scanning and off-target scoring."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal  # noqa: TID251

from ..models.domain import gRNACandidate
from .grna_designer import CRISPRDesignEngine


class CRISPRWorker(QThread):
    """Granular QThread worker dedicated strictly to CRISPR gRNA candidate
    discovery and CFD scoring.
    """

    scan_finished = pyqtSignal(list)  # Emits List[gRNACandidate]
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        target_sequence: str,
        pam_type: str = "SpCas9 (NGG)",
        spacer_length: int = 20,
        parent=None,
    ):
        super().__init__(parent)
        self.target_sequence = target_sequence
        self.pam_type = pam_type
        self.spacer_length = spacer_length

    def run(self) -> None:
        """Executes non-blocking PAM scan and CFD off-target calculation."""
        try:
            candidates: list[gRNACandidate] = CRISPRDesignEngine.find_grna_candidates(
                target_sequence=self.target_sequence,
                pam_type=self.pam_type,
                spacer_length=self.spacer_length,
            )
            self.scan_finished.emit(candidates)
        except Exception as e:
            self.error_occurred.emit(str(e))

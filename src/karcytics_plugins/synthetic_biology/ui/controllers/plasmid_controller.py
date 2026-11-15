"""Controller managing Plasmid Assembly View interactions, workers, and SynBioState."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from ...analysis.citations import (
    amplification_step,
    assembly_step,
    digest_step,
    gel_step,
    primer_screen_step,
    primer_step,
)
from ...analysis.models.domain import PlasmidVector
from ...analysis.parts.base import BiologicalPart
from ...analysis.state import SynBioState
from ..workers import AssemblyWorker


class PlasmidAssemblyController(QObject):
    """Explicit Controller handling Vector Assembly, sequence file parsing,
    and primer design.
    """

    assembly_ready = Signal(PlasmidVector)
    error_raised = Signal(str)

    def __init__(self, state: SynBioState, parent=None):
        super().__init__(parent)
        self.state = state
        self._active_worker: AssemblyWorker | None = None

    @Slot(str, list)
    def handle_assemble_request(self, vector_name: str, parts: list[BiologicalPart]) -> None:
        """Launches background vector assembly worker."""
        self._active_worker = AssemblyWorker(
            task_type="assemble",
            vector_name=vector_name,
            parts=parts,
            parent=self,
        )
        self._active_worker.assembly_finished.connect(self._on_assembly_finished)
        self._active_worker.error_occurred.connect(self.error_raised.emit)
        self._active_worker.start()

    @Slot(str, str)
    def handle_file_parse_request(self, file_content: str, file_format: str) -> None:
        """Launches background Biopython sequence parsing worker."""
        self._active_worker = AssemblyWorker(
            task_type="parse",
            file_content=file_content,
            file_format=file_format,
            parent=self,
        )
        # Its own handler: an imported file was not assembled here, so it must
        # not be written up as an in-silico assembly.
        self._active_worker.assembly_finished.connect(self._on_parse_finished)
        self._active_worker.error_occurred.connect(self.error_raised.emit)
        self._active_worker.start()

    def _on_parse_finished(self, vector: PlasmidVector) -> None:
        """State update for a vector imported from a sequence file."""
        self.state.set_active_plasmid(vector)
        self.assembly_ready.emit(vector)

    def _on_assembly_finished(self, vector: PlasmidVector) -> None:
        """Centralized state update upon vector assembly completion."""
        self.state.set_active_plasmid(vector)
        self.state.record_method(
            assembly_step(
                vector.name, len(vector.sequence), len(vector.features), vector.is_circular
            )
        )
        self.assembly_ready.emit(vector)

    # ── Methods & References ───────────────────────────────────────────
    #
    # These four step builders existed with zero callers: a student could run
    # the entire primer workflow and the Methods dialog would show nothing
    # about any of it, so every Crossref-verified citation behind the numbers
    # was invisible in the exported write-up. Recording lives here rather than
    # in the dialog so there is exactly one path, and so it is testable
    # without a view.

    def record_primer_design(
        self, candidate: dict[str, Any], rubric: Any, n_candidates: int
    ) -> None:
        """Record the design and the screening that chose this candidate."""
        fwd, rev = candidate["forward"], candidate["reverse"]
        self.state.record_method(primer_step(fwd.target_tm, fwd.calculated_tm, rev.calculated_tm))
        summary = candidate.get("summary") or {}
        self.state.record_method(
            primer_screen_step(
                rubric=rubric,
                n_candidates=n_candidates,
                verdict=str(summary.get("verdict", "")),
                checks_applied=[c["name"] for c in candidate.get("checks", [])],
            )
        )

    def record_amplification(self, result: Any) -> None:
        self.state.record_method(amplification_step(result))

    def record_digest(self, digest: Any) -> None:
        self.state.record_method(digest_step(digest))

    def record_gel(self, gel: Any) -> None:
        self.state.record_method(gel_step(gel))

    def teardown(self) -> None:
        """Stops active background worker thread if running."""
        if self._active_worker is not None:
            self._active_worker.stop_and_wait(1000)
            self._active_worker = None

"""Controller managing Plasmid Assembly View interactions, workers, and SynBioState."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from ...analysis.assembly.vector_builder import VectorAssemblyEngine
from ...analysis.models.domain import PlasmidVector, Primer
from ...analysis.parts.base import BiologicalPart
from ...analysis.state import SynBioState
from ..workers import AssemblyWorker


class PlasmidAssemblyController(QObject):
    """Explicit Controller handling Vector Assembly, sequence file parsing,
    and primer design.
    """

    assembly_ready = Signal(PlasmidVector)
    primers_ready = Signal(Primer, Primer)
    error_raised = Signal(str)

    def __init__(self, state: SynBioState, parent=None):
        super().__init__(parent)
        self.state = state
        self._active_worker: AssemblyWorker | None = None

    def handle_primer_design(
        self,
        sequence: str = "",
        target_tm: float = 60.0,
        fwd_overhang: str = "",
        rev_overhang: str = "",
        target_seq: str = "",
    ) -> list[Primer]:
        """Calculates PCR primers synchronously via VectorAssemblyEngine and updates state."""
        seq = sequence or target_seq
        if not seq:
            return []
        fwd, rev = VectorAssemblyEngine.design_primers(
            target_sequence=seq,
            target_tm=target_tm,
            fwd_overhang=fwd_overhang,
            rev_overhang=rev_overhang,
        )
        plasmid = self.state.get_active_plasmid()
        if plasmid:
            plasmid.primers.extend([fwd, rev])
            self.state.set_active_plasmid(plasmid)
        self.primers_ready.emit(fwd, rev)
        return [fwd, rev]

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
        self._active_worker.assembly_finished.connect(self._on_assembly_finished)
        self._active_worker.error_occurred.connect(self.error_raised.emit)
        self._active_worker.start()

    @Slot(str, float, str, str)
    def handle_primer_design_request(
        self,
        target_seq: str,
        target_tm: float = 60.0,
        fwd_overhang: str = "",
        rev_overhang: str = "",
    ) -> None:
        """Launches background primer design worker."""
        self._active_worker = AssemblyWorker(
            task_type="primer",
            target_seq=target_seq,
            target_tm=target_tm,
            fwd_overhang=fwd_overhang,
            rev_overhang=rev_overhang,
            parent=self,
        )
        self._active_worker.primer_finished.connect(self._on_primer_finished)
        self._active_worker.error_occurred.connect(self.error_raised.emit)
        self._active_worker.start()

    def _on_assembly_finished(self, vector: PlasmidVector) -> None:
        """Centralized state update upon vector assembly completion."""
        self.state.set_active_plasmid(vector)
        self.assembly_ready.emit(vector)

    def _on_primer_finished(self, fwd: Primer, rev: Primer) -> None:
        """Updates active plasmid primers in state."""
        plasmid = self.state.get_active_plasmid()
        if plasmid:
            plasmid.primers.extend([fwd, rev])
            self.state.set_active_plasmid(plasmid)
        self.primers_ready.emit(fwd, rev)

    def teardown(self) -> None:
        """Stops active background worker thread if running."""
        if self._active_worker is not None:
            self._active_worker.stop_and_wait(1000)
            self._active_worker = None

"""Asynchronous worker for Plasmid Vector assembly and sequence parsing."""

from __future__ import annotations

from karcytics_sdk.plugin import OneShotWorkerThread
from PySide6.QtCore import Signal

from ...analysis.assembly.vector_builder import VectorAssemblyEngine
from ...analysis.models.domain import PlasmidVector, Primer
from ...analysis.parts.base import BiologicalPart


class AssemblyWorker(OneShotWorkerThread):
    """Granular QThread worker dedicated strictly to Vector Assembly
    and Primer Design tasks.
    """

    assembly_finished = Signal(PlasmidVector)
    primer_finished = Signal(Primer, Primer)
    error_occurred = Signal(str)

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        task_type: str,  # 'assemble', 'parse', 'primer'
        vector_name: str = "Construct",
        parts: list[BiologicalPart] | None = None,
        file_content: str = "",
        file_format: str = "genbank",
        target_seq: str = "",
        target_tm: float = 60.0,
        fwd_overhang: str = "",
        rev_overhang: str = "",
        parent=None,
    ):
        # Production callers always pass a parent (it anchors the thread's
        # lifetime); None is only for tests that call run() synchronously.
        super().__init__(parent)  # type: ignore[arg-type]
        self.finished_err.connect(self.error_occurred)
        self.task_type = task_type
        self.vector_name = vector_name
        self.parts = parts or []
        self.file_content = file_content
        self.file_format = file_format
        self.target_seq = target_seq
        self.target_tm = target_tm
        self.fwd_overhang = fwd_overhang
        self.rev_overhang = rev_overhang

    def _execute(self) -> None:
        """Executes non-blocking background computation."""
        if self.task_type == "assemble":
            vector = VectorAssemblyEngine.assemble_vector(
                vector_name=self.vector_name,
                parts=self.parts,
            )
            self.assembly_finished.emit(vector)
        elif self.task_type == "parse":
            vector = VectorAssemblyEngine.parse_sequence_file(
                file_content=self.file_content,
                file_format=self.file_format,
            )
            self.assembly_finished.emit(vector)
        elif self.task_type == "primer":
            fwd, rev = VectorAssemblyEngine.design_primers(
                target_sequence=self.target_seq,
                target_tm=self.target_tm,
                fwd_overhang=self.fwd_overhang,
                rev_overhang=self.rev_overhang,
            )
            self.primer_finished.emit(fwd, rev)
        else:
            raise ValueError(f"Unknown task type: {self.task_type}")

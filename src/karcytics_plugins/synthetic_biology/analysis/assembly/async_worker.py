"""Asynchronous worker for Plasmid Vector assembly and sequence parsing."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal  # noqa: TID251

from ..models.domain import PlasmidVector, Primer
from ..parts.base import BiologicalPart
from .vector_builder import VectorAssemblyEngine


class AssemblyWorker(QThread):
    """Granular QThread worker dedicated strictly to Vector Assembly
    and Primer Design tasks.
    """

    assembly_finished = pyqtSignal(PlasmidVector)
    primer_finished = pyqtSignal(Primer, Primer)
    error_occurred = pyqtSignal(str)

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
        super().__init__(parent)
        self.task_type = task_type
        self.vector_name = vector_name
        self.parts = parts or []
        self.file_content = file_content
        self.file_format = file_format
        self.target_seq = target_seq
        self.target_tm = target_tm
        self.fwd_overhang = fwd_overhang
        self.rev_overhang = rev_overhang

    def run(self) -> None:
        """Executes non-blocking background computation."""
        try:
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
                self.error_occurred.emit(f"Unknown task type: {self.task_type}")
        except Exception as e:
            self.error_occurred.emit(str(e))

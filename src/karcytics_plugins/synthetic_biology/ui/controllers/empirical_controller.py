"""Controller managing empirical data workflows and state synchronization."""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from ...analysis.empirical.fcs_ingestion import (
    FCSDataIngestionService,
    FCSEventData,
)
from ...analysis.empirical.ml_optimizer import (
    CircuitMLOptimizationEngine,
    HillOptimizationResult,
)
from ...analysis.empirical.ngs_alignment import (
    NGSAlignmentResult,
    NGSAlignmentService,
)
from ...analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
    PlasmidVector,
)
from ...analysis.state import SynBioState


class EmpiricalWorker(QThread):
    """Background worker for NGS alignment and ML parameter fitting."""

    fcs_done = pyqtSignal(FCSEventData)
    ngs_done = pyqtSignal(NGSAlignmentResult)
    opt_done = pyqtSignal(HillOptimizationResult)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        task_type: str,
        fcs_service: Optional[FCSDataIngestionService] = None,
        fcs_path: str = "",
        ngs_path: str = "",
        plasmid: Optional[PlasmidVector] = None,
        components: Optional[List[CircuitComponent]] = None,
        edges: Optional[List[CircuitEdge]] = None,
        fcs_data: Optional[FCSEventData] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.task_type = task_type
        self.fcs_service = fcs_service or FCSDataIngestionService()
        self.fcs_path = fcs_path
        self.ngs_path = ngs_path
        self.plasmid = plasmid
        self.components = components or []
        self.edges = edges or []
        self.fcs_data = fcs_data

    def run(self):
        try:
            if self.task_type == "fcs":
                res = self.fcs_service.ingest_fcs_file(self.fcs_path)
                self.fcs_done.emit(res)
            elif self.task_type == "ngs":
                ref = self.plasmid or PlasmidVector(
                    id="pDEFAULT", name="Reference Construct", sequence="ATGC" * 50
                )
                res = NGSAlignmentService.align_ngs_reads(self.ngs_path, ref)
                self.ngs_done.emit(res)
            elif self.task_type == "opt":
                fcs = self.fcs_data or self.fcs_service.ingest_fcs_file("dummy.fcs")
                res = CircuitMLOptimizationEngine.fit_kinetic_parameters(
                    components=self.components,
                    edges=self.edges,
                    fcs_data=fcs,
                )
                self.opt_done.emit(res)
        except Exception as ex:
            self.error_occurred.emit(str(ex))


class EmpiricalAnalyticsController(QObject):
    """Controller for FCS ingestion, NGS alignment, and ML parameter fitting."""

    fcs_loaded = pyqtSignal(FCSEventData)
    ngs_aligned = pyqtSignal(NGSAlignmentResult)
    optimization_finished = pyqtSignal(HillOptimizationResult)
    error_raised = pyqtSignal(str)

    def __init__(self, state: SynBioState, parent=None):
        super().__init__(parent)
        self.state = state
        self.fcs_service = FCSDataIngestionService()
        self._active_workers: List[EmpiricalWorker] = []

    def load_fcs_data(self, file_path: str) -> None:
        """Launch asynchronous FCS data ingestion."""
        worker = EmpiricalWorker(
            task_type="fcs",
            fcs_service=self.fcs_service,
            fcs_path=file_path,
            parent=self,
        )
        worker.fcs_done.connect(self.fcs_loaded.emit)
        worker.error_occurred.connect(self.error_raised.emit)
        worker.finished.connect(lambda: self._remove_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def run_ngs_alignment(
        self, ngs_path: str, plasmid: Optional[PlasmidVector] = None
    ) -> None:
        """Launch background NGS alignment task."""
        ref_plasmid = plasmid or self.state.plasmid
        worker = EmpiricalWorker(
            task_type="ngs",
            ngs_path=ngs_path,
            plasmid=ref_plasmid,
            parent=self,
        )
        worker.ngs_done.connect(self.ngs_aligned.emit)
        worker.error_occurred.connect(self.error_raised.emit)
        worker.finished.connect(lambda: self._remove_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def run_ml_optimization(
        self,
        components: List[CircuitComponent],
        edges: List[CircuitEdge],
        fcs_data: Optional[FCSEventData] = None,
    ) -> None:
        """Launch background Hill parameter optimization task."""
        comps = components or self.state.circuit_components
        edgs = edges or self.state.circuit_edges
        worker = EmpiricalWorker(
            task_type="opt",
            components=comps,
            edges=edgs,
            fcs_data=fcs_data,
            parent=self,
        )
        worker.opt_done.connect(self.optimization_finished.emit)
        worker.error_occurred.connect(self.error_raised.emit)
        worker.finished.connect(lambda: self._remove_worker(worker))
        self._active_workers.append(worker)
        worker.start()

    def _remove_worker(self, worker: EmpiricalWorker) -> None:
        if worker in self._active_workers:
            self._active_workers.remove(worker)
            worker.deleteLater()

    def teardown(self) -> None:
        """Strict memory safety cleanup for plugin hot-swapping.

        Disconnects signals, terminates active background threads, and releases
        underlying C++ worker objects using deleteLater().
        """
        for worker in list(self._active_workers):
            try:
                worker.fcs_done.disconnect()
                worker.ngs_done.disconnect()
                worker.opt_done.disconnect()
                worker.error_occurred.disconnect()
            except Exception:
                pass

            if worker.isRunning():
                worker.requestInterruption()
                worker.quit()
                worker.wait(1000)
            worker.deleteLater()
        self._active_workers.clear()

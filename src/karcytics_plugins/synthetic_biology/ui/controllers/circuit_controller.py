"""Controller managing Circuit Simulation View interactions, SciPy solver
workers, and SynBioState.
"""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from ...analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
    SimulationResult,
)
from ...analysis.simulation.async_worker import CircuitSimWorker
from ...analysis.state import SynBioState


class CircuitSimulationController(QObject):
    """Explicit Controller handling NetworkX circuit topology ODE compilation
    and SciPy integration.
    """

    simulation_ready = pyqtSignal(SimulationResult)
    error_raised = pyqtSignal(str)

    def __init__(self, state: SynBioState, parent=None):
        super().__init__(parent)
        self.state = state
        self._active_worker: Optional[CircuitSimWorker] = None

    @pyqtSlot(list, list, object)
    def handle_simulation_request(
        self,
        components: List[CircuitComponent],
        edges: List[CircuitEdge],
        params: Optional[SimulationParameters] = None,
    ) -> None:
        """Launches non-blocking background ODE simulation worker."""
        self._active_worker = CircuitSimWorker(
            components=components,
            edges=edges,
            params=params,
        )
        self._active_worker.simulation_finished.connect(self._on_simulation_finished)
        self._active_worker.error_occurred.connect(self.error_raised.emit)
        self._active_worker.start()

    def _on_simulation_finished(self, result: SimulationResult) -> None:
        """Updates SynBioState and notifies View with time-series result."""
        self.state.set_simulation_result(result)
        self.simulation_ready.emit(result)

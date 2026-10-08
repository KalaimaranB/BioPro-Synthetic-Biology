"""Controller managing Circuit Simulation View interactions, SciPy solver
workers, and SynBioState.
"""

from __future__ import annotations

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
        self._active_worker: CircuitSimWorker | None = None

    @pyqtSlot(list, list, object)
    def handle_simulation_request(
        self,
        components: list[CircuitComponent],
        edges: list[CircuitEdge],
        params: SimulationParameters | None = None,
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

    def _on_simulation_finished(self, result_or_bytes: object) -> None:
        """Updates SynBioState and notifies View with time-series result."""
        if isinstance(result_or_bytes, bytes):
            import msgpack  # type: ignore[import-untyped]
            import numpy as np

            unpacked = msgpack.unpackb(result_or_bytes, raw=False)
            t_bytes = unpacked.get("time_bytes", b"")
            t_arr = np.frombuffer(t_bytes, dtype=np.float64).tolist()
            species_dict = {}
            for k, v in unpacked.get("species_bytes", {}).items():
                species_dict[k] = np.frombuffer(v, dtype=np.float64).tolist()
            result = SimulationResult(
                time_points=t_arr,
                species_concentrations=species_dict,
            )
        else:
            result = result_or_bytes  # type: ignore

        self.state.set_simulation_result(result)
        self.simulation_ready.emit(result)

    def teardown(self) -> None:
        """Stops active background worker thread if running."""
        if self._active_worker is not None and self._active_worker.isRunning():
            self._active_worker.requestInterruption()
            self._active_worker.quit()
            self._active_worker.wait(1000)
            self._active_worker = None

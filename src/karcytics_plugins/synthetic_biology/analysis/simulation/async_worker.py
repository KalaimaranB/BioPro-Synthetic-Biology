"""Asynchronous worker for kinetic genetic circuit differential equation simulation."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal  # noqa: TID251

from ..models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
    SimulationResult,
)
from .circuit_engine import CircuitSimulationEngine

MAX_DOWNSAMPLE_POINTS = 1000


class CircuitSimWorker(QThread):
    """Granular QThread worker dedicated strictly to executing SciPy solve_ivp
    circuit simulations.
    """

    simulation_finished = pyqtSignal(SimulationResult)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        components: list[CircuitComponent],
        edges: list[CircuitEdge],
        params: SimulationParameters | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.components = components
        self.edges = edges
        self.params = params or SimulationParameters()

    def run(self) -> None:
        """Executes non-blocking ODE numerical integration."""
        try:
            result = CircuitSimulationEngine.simulate_circuit(
                components=self.components,
                edges=self.edges,
                params=self.params,
            )
            # Data Decimation (Downsampling): reduce data points if time steps exceed MAX_DOWNSAMPLE_POINTS
            if (
                result is not None
                and result.time_points
                and len(result.time_points) > MAX_DOWNSAMPLE_POINTS
            ):
                step = len(result.time_points) // MAX_DOWNSAMPLE_POINTS
                result.time_points = result.time_points[::step]
                result.species_concentrations = {
                    k: v[::step] for k, v in result.species_concentrations.items()
                }

            self.simulation_finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

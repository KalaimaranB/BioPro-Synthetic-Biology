"""Asynchronous worker for kinetic genetic circuit differential equation simulation."""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from ..models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
    SimulationResult,
)
from .circuit_engine import CircuitSimulationEngine


class CircuitSimWorker(QThread):
    """Granular QThread worker dedicated strictly to executing SciPy solve_ivp
    circuit simulations.
    """

    simulation_finished = pyqtSignal(SimulationResult)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        components: List[CircuitComponent],
        edges: List[CircuitEdge],
        params: Optional[SimulationParameters] = None,
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
            self.simulation_finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

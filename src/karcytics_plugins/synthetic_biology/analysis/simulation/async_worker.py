"""Asynchronous worker for kinetic genetic circuit differential equation simulation."""

from __future__ import annotations

import msgpack  # type: ignore[import-untyped]
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal  # noqa: TID251

from ..models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
)
from .circuit_engine import CircuitSimulationEngine

MAX_DOWNSAMPLE_POINTS = 1000


class CircuitSimWorker(QThread):
    """Granular QThread worker dedicated strictly to executing SciPy solve_ivp
    circuit simulations. Emits binary msgpack payload or SimulationResult object.
    """

    simulation_finished = pyqtSignal(object)
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

            if result is not None:
                # Fast binary msgpack serialization of NumPy byte buffers
                t_arr = np.asarray(result.time_points, dtype=np.float64)
                species_bytes = {
                    k: np.asarray(v, dtype=np.float64).tobytes()
                    for k, v in result.species_concentrations.items()
                }
                packed = msgpack.packb(
                    {
                        "time_bytes": t_arr.tobytes(),
                        "species_bytes": species_bytes,
                        "num_points": len(t_arr),
                    }
                )
                self.simulation_finished.emit(packed)
            else:
                self.simulation_finished.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))

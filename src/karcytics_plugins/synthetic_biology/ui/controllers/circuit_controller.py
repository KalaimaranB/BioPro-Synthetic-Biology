"""Controller managing Circuit Simulation View interactions, SciPy solver
workers, and SynBioState.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from ...analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
    SimulationResult,
)
from ...analysis.state import SynBioState
from ..workers import CircuitSimWorker


class CircuitSimulationController(QObject):
    """Explicit Controller handling NetworkX circuit topology ODE compilation
    and SciPy integration.
    """

    simulation_ready = Signal(SimulationResult)
    error_raised = Signal(str)

    def __init__(self, state: SynBioState | None = None, parent=None):
        super().__init__(parent)
        self.state = state
        self._active_worker: CircuitSimWorker | None = None

    @Slot(list, list, object)
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
            parent=self,
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

        if self.state is not None:
            self.state.set_simulation_result(result)
        self.simulation_ready.emit(result)

    def build_simulation_payload(
        self,
        components: list[CircuitComponent] | None = None,
        edges: list[CircuitEdge] | None = None,
        method: str = "ode",
    ) -> str:
        """Dynamically compiles an Antimony simulation model string from active circuit elements."""
        import re

        comps = (
            components
            if components is not None
            else (self.state.circuit_components if self.state else [])
        )
        conn_edges = (
            edges if edges is not None else (self.state.circuit_edges if self.state else [])
        )

        if not comps:
            return ""

        lines = ["model circuit()"]
        node_map = {c.id: c for c in comps}

        for comp in comps:
            var_name = re.sub(r"[^a-zA-Z0-9_]", "_", comp.id or comp.name)
            init_val = comp.initial_concentration
            if method == "gillespie":
                init_val = int(init_val * 10) if init_val > 0 else 0
            lines.append(f"  species {var_name} = {init_val};")

        for comp in comps:
            var_name = re.sub(r"[^a-zA-Z0-9_]", "_", comp.id or comp.name)
            incoming = [e for e in conn_edges if e.target_id == comp.id]

            reg_factors = []
            for e in incoming:
                src_comp = node_map.get(e.source_id)
                src_var = re.sub(r"[^a-zA-Z0-9_]", "_", e.source_id)
                kd = e.K_d if e.K_d is not None else (src_comp.K_d if src_comp else comp.K_d)
                n = e.n if e.n is not None else (src_comp.n if src_comp else comp.n)
                kd_val = max(1e-6, kd if kd is not None else 1.0)
                n_val = n if n is not None else 2.0

                itype = (e.interaction_type or "").lower()
                if itype == "repression":
                    reg_factors.append(f"(1 / (1 + ({src_var} / {kd_val})^{n_val}))")
                elif itype == "activation":
                    reg_factors.append(
                        f"(({src_var} / {kd_val})^{n_val} / (1 + ({src_var} / {kd_val})^{n_val}))"
                    )

            y_min = comp.y_min if comp.y_min is not None else 0.001
            y_max = comp.y_max if comp.y_max is not None else 5.0
            deg = comp.degradation_rate if comp.degradation_rate is not None else 0.1

            if reg_factors:
                prod_expr = f"{y_min} + ({y_max} - {y_min}) * " + " * ".join(reg_factors)
            else:
                prod_expr = f"{y_max}"

            lines.append(f"  J_prod_{var_name}: => {var_name}; {prod_expr};")
            lines.append(f"  J_deg_{var_name}: {var_name} => ; {deg} * {var_name};")

        lines.append("end")
        return "\n".join(lines)

    def teardown(self) -> None:
        """Stops active background worker thread if running."""
        if self._active_worker is not None:
            self._active_worker.stop_and_wait(1000)
            self._active_worker = None

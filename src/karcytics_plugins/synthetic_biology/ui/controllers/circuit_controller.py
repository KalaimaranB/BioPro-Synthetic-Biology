"""Controller managing Circuit Simulation View interactions, SciPy solver
workers, and SynBioState.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from ...analysis.citations import circuit_ode_step
from ...analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
    SimulationResult,
)
from ...analysis.simulation.kinetics import (
    DEFAULT_DEGRADATION_RATE,
    DEFAULT_Y_MAX,
    DEFAULT_Y_MIN,
    regulation_expression,
    resolve_edge_params,
)
from ...analysis.state import SynBioState
from ..workers import CircuitSimWorker


def antimony_var_names(components: list[CircuitComponent]) -> dict[str, str]:
    """Map each component id to the Antimony species identifier it compiles to.

    Derived from the component *name*, not its id: the identifier comes back as
    a column name in the simulation result and so decides what the Simulate tab
    plots. Deriving it from the id is what made that plot read "comp_1 ...
    comp_5" while the Circuit Simulation tab, which labels by name, showed real
    part names for the same design.

    Antimony identifiers admit only word characters, so this is the sanitized
    name and never carries the source organism; pair it with
    :func:`species_display_labels` to get what a reader should see.
    """
    import re

    var_names: dict[str, str] = {}
    used: set[str] = set()
    for comp in components:
        raw = comp.name or comp.id or "species"
        candidate = re.sub(r"[^a-zA-Z0-9_]", "_", raw).strip("_") or "species"
        if candidate[0].isdigit():
            candidate = f"s_{candidate}"
        # Two components may legitimately share a name; without a suffix the
        # second Antimony declaration would silently redefine the first.
        unique = candidate
        suffix = 2
        while unique in used:
            unique = f"{candidate}_{suffix}"
            suffix += 1
        used.add(unique)
        var_names[comp.id] = unique
    return var_names


def species_display_labels(components: list[CircuitComponent]) -> dict[str, str]:
    """Map each Antimony species identifier to the label a reader should see.

    The identifier cannot hold spaces or parentheses, so "LacI (E. coli lac
    operon)" compiles to the species ``LacI``. This is how the Simulate tab
    recovers the full label from a result's column names, so a trace names the
    organism the gene came from rather than just the protein.
    """
    var_names = antimony_var_names(components)
    by_id = {c.id: c for c in components}
    return {
        var: by_id[comp_id].display_label for comp_id, var in var_names.items() if comp_id in by_id
    }


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
        # What the in-flight run was asked to do, so its methods entry can be
        # recorded once it succeeds — never for a run that failed.
        self._pending_run: (
            tuple[list[CircuitComponent], list[CircuitEdge], SimulationParameters] | None
        ) = None

    @Slot(list, list, object)
    def handle_simulation_request(
        self,
        components: list[CircuitComponent],
        edges: list[CircuitEdge],
        params: SimulationParameters | None = None,
    ) -> None:
        """Launches non-blocking background ODE simulation worker."""
        self._pending_run = (list(components), list(edges), params or SimulationParameters())
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
            self._record_run(result)
        self.simulation_ready.emit(result)

    def _record_run(self, result: SimulationResult) -> None:
        """Add this run to the workspace's methods log if it produced a trace."""
        if self._pending_run is None or self.state is None:
            return
        components, edges, params = self._pending_run
        self._pending_run = None
        if not getattr(result, "success", True) or not result.time_points:
            return
        self.state.record_method(
            circuit_ode_step(
                components,
                edges,
                solver=params.solver_method,
                t_end=params.t_end,
                num_points=params.num_points,
            )
        )

    def build_simulation_payload(
        self,
        components: list[CircuitComponent] | None = None,
        edges: list[CircuitEdge] | None = None,
        method: str = "ode",
    ) -> str:
        """Dynamically compiles an Antimony simulation model string from active circuit elements."""
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
        var_names = antimony_var_names(comps)

        for comp in comps:
            var_name = var_names[comp.id]
            init_val = comp.initial_concentration
            if method == "gillespie":
                init_val = int(init_val * 10) if init_val > 0 else 0
            lines.append(f"  species {var_name} = {init_val};")

        for comp in comps:
            var_name = var_names[comp.id]
            incoming = [e for e in conn_edges if e.target_id == comp.id]

            reg_factors = []
            for e in incoming:
                # Skip dangling edges, as the SciPy engine does.
                if e.source_id not in node_map:
                    continue
                src_var = var_names[e.source_id]
                # Shared with the SciPy engine so both simulators resolve the
                # same K_d / n for the same edge.
                kd_val, n_val = resolve_edge_params(e, target=comp)
                term = regulation_expression(e.interaction_type, src_var, kd_val, n_val)
                if term is not None:
                    reg_factors.append(term)

            y_min = comp.y_min if comp.y_min is not None else DEFAULT_Y_MIN
            y_max = comp.y_max if comp.y_max is not None else DEFAULT_Y_MAX
            deg = (
                comp.degradation_rate
                if comp.degradation_rate is not None
                else DEFAULT_DEGRADATION_RATE
            )

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

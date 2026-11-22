"""Machine Learning Optimization Engine for Genetic Circuit Kinetic Parameters.

Feeds empirical .fcs fluorescence profiles and NGS variant frequencies back into the
`CircuitSimulationEngine`, fitting Hill parameters (n, Kd, y_max, y_min, degradation)
to match empirical observations.

**There is a demonstration path, and it is labelled as one.** When no usable
flow-cytometry series is supplied, this engine can still show what a fit looks
like by fitting synthetic targets derived from the circuit's own output. That
path previously reported "Hill parameters optimized against empirical dataset"
with ``success=True`` against data it had invented, and the noise was unseeded
so no two runs agreed (audit finding C-4). It now sets ``is_mock=True``, names
itself in ``status_message``, and draws from a seeded generator so a
demonstration is reproducible. ``analysis/result_integrity.py`` is what stops
a view presenting it as a measurement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.optimize import minimize

from ..models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
)
from ..simulation.circuit_engine import CircuitSimulationEngine
from .fcs_ingestion import FCSEventData
from .ngs_alignment import NGSAlignmentResult

#: Seed for the demonstration path's synthetic targets. Fixed so that the same
#: circuit demonstrates the same fit every time: an unseeded generator gave
#: MSE 0.2319 / 0.1890 / 0.2435 across three identical runs, and a figure a
#: student cannot reproduce should not be shown as a fit at all.
DEMO_TARGET_SEED = 20261121

#: Scale and offset applied to the simulated trace to make a synthetic target
#: that differs from the model it came from. A presentation convention for the
#: demonstration path; it cites nothing because it is not a measurement.
DEMO_TARGET_SCALE = 0.85
DEMO_TARGET_OFFSET = 0.1
DEMO_TARGET_NOISE_SD = 0.05


@dataclass
class HillOptimizationResult:
    """Container holding original vs empirically optimized kinetic parameters."""

    original_components: list[CircuitComponent] = field(default_factory=list)
    optimized_components: list[CircuitComponent] = field(default_factory=list)
    parameter_deltas: dict[str, dict[str, tuple[float, float]]] = field(default_factory=dict)
    initial_mse: float = 0.0
    final_mse: float = 0.0
    fitted_time_series: dict[str, list[float]] = field(default_factory=dict)
    empirical_time_series: dict[str, list[float]] = field(default_factory=dict)
    status_message: str = "Optimization complete"
    success: bool = True
    #: True when the targets were synthesised rather than measured. Read by
    #: ``analysis/result_integrity.assess``; a view must not present a result
    #: carrying this flag as a measurement.
    is_mock: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "parameter_deltas": self.parameter_deltas,
            "initial_mse": self.initial_mse,
            "final_mse": self.final_mse,
            "status_message": self.status_message,
            "success": self.success,
            "is_mock": self.is_mock,
        }


class CircuitMLOptimizationEngine:
    """Machine learning optimization loop for Hill kinetic parameters.

    Adjusts binding cooperativity (n), dissociation constants (K_d), leakiness (y_min),
    max expression (y_max), and protein degradation rates based on empirical data.
    """

    @staticmethod
    def _build_target_curves(
        components: list[CircuitComponent],
        orig_sim: Any,
        fcs_data: FCSEventData | None,
    ) -> tuple[dict[str, list[float]], bool]:
        """The curves to fit against, and whether they are real measurements.

        Where the targets come from decides what the result may claim. Real
        observations give a measurement; targets synthesised from the model's
        own output give a demonstration, and the two must not be reported the
        same way (audit finding C-4).

        Returns:
            ``(target_curves, usable_fcs)``. ``usable_fcs`` is False whenever
            the supplied dataset is absent, did not load, carried no events or
            carried no time series — each of which previously fell through to
            the synthetic path while still being reported as empirical.
        """
        usable_fcs = bool(
            fcs_data is not None
            and getattr(fcs_data, "is_valid", True)
            and getattr(fcs_data, "total_events", 0)
            and fcs_data.time_series_expression
        )
        if usable_fcs:
            return dict(fcs_data.time_series_expression), True  # type: ignore[union-attr]

        # Demonstration path, seeded so the same circuit demonstrates the same
        # fit every time. A falling error here measures nothing about any
        # cells; the caller flags the result is_mock and says so.
        rng = np.random.default_rng(DEMO_TARGET_SEED)
        curves: dict[str, list[float]] = {}
        for comp in components:
            orig_conc = orig_sim.species_concentrations.get(comp.name, [])
            if orig_conc:
                # Parameter shift (higher leakiness, lower max expression)
                noise = rng.normal(0, DEMO_TARGET_NOISE_SD, len(orig_conc))
                curves[comp.name] = (
                    np.array(orig_conc) * DEMO_TARGET_SCALE + DEMO_TARGET_OFFSET + noise
                ).tolist()
        return curves, False

    @classmethod
    def fit_kinetic_parameters(  # noqa: C901
        cls,
        components: list[CircuitComponent],
        edges: list[CircuitEdge],
        fcs_data: FCSEventData,
        ngs_data: NGSAlignmentResult | None = None,  # noqa: ARG003 — reserved for future NGS-based fitting
        sim_params: SimulationParameters | None = None,
    ) -> HillOptimizationResult:
        """Perform non-linear least-squares parameter fitting against FCS data."""
        if not components:
            return HillOptimizationResult(
                status_message="No circuit components provided", success=False
            )

        if sim_params is None:
            sim_params = SimulationParameters(t_start=0.0, t_end=100.0, num_points=50)

        # Baseline original simulation
        orig_sim = CircuitSimulationEngine.simulate_circuit(components, edges, sim_params)

        target_curves, usable_fcs = cls._build_target_curves(components, orig_sim, fcs_data)

        if not target_curves:
            reason = "no circuit output to fit against"
            if fcs_data is not None and not getattr(fcs_data, "is_valid", True):
                reason = getattr(fcs_data, "error_message", "") or "the dataset did not load"
            return HillOptimizationResult(
                original_components=components,
                status_message=f"Nothing to fit: {reason}.",
                success=False,
            )

        # Build initial vector of optimization parameters per component
        initial_params = []
        bounds = []

        for comp in components:
            # y_min, y_max, K_d, n, degradation_rate
            initial_params.extend(
                [
                    comp.y_min,
                    comp.y_max,
                    comp.K_d,
                    comp.n,
                    comp.degradation_rate,
                ]
            )
            bounds.extend(
                [
                    (0.0001, 1.0),  # y_min
                    (0.1, 50.0),  # y_max
                    (0.01, 20.0),  # K_d
                    (0.5, 6.0),  # n (Hill coefficient)
                    (0.01, 2.0),  # degradation_rate
                ]
            )

        def objective_function(param_vector: np.ndarray) -> float:
            # Reconstruct temporary components
            temp_comps = []
            idx = 0
            for orig in components:
                c = CircuitComponent(
                    id=orig.id,
                    name=orig.name,
                    component_type=orig.component_type,
                    y_min=float(param_vector[idx]),
                    y_max=float(param_vector[idx + 1]),
                    K_d=float(param_vector[idx + 2]),
                    n=float(param_vector[idx + 3]),
                    degradation_rate=float(param_vector[idx + 4]),
                    initial_concentration=orig.initial_concentration,
                )
                temp_comps.append(c)
                idx += 5

            res = CircuitSimulationEngine.simulate_circuit(temp_comps, edges, sim_params)
            if not res.success:
                return 1e6

            mse = 0.0
            for c_name, target in target_curves.items():
                simulated = res.species_concentrations.get(c_name)
                if simulated and len(simulated) == len(target):
                    mse += float(np.mean((np.array(simulated) - np.array(target)) ** 2))

            return mse

        # Calculate initial MSE
        initial_mse = float(objective_function(np.array(initial_params)))

        # Perform SciPy minimize using L-BFGS-B bounded solver
        res_opt = minimize(
            fun=objective_function,
            x0=initial_params,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 35},
        )

        opt_params = res_opt.x if res_opt.success else initial_params
        final_mse = float(res_opt.fun)

        # Build optimized components list & deltas map
        opt_components: list[CircuitComponent] = []
        deltas: dict[str, dict[str, tuple[float, float]]] = {}

        idx = 0
        for orig in components:
            new_y_min = float(opt_params[idx])
            new_y_max = float(opt_params[idx + 1])
            new_K_d = float(opt_params[idx + 2])  # noqa: N806
            new_n = float(opt_params[idx + 3])
            new_deg = float(opt_params[idx + 4])

            opt_c = CircuitComponent(
                id=orig.id,
                name=orig.name,
                component_type=orig.component_type,
                y_min=new_y_min,
                y_max=new_y_max,
                K_d=new_K_d,
                n=new_n,
                degradation_rate=new_deg,
                initial_concentration=orig.initial_concentration,
            )
            opt_components.append(opt_c)

            deltas[orig.name] = {
                "y_min": (orig.y_min, new_y_min),
                "y_max": (orig.y_max, new_y_max),
                "K_d": (orig.K_d, new_K_d),
                "n": (orig.n, new_n),
                "degradation_rate": (orig.degradation_rate, new_deg),
            }
            idx += 5

        # Final simulation run with optimized parameters
        opt_sim = CircuitSimulationEngine.simulate_circuit(opt_components, edges, sim_params)

        return HillOptimizationResult(
            original_components=components,
            optimized_components=opt_components,
            parameter_deltas=deltas,
            initial_mse=initial_mse,
            final_mse=final_mse,
            fitted_time_series=opt_sim.species_concentrations,
            empirical_time_series=target_curves,
            status_message=(
                "Hill parameters optimized against the supplied flow-cytometry dataset"
                if usable_fcs
                else (
                    "Demonstration fit: no usable flow-cytometry data was supplied, so the "
                    "targets were synthesised from this circuit's own simulated output. "
                    "The error values describe the fit to that synthetic target and say "
                    "nothing about any measurement."
                )
            ),
            success=True,
            is_mock=not usable_fcs,
        )

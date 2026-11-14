"""The Antimony/Tellurium path must scale production exactly as SciPy does.

Two simulators plot the same circuit: the SciPy engine on the Circuit
Simulation tab and an Antimony model handed to Tellurium on the Simulate tab.
The RPU x min fix (audit finding C-1) had to land on both, or the same design
would plot at two different scales in two tabs.

``test_simulator_agreement`` does not cover this. It pins the two paths'
*regulation terms* -- ``regulation_factor`` against
``regulation_expression`` -- which are shared and were already correct. The
production reaction itself is built in the view and was untested, so the
agreement suite passed with the two fixed points a factor of 1/gamma apart.
That gap is what this module closes.
"""

from __future__ import annotations

import numpy as np
import pytest

from karcytics_plugins.synthetic_biology.analysis.models.domain import (
    CircuitComponent,
    SimulationParameters,
)
from karcytics_plugins.synthetic_biology.analysis.parts.components import CDS, Promoter
from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
    CircuitSimulationEngine,
)
from karcytics_plugins.synthetic_biology.ui.views.simulate_view import SimulateView

Y_MAX = 10.0
Y_MIN = 0.001
GAMMA = 0.2


def _parts(y_max=Y_MAX, gamma=GAMMA, repressors=()):
    """One promoter driving one CDS: the smallest model with a fixed point."""
    return [
        Promoter(
            id="p1",
            name="pTet",
            y_min=Y_MIN,
            y_max=y_max,
            K_d=1.0,
            n=2.0,
            repressors=list(repressors),
        ),
        CDS(id="c1", name="GFP", product="GFP", degradation_rate=gamma),
    ]


def _antimony(parts, method="ode"):
    """Generate the model string.

    Called unbound: the generator reads only its arguments, and constructing a
    SimulateView would need a QApplication and a live state for no benefit.
    """
    return SimulateView._generate_antimony_from_parts(None, parts, method)


# ── The reaction carries the degradation rate ──────────────────────────


@pytest.mark.unit
def test_the_production_reaction_is_scaled_by_the_degradation_rate():
    model = _antimony(_parts())

    production = next(line for line in model.splitlines() if "J_prod_GFP" in line)
    assert f"{GAMMA} * (" in production, (
        f"production must be scaled by gamma so [P]* = y, got: {production.strip()}"
    )


@pytest.mark.unit
def test_degradation_is_unchanged_and_still_first_order():
    model = _antimony(_parts())

    degradation = next(line for line in model.splitlines() if "J_deg_GFP" in line)
    assert f"{GAMMA} * GFP" in degradation


# ── The fixed point, through Tellurium itself ──────────────────────────


@pytest.mark.unit
def test_tellurium_settles_a_derepressed_gene_at_y_max():
    """The same invariant the SciPy engine is held to, in the other simulator.

    Before the fix this settled at y_max / gamma = 50 RPU on an axis labelled
    RPU whose promoter caps at 10.
    """
    tellurium = pytest.importorskip("tellurium")

    runner = tellurium.loada(_antimony(_parts()))
    runner.simulate(0, 2000, 500)

    final = float(runner.GFP)
    assert final == pytest.approx(Y_MAX, rel=1e-3), (
        f"a derepressed gene must settle at y_max = {Y_MAX} RPU, "
        f"not y_max / gamma = {Y_MAX / GAMMA}"
    )


@pytest.mark.unit
@pytest.mark.parametrize("gamma", [0.05, 0.2, 1.0])
def test_the_fixed_point_is_independent_of_the_degradation_rate(gamma):
    """Gamma must set the timescale only, never the level."""
    tellurium = pytest.importorskip("tellurium")

    runner = tellurium.loada(_antimony(_parts(gamma=gamma)))
    runner.simulate(0, 5000, 1000)

    assert float(runner.GFP) == pytest.approx(Y_MAX, rel=1e-3)


@pytest.mark.unit
def test_both_simulators_reach_the_same_level_for_the_same_gene():
    """Cross-check: SciPy and Tellurium on one circuit, same steady state."""
    tellurium = pytest.importorskip("tellurium")

    runner = tellurium.loada(_antimony(_parts()))
    runner.simulate(0, 2000, 500)
    antimony_level = float(runner.GFP)

    gene = CircuitComponent(
        id="GFP",
        name="GFP",
        component_type="cds",
        y_min=Y_MIN,
        y_max=Y_MAX,
        K_d=1.0,
        n=2.0,
        degradation_rate=GAMMA,
        initial_concentration=0.0,
    )
    result = CircuitSimulationEngine.simulate_circuit(
        [gene], [], SimulationParameters(t_start=0.0, t_end=2000.0, num_points=500)
    )
    assert result.success, result.status_message
    scipy_level = np.asarray(result.species_concentrations["GFP"], dtype=float)[-1]

    assert antimony_level == pytest.approx(scipy_level, rel=1e-3), (
        f"the two simulators disagree on the same gene: "
        f"Antimony {antimony_level:.4f} vs SciPy {scipy_level:.4f} RPU"
    )

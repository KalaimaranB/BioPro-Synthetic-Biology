"""The plotted quantity is RPU, and the bound that forces the preset's n.

The defect this closes (audit finding C-1): the engine integrated

    d[P]/dt = y_min + (y_max - y_min) * Prod Hill(R) - gamma * [P]

so a gene's steady state was ``production / gamma``. But ``y_min`` and
``y_max`` are *relative promoter units* from the Cello UCF -- a dimensionless
output level, not a synthesis rate -- so dividing RPU by a rate in min^-1
gives RPU x min. Four axes called that RPU, and the repressilator preset
peaked at 24.5 on an axis whose promoters cap at 10 RPU.

Production is now scaled by gamma, so ``[P]* = y``. The first test here is
the invariant that restores: a fully derepressed gene settles at ``y_max``.
It would have caught the original defect immediately, at any y_max.

Measurement method, recorded so these numbers can be reproduced:

* amplitude is peak-to-trough of the named trace over the first and last
  third of a 400-min window sampled at 1600 points, matching ``DEMO_T_END``
  and ``DEMO_NUM_POINTS``;
* period is the mean peak-to-peak spacing over the last half of that window;
* the analytic Hopf threshold is the root of ``loop gain = 2`` for a
  symmetric three-node ring, computed from the closed form in
  :func:`loop_gain` below;
* the finite-time threshold is bisection on "still oscillating at 400 min"
  against the real engine, and is deliberately higher -- just above the
  analytic threshold the growth rate is too small to show inside the window.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.optimize import brentq

from karcytics_plugins.synthetic_biology.analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
)
from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
    PRESET_PROVENANCE,
    CircuitSimulationEngine,
)
from karcytics_plugins.synthetic_biology.analysis.units import (
    OUTPUT_UNIT,
    PROTEIN_AXIS_LABEL,
    axis_label,
)

T_END = 400.0
NUM_POINTS = 1600

#: Analytic Hopf threshold for the preset's parameters after the gamma
#: scaling. Before it, the same calculation gave 2.1484.
ANALYTIC_THRESHOLD = 2.4514

#: The preset's values, asserted here so a silent retune fails a test.
SUSTAINED_N = 3.5
DAMPED_N = 2.0


def _simulate(components, edges, t_end=T_END, num_points=NUM_POINTS):
    result = CircuitSimulationEngine.simulate_circuit(
        components,
        edges,
        SimulationParameters(t_start=0.0, t_end=t_end, num_points=num_points),
    )
    assert result.success, result.status_message
    return result


def _trace(result, substring):
    key = next(k for k in result.species_concentrations if substring in k)
    return np.asarray(result.species_concentrations[key], dtype=float)


def _amplitude(trace, lo_frac, hi_frac):
    """Peak-to-trough over a fractional window of the trace."""
    segment = trace[int(len(trace) * lo_frac) : int(len(trace) * hi_frac)]
    return float(segment.max() - segment.min())


def _period(trace, t_end=T_END):
    """Mean peak-to-peak spacing over the last half of the window."""
    times = np.linspace(0.0, t_end, len(trace))
    half = len(trace) // 2
    seg, ts = trace[half:], times[half:]
    peaks = [i for i in range(1, len(seg) - 1) if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1]]
    if len(peaks) < 2:
        return float("nan")
    return float(np.mean(np.diff(ts[peaks])))


def _preset_at(n):
    components, edges = CircuitSimulationEngine.create_preset_repressilator()
    for component in components:
        component.n = n
    for edge in edges:
        edge.n = n
    return components, edges


def _sustains(n):
    trace = _trace(_simulate(*_preset_at(n)), "LacI")
    first, last = _amplitude(trace, 0.0, 1 / 3), _amplitude(trace, 2 / 3, 1.0)
    return (last > 0.25 and last > 0.5 * first), first, last


# ── The invariant the fix restores ─────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize("y_max", [1.0, 5.0, 10.0, 250.0])
@pytest.mark.parametrize("gamma", [0.05, 0.2, 1.0])
def test_a_fully_derepressed_gene_settles_at_y_max(y_max, gamma):
    """[P]* must equal y_max, in RPU, independently of the degradation rate.

    This is the test that would have caught C-1: before the fix the steady
    state was y_max / gamma, so at the preset's gamma = 0.2 a promoter
    capped at 10 RPU settled at 50.
    """
    gene = CircuitComponent(
        id="P",
        name="P",
        component_type="cds",
        y_min=0.001,
        y_max=y_max,
        K_d=1.0,
        n=2.0,
        degradation_rate=gamma,
        initial_concentration=0.0,
    )

    final = _trace(_simulate([gene], [], t_end=2000.0, num_points=400), "P")[-1]

    assert final == pytest.approx(y_max, rel=1e-3), (
        f"a fully derepressed gene must settle at y_max = {y_max} RPU, "
        f"not y_max / gamma = {y_max / gamma}"
    )


@pytest.mark.unit
def test_a_repressed_gene_settles_at_y_min_not_y_min_over_gamma():
    """The other end of the same invariant."""
    gene = CircuitComponent(
        id="Target",
        name="Target",
        component_type="cds",
        y_min=0.05,
        y_max=10.0,
        K_d=0.01,
        n=2.0,
        degradation_rate=0.2,
        initial_concentration=0.0,
    )
    repressor = CircuitComponent(
        id="R",
        name="R",
        component_type="cds",
        y_min=5.0,
        y_max=5.0,
        K_d=1.0,
        n=2.0,
        degradation_rate=0.2,
        initial_concentration=5.0,
    )
    edge = CircuitEdge(source_id="R", target_id="Target", interaction_type="repression")

    final = _trace(_simulate([repressor, gene], [edge], t_end=2000.0, num_points=400), "Target")[-1]

    assert final < 0.2, f"a strongly repressed gene must sit near y_min, got {final}"


@pytest.mark.unit
def test_the_result_carries_its_unit():
    """So a view labels its axis from the result, not from a hopeful constant."""
    result = _simulate(*CircuitSimulationEngine.create_preset_repressilator())

    assert result.unit == OUTPUT_UNIT == "RPU"
    assert result.to_dict()["unit"] == "RPU"


@pytest.mark.unit
def test_the_axis_label_is_derived_from_the_unit():
    assert PROTEIN_AXIS_LABEL == "Protein concentration (RPU)"
    assert axis_label("Molecule count", unit="") == "Molecule count", (
        "a quantity with no unit must not get an empty parenthesis"
    )


# ── The bound: sup(loop gain) = n, so a 3-ring needs n > 2 ─────────────


def loop_gain(y_min, y_max, k_d, n):
    """|f'(P*)| at the symmetric fixed point P* = f(P*), in closed form.

    For the scaled system the loop gain of a symmetric ring is exactly
    |f'(P*)|, and a three-node ring is unstable when that exceeds 2.
    """

    def f(p):
        return y_min + (y_max - y_min) / (1.0 + (p / k_d) ** n)

    p_star = brentq(lambda p: f(p) - p, 1e-12, 1e9)
    u = (p_star / k_d) ** n
    return (y_max - y_min) * n * u / (p_star * (1.0 + u) ** 2)


@pytest.mark.unit
def test_the_loop_gain_never_exceeds_n():
    """Sup over K_d, y_max, y_min of the loop gain = n, exactly.

    The algebra: with u = (P*/K_d)^n, m = y_min and D = y_max - y_min,

        gain = D*n*u / [(1+u) * (m*(1+u) + D)]  <=  n*u/(1+u)  <  n

    with equality approached as y_min -> 0 and K_d -> 0. This is the bound
    that makes n > 2 a hard requirement rather than a tuning preference.
    """
    for n in (2.0, 2.5, 3.0, 4.0):
        best = 0.0
        for y_min in (1e-9, 1e-6, 1e-3, 1e-1):
            for y_max in (1.0, 10.0, 1e3, 1e6):
                if y_max <= y_min:
                    continue
                for k_d in np.logspace(-9, 3, 60):
                    best = max(best, loop_gain(y_min, y_max, k_d, n))
        assert best <= n + 1e-9, f"loop gain {best} exceeded the bound n = {n}"
        assert best > 0.99 * n, f"bound n = {n} should be approachable, best was {best}"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("y_min", "y_max", "k_d", "gamma"),
    [
        (0.001, 10.0, 1.0, 0.2),
        (1e-9, 1e6, 1e-4, 0.2),
        (0.05, 250.0, 0.05, 1.0),
        (1e-6, 1.0, 1e-3, 0.05),
    ],
)
def test_a_three_ring_cannot_sustain_oscillation_at_n_equals_two(y_min, y_max, k_d, gamma):
    """N = 2 is the hard bound: no parameter set rescues it.

    Pins the consequence of sup(loop gain) = n. Measured Hill coefficients
    for LacI, TetR and cI are all about 2, which is why this reduced model
    cannot oscillate at physiological cooperativity -- the reason the preset
    must use a non-physiological n and say so.
    """
    ids = ("A", "B", "C")
    components = [
        CircuitComponent(
            id=cid,
            name=cid,
            component_type="cds",
            y_min=y_min,
            y_max=y_max,
            K_d=k_d,
            n=2.0,
            degradation_rate=gamma,
            initial_concentration=(y_max if i == 0 else y_min),
        )
        for i, cid in enumerate(ids)
    ]
    edges = [
        CircuitEdge(source_id=ids[i], target_id=ids[(i + 1) % 3], interaction_type="repression")
        for i in range(3)
    ]

    trace = _trace(_simulate(components, edges, t_end=4000.0, num_points=4000), "A")
    first = _amplitude(trace, 0.0, 1 / 3)
    last = _amplitude(trace, 2 / 3, 1.0)

    assert last < 0.05 * max(first, 1e-12) or last < 1e-6 * max(y_max, 1.0), (
        f"n = 2 must not sustain a 3-ring (loop gain <= n = 2 is the Hopf "
        f"boundary); amplitude went {first:.6g} -> {last:.6g}"
    )


# ── The re-measured threshold and the retuned preset ───────────────────


@pytest.mark.unit
def test_the_analytic_hopf_threshold_moved_with_the_scaling():
    """Scaling production by gamma changes the Jacobian, so the Hopf moves."""
    threshold = brentq(lambda n: loop_gain(0.001, 10.0, 1.0, n) - 2.0, 1.01, 20.0)

    assert threshold == pytest.approx(ANALYTIC_THRESHOLD, abs=1e-3)
    assert threshold > 2.0, "and it must stay above the hard bound"


@pytest.mark.unit
def test_the_preset_sits_well_above_the_threshold_and_sustains():
    """N = 3.5: +42.8% margin, 89% of amplitude retained, period ~27.8 min."""
    components, _ = CircuitSimulationEngine.create_preset_repressilator()
    assert all(c.n == SUSTAINED_N for c in components), "the preset's own n"

    margin = (SUSTAINED_N - ANALYTIC_THRESHOLD) / ANALYTIC_THRESHOLD
    assert margin > 0.15, f"margin {margin:.1%} is under the 15% floor"

    ok, first, last = _sustains(SUSTAINED_N)
    assert ok, f"n = {SUSTAINED_N} must sustain; amplitude {first:.3f} -> {last:.3f}"
    assert first == pytest.approx(7.208, abs=0.05)
    assert last == pytest.approx(6.439, abs=0.05)
    assert last / first > 0.85, "most of the amplitude must survive the window"

    period = _period(_trace(_simulate(*_preset_at(SUSTAINED_N)), "LacI"))
    assert period == pytest.approx(27.8, abs=0.5)


@pytest.mark.unit
def test_the_tour_s_low_value_sits_well_below_the_threshold_and_damps():
    """N = 2.0: -18.4% margin, and at the hard bound, so it damps to flat."""
    margin = (ANALYTIC_THRESHOLD - DAMPED_N) / ANALYTIC_THRESHOLD
    assert margin > 0.15, f"margin {margin:.1%} is under the 15% floor"

    ok, first, last = _sustains(DAMPED_N)
    assert not ok, f"n = {DAMPED_N} must damp; amplitude {first:.3f} -> {last:.3f}"
    assert first == pytest.approx(4.023, abs=0.05)
    assert last < 0.01, f"it must damp to flat, got {last}"


@pytest.mark.unit
def test_the_rejected_value_is_rejected_for_the_stated_reason():
    """N = 2.2 damps, but only 10.3% below the threshold -- under the floor."""
    margin = (ANALYTIC_THRESHOLD - 2.2) / ANALYTIC_THRESHOLD

    assert margin < 0.15, (
        "2.2 is recorded as rejected for insufficient margin; if this now "
        "passes the floor the docstring's reasoning is stale"
    )
    assert not _sustains(2.2)[0], "it does damp, which is why it was tempting"


@pytest.mark.unit
def test_the_finite_time_threshold_is_above_the_analytic_one():
    """Bisection on the engine, and why a demo needs this figure not the other."""
    lo, hi = 1.5, 6.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if _sustains(mid)[0]:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-3:
            break
    finite_time = 0.5 * (lo + hi)

    assert finite_time == pytest.approx(2.657, abs=0.01)
    assert finite_time > ANALYTIC_THRESHOLD, (
        "just above the analytic threshold the growth rate is too small to "
        "show inside 400 min, so the visible threshold is higher"
    )


# ── The provenance of the preset's numbers ─────────────────────────────


@pytest.mark.unit
def test_the_cello_values_are_sourced_and_the_chosen_ones_are_not():
    assert PRESET_PROVENANCE["y_min"].kind == "sourced"
    assert PRESET_PROVENANCE["y_max"].kind == "sourced"
    for chosen in ("K_d", "n", "degradation_rate", "initial_concentration"):
        assert PRESET_PROVENANCE[chosen].kind == "convention", chosen


@pytest.mark.unit
def test_the_hill_coefficient_declares_it_is_not_physiological():
    """A preset that hid this would make the tool unciteable."""
    entry = PRESET_PROVENANCE["n"]

    assert entry.mechanism == ("elowitz2000",)
    assert "not n = 3.5" in entry.mechanism_claim, "the paper must not be made to own it"
    assert "2.4514" in entry.explanation, "state the threshold it clears"
    assert "n > 2" in entry.explanation, "state the hard bound"


@pytest.mark.unit
def test_the_preset_docstring_states_the_bound_and_the_physiology():
    doc = CircuitSimulationEngine.create_preset_repressilator.__doc__ or ""

    assert "sup(loop gain)" in doc
    assert "n > 2" in doc
    assert "2.4514" in doc
    assert "cannot oscillate at physiological" in doc
    assert "27.8" in doc, "the measured period"

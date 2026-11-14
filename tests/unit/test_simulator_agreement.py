"""The SciPy engine and the Antimony compiler must agree on the same circuit.

These two paths used to resolve an edge's K_d / n from different nodes (the
engine from the target, the compiler from the source), so an asymmetric circuit
plotted differently in the Circuit Simulation tab and the Simulate tab.
"""

from __future__ import annotations

import pytest

from karcytics_plugins.synthetic_biology.analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
)
from karcytics_plugins.synthetic_biology.analysis.simulation.kinetics import (
    regulation_expression,
    regulation_factor,
    resolve_edge_params,
)


def _asymmetric_circuit() -> tuple[list[CircuitComponent], list[CircuitEdge]]:
    """A repressor whose K_d / n differ from the gene it regulates.

    The preset repressilator shares K_d=1.0, n=3.5 across all three nodes,
    which is exactly why it hid the disagreement.
    """
    repressor = CircuitComponent(
        id="R",
        name="Repressor",
        component_type="cds",
        y_min=0.01,
        y_max=8.0,
        K_d=5.0,
        n=1.2,
        degradation_rate=0.2,
        initial_concentration=2.0,
    )
    reporter = CircuitComponent(
        id="G",
        name="GFP",
        component_type="cds",
        y_min=0.02,
        y_max=10.0,
        K_d=0.5,
        n=3.4,
        degradation_rate=0.05,
        initial_concentration=0.1,
    )
    # K_d and n unset on the edge — the dataclass default, and the common case.
    edges = [CircuitEdge(source_id="R", target_id="G", interaction_type="repression")]
    return [repressor, reporter], edges


@pytest.mark.unit
def test_edge_params_fall_back_to_target_node():
    """An edge with no K_d / n of its own inherits them from its target."""
    components, edges = _asymmetric_circuit()
    target = {c.id: c for c in components}["G"]

    k_d, n = resolve_edge_params(edges[0], target=target)

    assert k_d == pytest.approx(0.5)
    assert n == pytest.approx(3.4)


@pytest.mark.unit
def test_edge_params_prefer_explicit_edge_values():
    """Operator-specific values on the edge win over the node's."""
    _, _ = _asymmetric_circuit()
    edge = CircuitEdge(source_id="R", target_id="G", interaction_type="repression", K_d=2.5, n=1.8)
    target = CircuitComponent(id="G", name="GFP", component_type="cds", K_d=0.5, n=3.4)

    k_d, n = resolve_edge_params(edge, target=target)

    assert k_d == pytest.approx(2.5)
    assert n == pytest.approx(1.8)


@pytest.mark.unit
def test_both_simulators_resolve_identical_edge_parameters():
    """The compiled Antimony text carries the engine's resolved parameters."""
    from karcytics_plugins.synthetic_biology.ui.controllers.circuit_controller import (
        CircuitSimulationController,
    )

    components, edges = _asymmetric_circuit()
    target = {c.id: c for c in components}["G"]
    k_d, n = resolve_edge_params(edges[0], target=target)

    model_str = CircuitSimulationController(None).build_simulation_payload(
        components=components, edges=edges
    )

    # The Hill term for the regulated gene must use the shared K_d / n. The
    # source variable is the repressor's *name*, since that is what the
    # Simulate tab shows in its legend.
    assert f"(Repressor / {k_d})^{n}" in model_str


@pytest.mark.unit
def test_both_simulators_label_the_same_species_the_same_way():
    """A design must not be plotted under one set of names in one tab and
    another set in the next.

    The SciPy engine labels traces by component name; the Antimony compiler used
    to name its species after the component *id*, so the same circuit appeared
    as "comp_1 ... comp_5" on the Simulate tab and as real part names on the
    Circuit Simulation tab.
    """
    from karcytics_plugins.synthetic_biology.analysis.models.domain import SimulationParameters
    from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
        CircuitSimulationEngine,
    )
    from karcytics_plugins.synthetic_biology.ui.controllers.circuit_controller import (
        CircuitSimulationController,
    )

    components, edges = _asymmetric_circuit()

    result = CircuitSimulationEngine.simulate_circuit(
        components, edges, SimulationParameters(t_start=0.0, t_end=5.0, num_points=5)
    )
    model_str = CircuitSimulationController(None).build_simulation_payload(
        components=components, edges=edges
    )

    for label in result.species_concentrations:
        # Antimony identifiers cannot contain spaces, so compare the sanitized form.
        assert f"species {label.replace(' ', '_')} =" in model_str


@pytest.mark.unit
@pytest.mark.parametrize("itype", ["repression", "activation"])
def test_numeric_and_symbolic_hill_terms_match(itype: str):
    """``regulation_factor`` and ``regulation_expression`` encode the same math."""
    k_d, n, conc = 0.5, 3.4, 2.0

    numeric = regulation_factor(itype, conc, k_d, n)
    expr = regulation_expression(itype, "R", k_d, n)
    assert numeric is not None and expr is not None

    # Evaluate the Antimony expression as Python (^ is Antimony's power operator).
    evaluated = eval(expr.replace("^", "**"), {"R": conc})  # noqa: S307
    assert evaluated == pytest.approx(numeric)


@pytest.mark.unit
def test_unknown_interaction_type_is_skipped_not_treated_as_passthrough():
    """An unrecognized interaction yields no term rather than a silent 1.0."""
    assert regulation_factor("sequestration", 1.0, 1.0, 2.0) is None
    assert regulation_expression("sequestration", "R", 1.0, 2.0) is None


@pytest.mark.unit
def test_engine_simulates_asymmetric_circuit_successfully():
    """End-to-end: the resolved parameters still integrate to a valid result."""
    from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
        CircuitSimulationEngine,
    )

    components, edges = _asymmetric_circuit()
    result = CircuitSimulationEngine.simulate_circuit(components, edges)

    assert result.success, result.status_message
    assert set(result.species_concentrations) == {"Repressor", "GFP"}


@pytest.mark.unit
def test_dangling_edge_does_not_crash_the_engine():
    """An edge pointing at a deleted node is ignored, not a bare KeyError."""
    from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
        CircuitSimulationEngine,
    )

    components, _ = _asymmetric_circuit()
    edges = [CircuitEdge(source_id="R", target_id="GHOST", interaction_type="repression")]

    result = CircuitSimulationEngine.simulate_circuit(components, edges)

    assert result.success, result.status_message
    assert "GHOST" not in result.species_concentrations


@pytest.mark.unit
def test_duplicate_component_names_keep_separate_traces():
    """Two components sharing a name must not collapse into one trace."""
    from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
        CircuitSimulationEngine,
    )

    a = CircuitComponent(id="gfp_1", name="GFP", component_type="cds", initial_concentration=1.0)
    b = CircuitComponent(id="gfp_2", name="GFP", component_type="cds", initial_concentration=4.0)

    result = CircuitSimulationEngine.simulate_circuit([a, b], [])

    assert result.success, result.status_message
    assert len(result.species_concentrations) == 2

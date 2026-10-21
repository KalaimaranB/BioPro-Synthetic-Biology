"""Unit tests for NetworkX & SciPy Predictive Circuit Simulation Engine."""

import pytest

from karcytics_plugins.synthetic_biology.analysis.models.domain import (
    SimulationParameters,
    SimulationResult,
)
from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
    CircuitSimulationEngine,
)


@pytest.mark.unit
def test_repressilator_simulation():
    """Test 3-gene Repressilator ring oscillator NetworkX & SciPy solve_ivp ODE
    integration.
    """
    components, edges = CircuitSimulationEngine.create_preset_repressilator()
    params = SimulationParameters(t_start=0.0, t_end=50.0, num_points=100)

    result: SimulationResult = CircuitSimulationEngine.simulate_circuit(
        components=components,
        edges=edges,
        params=params,
    )

    assert result.success is True
    assert len(result.time_points) == 100
    assert "TetR Repressor" in result.species_concentrations
    assert "LacI Repressor" in result.species_concentrations
    assert len(result.species_concentrations["TetR Repressor"]) == 100


@pytest.mark.unit
def test_edge_specific_kd_and_n():
    """Test that edge-specific Kd and n parameters override component defaults."""
    from karcytics_plugins.synthetic_biology.analysis.models.domain import (
        CircuitComponent,
        CircuitEdge,
    )

    comp_a = CircuitComponent(
        id="A",
        name="Repressor_A",
        component_type="cds",
        y_min=0.01,
        y_max=10.0,
        degradation_rate=0.1,
        initial_concentration=2.0,
    )
    comp_b = CircuitComponent(
        id="B",
        name="Target_B",
        component_type="promoter",
        y_min=0.01,
        y_max=10.0,
        K_d=100.0,  # High default on node (weak repression)
        n=1.0,
        degradation_rate=0.1,
        initial_concentration=0.0,
    )

    # Edge with high binding affinity (tight Kd = 0.1, n = 3.0)
    tight_edge = CircuitEdge(
        source_id="A",
        target_id="B",
        interaction_type="repression",
        K_d=0.1,
        n=3.0,
    )

    params = SimulationParameters(t_start=0.0, t_end=20.0, num_points=50)
    result = CircuitSimulationEngine.simulate_circuit(
        components=[comp_a, comp_b],
        edges=[tight_edge],
        params=params,
    )

    assert result.success is True
    # With tight Kd = 0.1 and repressor A at 2.0, Target_B should be strongly repressed (< 0.5 RPU)
    final_b_conc = result.species_concentrations["Target_B"][-1]
    assert final_b_conc < 1.0

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
    assert "cI Repressor" in result.species_concentrations
    assert len(result.species_concentrations["TetR Repressor"]) == 100

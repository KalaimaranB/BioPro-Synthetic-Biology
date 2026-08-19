"""Tests for SynBioState serialization and round-tripping."""

from karcytics_plugins.synthetic_biology.analysis.state import (
    CircuitState,
    SynBioState,
    ViewState,
)


class TestCircuitState:
    """Tests for the CircuitState domain model."""

    def test_default_construction(self):
        state = CircuitState()
        assert state.parts == []
        assert state.connections == []
        assert state.simulation_results == {}

    def test_to_dict(self):
        state = CircuitState(parts=[{"id": "p1"}], connections=[{"src": "p1", "dst": "p2"}])
        d = state.to_dict()
        assert d["parts"] == [{"id": "p1"}]
        assert d["connections"] == [{"src": "p1", "dst": "p2"}]

    def test_round_trip(self):
        original = CircuitState(
            parts=[{"id": "p1", "type": "promoter"}],
            connections=[{"src": "p1", "dst": "p2"}],
            simulation_results={"time": [0, 1, 2]},
        )
        reconstructed = CircuitState.from_dict(original.to_dict())
        assert reconstructed.parts == original.parts
        assert reconstructed.connections == original.connections
        assert reconstructed.simulation_results == original.simulation_results


class TestViewState:
    """Tests for the ViewState UI model."""

    def test_default_construction(self):
        state = ViewState()
        assert state.active_tab == 0
        assert state.selected_part_id is None
        assert state.zoom_level == 1.0

    def test_round_trip(self):
        original = ViewState(active_tab=2, selected_part_id="gate_1", zoom_level=1.5)
        reconstructed = ViewState.from_dict(original.to_dict())
        assert reconstructed.active_tab == 2
        assert reconstructed.selected_part_id == "gate_1"
        assert reconstructed.zoom_level == 1.5


class TestSynBioState:
    """Tests for the top-level SynBioState container."""

    def test_default_construction(self):
        state = SynBioState()
        assert isinstance(state.data, CircuitState)
        assert isinstance(state.view, ViewState)

    def test_to_dict_structure(self):
        state = SynBioState()
        d = state.to_dict()
        assert "data" in d
        assert "view" in d

    def test_full_round_trip(self):
        original = SynBioState()
        original.data.parts = [{"id": "promoter_1", "type": "promoter"}]
        original.data.connections = [{"src": "promoter_1", "dst": "rbs_1"}]
        original.view.active_tab = 3
        original.view.selected_part_id = "promoter_1"

        reconstructed = SynBioState.from_dict(original.to_dict())
        assert reconstructed.data.parts == original.data.parts
        assert reconstructed.data.connections == original.data.connections
        assert reconstructed.view.active_tab == 3
        assert reconstructed.view.selected_part_id == "promoter_1"

    def test_from_empty_dict(self):
        """Gracefully handles an empty dict (e.g., fresh workspace)."""
        state = SynBioState.from_dict({})
        assert state.data.parts == []
        assert state.view.active_tab == 0

    def test_fixture_empty_state(self, empty_state):
        """Verify the conftest fixture works."""
        assert isinstance(empty_state, SynBioState)
        assert empty_state.data.parts == []

    def test_circuit_components_and_edges_properties(self):
        """Verify circuit_components, circuit_edges, and plasmid properties."""
        from karcytics_plugins.synthetic_biology.analysis.models.domain import (
            CircuitComponent,
            CircuitEdge,
            PlasmidVector,
        )

        state = SynBioState()
        assert state.circuit_components == []
        assert state.circuit_edges == []
        assert state.plasmid is None

        c1 = CircuitComponent(id="TetR", name="TetR", component_type="cds")
        e1 = CircuitEdge(source_id="TetR", target_id="LacI", interaction_type="repression")
        p1 = PlasmidVector(id="p1", name="Plasmid 1")

        state.circuit_components = [c1]
        state.circuit_edges = [e1]
        state.plasmid = p1

        assert len(state.circuit_components) == 1
        assert state.circuit_components[0].id == "TetR"
        assert len(state.circuit_edges) == 1
        assert state.circuit_edges[0].source_id == "TetR"
        assert state.plasmid is not None
        assert state.plasmid.id == "p1"

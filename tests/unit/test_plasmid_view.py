"""Unit tests for PyQt6 Views and Controllers (Plasmid, CRISPR, Circuit Simulation)."""

import pytest
from PyQt6.QtWidgets import QApplication

from biopro_plugins.synthetic_biology.analysis.state import SynBioState
from biopro_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
    PlasmidAssemblyController,
)
from biopro_plugins.synthetic_biology.ui.controllers.crispr_controller import (
    CRISPRDesignController,
)
from biopro_plugins.synthetic_biology.ui.controllers.circuit_controller import (
    CircuitSimulationController,
)
from biopro_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
    PlasmidAssemblyView,
)
from biopro_plugins.synthetic_biology.ui.views.crispr_view import CRISPRDesignView
from biopro_plugins.synthetic_biology.ui.views.circuit_simulation_view import (
    CircuitSimulationView,
)


@pytest.fixture(scope="module")
def qapp():
    """Ensure QApplication instance exists for PyQt6 UI tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.mark.unit
def test_plasmid_assembly_view_instantiation(qapp):
    """Test PlasmidAssemblyView widget creation and controller wiring."""
    state = SynBioState()
    controller = PlasmidAssemblyController(state)
    view = PlasmidAssemblyView(state, controller)

    assert view is not None
    assert view.part_palette.count() >= 4
    assert view.assembly_canvas is not None


@pytest.mark.unit
def test_crispr_view_instantiation(qapp):
    """Test CRISPRDesignView widget creation and controller wiring."""
    state = SynBioState()
    controller = CRISPRDesignController(state)
    view = CRISPRDesignView(state, controller)

    assert view is not None
    assert view.pam_combo.count() >= 5


@pytest.mark.unit
def test_circuit_simulation_view_instantiation(qapp):
    """Test CircuitSimulationView widget creation and PyQtGraph plot widget setup."""
    state = SynBioState()
    controller = CircuitSimulationController(state)
    view = CircuitSimulationView(state, controller)

    assert view is not None
    assert view.plot_widget is not None

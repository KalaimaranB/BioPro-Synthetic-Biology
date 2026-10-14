"""Unit tests for Phase 2: Functional Wiring & State Management."""

from unittest.mock import MagicMock, patch

import pytest
from karcytics_sdk.plugin import DirtyTrackingGraphicsScene, DirtyTrackingGraphicsView
from karcytics_sdk.plugin.ribbon import BioRibbon

from karcytics_plugins.synthetic_biology.analysis.parts.components import Promoter
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.canvas.circuit_canvas import CircuitCanvas, CircuitScene
from karcytics_plugins.synthetic_biology.ui.ribbons import (
    BiologicalViewRibbon,
    CatalogueRibbon,
    DesignRibbon,
    PlaceholderRibbon,
    SimulateRibbon,
)
from karcytics_plugins.synthetic_biology.ui.views.laboratory_execution_view import (
    LaboratoryExecutionView,
)
from karcytics_plugins.synthetic_biology.ui.views.properties_view import PropertiesView
from karcytics_plugins.synthetic_biology.utils.robot_exporter import WorklistGenerator


def test_ribbons_inherit_bioribbon():
    """Verify that all ribbons inherit from BioRibbon."""
    mock_factory = MagicMock()
    bio_ribbon = BiologicalViewRibbon(mock_factory)
    cat_ribbon = CatalogueRibbon(mock_factory)
    sim_ribbon = SimulateRibbon(mock_factory)
    des_ribbon = DesignRibbon(mock_factory)
    placeholder = PlaceholderRibbon("Test Tab")

    assert isinstance(bio_ribbon, BioRibbon)
    assert isinstance(cat_ribbon, BioRibbon)
    assert isinstance(sim_ribbon, BioRibbon)
    assert isinstance(des_ribbon, BioRibbon)
    assert isinstance(placeholder, BioRibbon)


def test_canvas_inherits_dirty_tracking():
    """Verify CircuitCanvas and CircuitScene inherit from DirtyTracking classes."""
    canvas = CircuitCanvas()
    assert isinstance(canvas, DirtyTrackingGraphicsView)
    assert isinstance(canvas._scene, DirtyTrackingGraphicsScene)
    assert isinstance(canvas._scene, CircuitScene)


def test_toggle_seq_and_stubs():
    """Verify toggle_seq and toggle_stubs toggle state and trigger render."""
    canvas = CircuitCanvas()
    part = Promoter(id="P1", name="pTet", sequence="TATAA", y_max=5.0)
    canvas.add_part(part)

    assert not canvas._show_sequences
    assert canvas._show_stubs

    canvas.set_show_sequences(True)
    assert canvas._show_sequences

    canvas.set_show_stubs(False)
    assert not canvas._show_stubs

    canvas.toggle_seq()
    assert not canvas._show_sequences

    canvas.toggle_stubs()
    assert canvas._show_stubs


def test_properties_view_state_sync():
    """Verify _on_param_changed triggers state_changed on SynBioState and emits state_changed signal."""
    state = SynBioState()
    state.state_changed = MagicMock()

    view = PropertiesView(state=state)
    part = Promoter(id="P1", name="pTet", y_max=5.0)
    view._current_part = part

    signal_received = []
    view.state_changed.connect(lambda: signal_received.append(True))

    view._on_param_changed("y_max", 10.0)

    assert part.y_max == 10.0
    state.state_changed.assert_called_once()
    assert len(signal_received) == 1


def test_opentrons_placeholder_toast():
    """Verify Opentrons export calls show_toast placeholder."""
    with patch("karcytics_sdk.plugin.toast.show_toast") as mock_toast:
        WorklistGenerator.export_to_opentrons()
        mock_toast.assert_called_once_with(
            "Opentrons OT-2 export coming in v2.1", level="info"
        )

    with patch("karcytics_plugins.synthetic_biology.ui.views.laboratory_execution_view.show_toast") as mock_view_toast:
        lab_view = LaboratoryExecutionView()
        lab_view._on_export_opentrons_clicked()
        mock_view_toast.assert_called_once_with(
            "Opentrons OT-2 export coming in v2.1", level="info"
        )

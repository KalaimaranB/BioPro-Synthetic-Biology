"""Unit tests for the SimulateView UI layout, PyQtGraph integration, and species filtering logic."""

import sys
from unittest.mock import MagicMock

import numpy as np

# Mock sbol3 if not present
if "sbol3" not in sys.modules:
    sys.modules["sbol3"] = MagicMock()

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QSplitter

from karcytics_plugins.synthetic_biology.ui.views.simulate_view import SimulateView

# Ensure QApplication instance exists for PyQt widget tests
app = QApplication.instance() or QApplication([])


def test_simulate_view_layout_setup():
    """Test that SimulateView initializes with QSplitter, plot_widget, and species QListWidget."""
    view = SimulateView()

    assert hasattr(view, "splitter")
    assert isinstance(view.splitter, QSplitter)
    assert hasattr(view, "plot_widget")
    assert isinstance(view.plot_widget, pg.PlotWidget)
    assert hasattr(view, "species_list")
    assert isinstance(view.species_list, QListWidget)
    assert hasattr(view, "select_all_btn")
    assert hasattr(view, "clear_all_btn")


def test_species_list_filtering_and_plot_update():
    """Test species list check state toggling and interactive PyQtGraph plot update."""
    view = SimulateView()

    # Mock simulation result object
    class MockResult:
        colnames = ["time", "[LacI]", "[TetR]"]

        def __getitem__(self, item):
            if item == "time":
                return np.array([0, 1, 2, 3, 4, 5])
            if item in ("[LacI]", "LacI"):
                return np.array([10, 8, 6, 4, 2, 0])
            if item in ("[TetR]", "TetR"):
                return np.array([0, 2, 4, 6, 8, 10])
            return np.array([0, 0, 0, 0, 0, 0])

    mock_res = MockResult()

    # Set up cached simulation state
    view._last_simulation_result = mock_res
    view._last_simulation_method = "ode"
    view._last_simulation_title = "Test Simulation"

    # Populate species list widget
    view.control_panel.setVisible(True)
    view.species_list.blockSignals(True)
    view.species_list.clear()

    for col in mock_res.colnames[1:]:
        clean_name = col.replace("[", "").replace("]", "")
        item = QListWidgetItem(clean_name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked)
        item.setData(Qt.ItemDataRole.UserRole, col)
        view.species_list.addItem(item)

    view.species_list.blockSignals(False)

    assert view.species_list.count() == 2

    # Render plot with both checked
    view.update_plot()
    assert len(view.plot_widget.listDataItems()) == 2

    # Uncheck one item (TetR)
    view.species_list.item(1).setCheckState(Qt.CheckState.Unchecked)
    view.update_plot()
    data_items = view.plot_widget.listDataItems()
    assert len(data_items) == 1
    assert data_items[0].name() == "LacI"

    # Select all helper
    view._select_all_species()
    assert len(view.plot_widget.listDataItems()) == 2

    # Clear all helper
    view._clear_all_species()
    assert len(view.plot_widget.listDataItems()) == 0


def test_nan_inf_simulation_result_handling():
    """Test that SimulateView.update_plot displays UI warning on NaN or Inf array inputs."""
    view = SimulateView()

    class NanResult:
        colnames = ["time", "[LacI]"]

        def __getitem__(self, item):
            if item == "time":
                return np.array([0, 1, 2, 3])
            return np.array([10.0, np.nan, 2.0, np.inf])

    view._last_simulation_result = NanResult()
    view.species_list.clear()
    item = QListWidgetItem("LacI")
    item.setCheckState(Qt.CheckState.Checked)
    item.setData(Qt.ItemDataRole.UserRole, "[LacI]")
    view.species_list.addItem(item)

    view.update_plot()
    assert len(view.plot_widget.listDataItems()) == 0
    # Verify warning text on title
    title_text = view.plot_widget.plotItem.titleLabel.text
    assert "invalid or infinite values" in title_text.lower()


def test_empty_array_simulation_result_handling():
    """Test that SimulateView.update_plot displays UI warning on empty array inputs."""
    view = SimulateView()

    class EmptyResult:
        colnames = ["time", "[LacI]"]

        def __getitem__(self, item):
            return np.array([], dtype=float)

    view._last_simulation_result = EmptyResult()
    view.species_list.clear()
    item = QListWidgetItem("LacI")
    item.setCheckState(Qt.CheckState.Checked)
    item.setData(Qt.ItemDataRole.UserRole, "[LacI]")
    view.species_list.addItem(item)

    view.update_plot()
    assert len(view.plot_widget.listDataItems()) == 0
    title_text = view.plot_widget.plotItem.titleLabel.text
    assert "invalid or infinite values" in title_text.lower()


def test_axis_limits_non_singular():
    """Test that SimulateView.update_plot renders constant traces without crashes."""
    view = SimulateView()

    class ConstantResult:
        colnames = ["time", "[LacI]"]

        def __getitem__(self, item):
            if item == "time":
                return np.array([0, 1, 2, 3])
            return np.array([5.0, 5.0, 5.0, 5.0])

    view._last_simulation_result = ConstantResult()
    view.species_list.clear()
    item = QListWidgetItem("LacI")
    item.setCheckState(Qt.CheckState.Checked)
    item.setData(Qt.ItemDataRole.UserRole, "[LacI]")
    view.species_list.addItem(item)

    view.update_plot()
    assert len(view.plot_widget.listDataItems()) == 1


def test_safe_figure_canvas_zero_dimension_protection():
    """Test that SafeFigureCanvasQTAgg guards against 0-dimension canvas drawing."""
    from matplotlib.figure import Figure

    from karcytics_plugins.synthetic_biology.ui.views.simulate_view import SafeFigureCanvasQTAgg

    fig = Figure(figsize=(6, 4), dpi=100)
    canvas = SafeFigureCanvasQTAgg(fig)
    canvas.resize(0, 0)

    # Calling draw on a 0x0 canvas should return safely without raising exception
    canvas.draw()
    assert canvas.width() == 0 or canvas.height() == 0


def test_simulate_worker_thread_decoupling():
    """Test that SimulateWorker runs off-thread and emits simulation_finished signal."""
    import msgpack

    from karcytics_plugins.synthetic_biology.ui.views.simulate_view import SimulateWorker

    worker = SimulateWorker(
        model_str="model circuit()\n  species P1 = 10;\n  J0: => P1; 1.0;\nend",
        method="ode",
        max_time=10,
        title="Test Thread Decoupling",
    )

    received_payload = None

    def on_finished(payload):
        nonlocal received_payload
        received_payload = payload

    worker.simulation_finished.connect(on_finished)

    # Test run() directly or via start()
    worker.run()
    assert received_payload is not None

    if isinstance(received_payload, bytes):
        unpacked = msgpack.unpackb(received_payload, raw=False)
        assert "arr_bytes" in unpacked
        assert unpacked["method"] == "ode"
        assert unpacked["title"] == "Test Thread Decoupling"
    else:
        assert "result" in received_payload
        assert received_payload["method"] == "ode"
        assert received_payload["title"] == "Test Thread Decoupling"

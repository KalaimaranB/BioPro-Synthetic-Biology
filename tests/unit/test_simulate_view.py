"""Unit tests for the SimulateView UI layout, PyQtGraph integration, and species filtering logic."""

import sys
from unittest.mock import MagicMock

import numpy as np

# Mock sbol3 if not present
if "sbol3" not in sys.modules:
    sys.modules["sbol3"] = MagicMock()

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QSplitter

from karcytics_plugins.synthetic_biology.ui.views.simulate_view import SimulateView

# Ensure QApplication instance exists for PySide6 widget tests
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


def test_empty_circuit_aborts_simulation_with_warning(monkeypatch):
    """Test that an empty circuit aborts worker dispatch and triggers show_warning."""
    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState

    state = SynBioState()
    view = SimulateView(state=state)

    warning_called = {}

    def mock_show_warning(parent, title, message):
        warning_called["title"] = title
        warning_called["message"] = message

    monkeypatch.setattr(
        "karcytics_plugins.synthetic_biology.ui.views.simulate_view.show_warning",
        mock_show_warning,
    )

    view.plot_time_series(max_time=50, method="ode")

    assert warning_called.get("title") == "Empty Circuit"
    assert "Please design or load a circuit before running a simulation." in warning_called.get(
        "message", ""
    )
    assert view._active_worker is None


def test_live_circuit_state_dynamically_generates_payload(monkeypatch):
    """Test that SimulateView parses nodes, edges, and parameters from active SynBioState."""
    from karcytics_plugins.synthetic_biology.analysis.models.domain import (
        CircuitComponent,
        CircuitEdge,
    )
    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
    from karcytics_plugins.synthetic_biology.ui.controllers.circuit_controller import (
        CircuitSimulationController,
    )

    state = SynBioState()
    comp_a = CircuitComponent(
        id="NodeA",
        name="Repressor A",
        component_type="repressor",
        initial_concentration=2.5,
        y_min=0.05,
        y_max=8.0,
        degradation_rate=0.15,
        K_d=1.2,
        n=2.0,
    )
    comp_b = CircuitComponent(
        id="NodeB",
        name="Reporter B",
        component_type="reporter",
        initial_concentration=0.0,
        y_min=0.01,
        y_max=12.0,
        degradation_rate=0.3,
        K_d=0.8,
        n=3.0,
    )
    edge = CircuitEdge(
        source_id="NodeA",
        target_id="NodeB",
        interaction_type="repression",
        K_d=1.2,
        n=2.0,
    )
    state.set_circuit_components([comp_a, comp_b])
    state.data.circuit_edges = [edge.to_dict()]

    controller = CircuitSimulationController(state)
    view = SimulateView(state=state, controller=controller)

    # Intercept worker creation to inspect model_str passed to SimulateWorker
    captured_model = {}

    class MockWorker:
        def __init__(self, model_str, method, max_time, title, parent=None):
            captured_model["model_str"] = model_str
            captured_model["method"] = method
            captured_model["max_time"] = max_time
            self.simulation_finished = MagicMock()
            self.simulation_error = MagicMock()

        def start(self):
            pass

    monkeypatch.setattr(
        "karcytics_plugins.synthetic_biology.ui.views.simulate_view.SimulateWorker",
        MockWorker,
    )

    view.plot_time_series(max_time=150, method="ode")

    assert "model_str" in captured_model
    model_str = captured_model["model_str"]
    # Species are named after the component's *name*, not its id: the Antimony
    # variable becomes the Simulate tab's legend entry, and naming it from the
    # id is what made that plot read "comp_1 ... comp_5" while the Circuit
    # Simulation tab — which labels by name — showed real part names for the
    # same design.
    assert "species Repressor_A = 2.5;" in model_str
    assert "species Reporter_B = 0.0;" in model_str
    assert "J_prod_Repressor_A: => Repressor_A; 8.0;" in model_str
    # Reporter_B has repression from Repressor_A
    assert "J_prod_Reporter_B" in model_str
    assert "Repressor_A" in model_str
    assert "J_deg_Repressor_A: Repressor_A => ; 0.15 * Repressor_A;" in model_str
    assert "J_deg_Reporter_B: Reporter_B => ; 0.3 * Reporter_B;" in model_str
    # The ids must not leak into the model text at all.
    assert "NodeA" not in model_str
    assert "NodeB" not in model_str


def test_species_names_survive_downsampling():
    """A long run must still name its traces after the circuit's species.

    Slicing a Tellurium ``NamedArray`` returns a ``NamedArray`` whose
    ``colnames`` is empty. The worker used to decimate the result before reading
    the names, so any run past the decimation threshold lost them and the view
    fell back to "Species_1", "Species_2", ... A Gillespie run asks for
    ``max_time * 5`` points and so always crossed that threshold, which is why a
    stochastic plot was unnamed while the deterministic plot of the same circuit
    was not.
    """
    import msgpack

    from karcytics_plugins.synthetic_biology.ui.views import simulate_view as sv

    # Stand in for Tellurium: a result that reports its colnames, and loses them
    # on slicing exactly as a NamedArray does.
    class FakeNamedArray:
        def __init__(self, rows: int, named: bool = True):
            self._rows = rows
            self.colnames = ["time", "[LacI]", "[cI]", "[TetR]"] if named else []

        def __len__(self):
            return self._rows

        def __getitem__(self, key):
            assert isinstance(key, slice), key
            step = key.step or 1
            return FakeNamedArray((self._rows + step - 1) // step, named=False)

        def __array__(self, dtype=None, copy=None):
            import numpy as np

            arr = np.zeros((self._rows, 4), dtype=dtype or float)
            arr[:, 0] = np.arange(self._rows)
            return arr

    class FakeModel:
        def setIntegrator(self, _name):  # noqa: N802 - mirrors Tellurium's API
            pass

        @property
        def integrator(self):
            return type("I", (), {"seed": 0})()

        def simulate(self, _start, _end, points):
            # Comfortably past MAX_DOWNSAMPLE_POINTS so decimation runs.
            return FakeNamedArray(points)

    class FakeTe:
        @staticmethod
        def loada(_model_str):
            return FakeModel()

    original = sv.te
    sv.te = FakeTe()  # type: ignore[assignment]
    try:
        worker = sv.SimulateWorker(
            model_str="model circuit() end",
            method="gillespie",
            max_time=400,
            title="Dynamic Circuit Simulation (Stochastic Gillespie)",
        )
        captured: dict = {}
        worker.simulation_finished.connect(lambda p: captured.update(payload=p))
        worker.run()
    finally:
        sv.te = original  # type: ignore[assignment]

    assert "payload" in captured
    unpacked = msgpack.unpackb(captured["payload"], raw=False)

    assert unpacked["colnames"] == ["time", "[LacI]", "[cI]", "[TetR]"]
    # And the data really was decimated, so the names survived a slice.
    assert unpacked["shape"][0] <= sv.MAX_DOWNSAMPLE_POINTS


def test_methods_log_reports_the_integrated_duration_not_the_decimated_end():
    """Keeping every 2nd of 2000 points ends the plotted series at t = 399.8 for a
    400-minute run. The Methods paragraph must say 400.
    """
    import msgpack

    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState

    state = SynBioState()
    view = SimulateView(state=state)
    time_col = np.arange(0, 400, 0.2)  # 2000 points, decimated: last = 399.8
    arr = np.column_stack([time_col[::2], np.ones(1000)])
    payload = msgpack.packb(
        {
            "colnames": ["time", "[LacI]"],
            "arr_bytes": arr.astype(np.float64).tobytes(),
            "shape": list(arr.shape),
            "dtype": "float64",
            "method": "gillespie",
            "title": "t",
            "sim_duration_ms": 1.0,
            "max_time": 400,
        }
    )
    view._on_simulation_finished(payload)

    entry = next(e for e in state.methods_log if e["kind"] == "tellurium_ssa")
    assert entry["parameters"]["duration"] == "400 min"
    view.deleteLater()

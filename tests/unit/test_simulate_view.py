"""Unit tests for the SimulateView UI layout and species filtering logic."""

import sys
from unittest.mock import MagicMock

import numpy as np

# Mock sbol3 if not present
if "sbol3" not in sys.modules:
    sys.modules["sbol3"] = MagicMock()

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QSplitter

from ui.views.simulate_view import SimulateView

# Ensure QApplication instance exists for PyQt widget tests
app = QApplication.instance() or QApplication([])


def test_simulate_view_layout_setup():
    """Test that SimulateView initializes with QSplitter and species QListWidget."""
    view = SimulateView()

    assert hasattr(view, "splitter")
    assert isinstance(view.splitter, QSplitter)
    assert hasattr(view, "species_list")
    assert isinstance(view.species_list, QListWidget)
    assert hasattr(view, "select_all_btn")
    assert hasattr(view, "clear_all_btn")


def test_species_list_filtering_and_plot_update():
    """Test species list check state toggling and interactive plot update."""
    view = SimulateView()

    # Mock simulation result object
    class MockResult:
        colnames = ["time", "[LacI]", "[TetR]"]

        def __getitem__(self, item):
            if item == "time":
                return np.array([0, 1, 2, 3, 4, 5])
            elif item in ("[LacI]", "LacI"):
                return np.array([10, 8, 6, 4, 2, 0])
            elif item in ("[TetR]", "TetR"):
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
    assert len(view.figure.axes[0].get_lines()) == 2

    # Uncheck one item (TetR)
    view.species_list.item(1).setCheckState(Qt.CheckState.Unchecked)
    view.update_plot()
    ax = view.figure.axes[0]
    assert len(ax.get_lines()) == 1
    assert ax.get_lines()[0].get_label() == "LacI"

    # Select all helper
    view._select_all_species()
    assert len(view.figure.axes[0].get_lines()) == 2

    # Clear all helper
    view._clear_all_species()
    assert len(view.figure.axes[0].get_lines()) == 0

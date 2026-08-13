"""PyQt6 Predictive Circuit Simulation View with PyQtGraph Time-Series Plotter.

Provides preset selection (Repressilator, Toggle Switch, NOR gate),
numerical parameter controls, and PyQtGraph dynamic GPU-accelerated
expression plotting over time. Decoupled from engines via
CircuitSimulationController signals & slots.
"""

from __future__ import annotations

from typing import List, Optional
import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
    SimulationParameters,
    SimulationResult,
)
from ...analysis.simulation.circuit_engine import CircuitSimulationEngine
from ...analysis.state import SynBioState
from ..controllers.circuit_controller import CircuitSimulationController

try:
    from biopro.ui.theme import Colors, Fonts, theme_manager
except ImportError:
    try:
        from biopro_sdk.plugin.theme_fallback import Colors, Fonts, theme_manager
    except ImportError:

        class Colors:
            BG_DARKEST = "#0d1117"
            BG_DARK = "#161b22"
            BG_MEDIUM = "#21262d"
            FG_PRIMARY = "#e6edf3"
            FG_SECONDARY = "#8b949e"
            FG_DISABLED = "#484f58"
            BORDER = "#30363d"
            ACCENT_PRIMARY = "#00bcd4"

        class Fonts:
            SIZE_SMALL = 11

        class _DummySignal:
            def connect(self, cb):
                pass

        class _DummyThemeManager:
            theme_changed = _DummySignal()

        theme_manager = _DummyThemeManager()


class CircuitSimulationView(QWidget):
    """PyQt6 View for predictive genetic circuit kinetic simulation
    and PyQtGraph plotting with dynamic theme support.
    """

    simulation_requested = pyqtSignal(list, list, object)

    def __init__(
        self,
        state: Optional[SynBioState] = None,
        controller: Optional[CircuitSimulationController] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.state = state if state is not None else SynBioState()
        self.controller = (
            controller
            if controller is not None
            else CircuitSimulationController(self.state)
        )

        self._active_components: List[CircuitComponent] = []
        self._active_edges: List[CircuitEdge] = []

        self._init_ui()
        self._connect_signals()

        # Connect global theme change signal
        theme_manager.theme_changed.connect(self.refresh_styles)

        # Load default Repressilator preset
        self._load_preset("Repressilator (3-Gene Oscillator)")

    def _init_ui(self):
        self.setObjectName("circuit_simulation_view")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Control Panel: Preset selector & parameters
        left_widget = QGroupBox("Circuit Simulation Parameters")
        left_layout = QVBoxLayout(left_widget)

        form = QFormLayout()

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(
            [
                "Repressilator (3-Gene Oscillator)",
                "Genetic Toggle Switch",
                "Single Inverter (NOT Gate)",
            ]
        )
        self.preset_combo.currentTextChanged.connect(self._load_preset)
        form.addRow("Circuit Preset:", self.preset_combo)

        self.t_end_spin = QDoubleSpinBox()
        self.t_end_spin.setRange(10.0, 1000.0)
        self.t_end_spin.setValue(100.0)
        self.t_end_spin.setSuffix(" min")
        form.addRow("Sim Time (t_end):", self.t_end_spin)

        self.num_points_spin = QSpinBox()
        self.num_points_spin.setRange(100, 5000)
        self.num_points_spin.setValue(500)
        form.addRow("Time Points:", self.num_points_spin)

        self.hill_n_spin = QDoubleSpinBox()
        self.hill_n_spin.setRange(1.0, 5.0)
        self.hill_n_spin.setValue(2.1)
        self.hill_n_spin.setSingleStep(0.1)
        form.addRow("Hill Coeff (n):", self.hill_n_spin)

        self.solver_combo = QComboBox()
        self.solver_combo.addItems(["RK45", "Radau", "BDF", "LSODA"])
        form.addRow("ODE Solver:", self.solver_combo)

        left_layout.addLayout(form)

        self.btn_run_sim = QPushButton("▶ Run Predictive Simulation")
        self.btn_run_sim.clicked.connect(self._on_run_sim_clicked)
        left_layout.addWidget(self.btn_run_sim)

        left_layout.addStretch()
        splitter.addWidget(left_widget)

        # Right Panel: PyQtGraph GPU-Accelerated Visualization Widget
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOption("antialias", True)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.addLegend(offset=(10, 10))

        right_layout.addWidget(self.plot_widget)

        splitter.addWidget(right_widget)
        splitter.setSizes([260, 640])

        layout.addWidget(splitter)

        self.refresh_styles()

    def refresh_styles(self) -> None:
        """Dynamically update PyQtGraph background and UI styling on theme change."""
        bg_color = self.palette().color(QPalette.ColorRole.Base).name()
        fg_color = self.palette().color(QPalette.ColorRole.WindowText).name()

        self.plot_widget.setBackground(bg_color)
        axis_pen = pg.mkPen(color=fg_color, width=1)

        for axis_name in ("left", "bottom", "top", "right"):
            axis = self.plot_widget.getPlotItem().getAxis(axis_name)
            axis.setPen(axis_pen)
            axis.setTextPen(axis_pen)

        title_color = (
            Colors.ACCENT_PRIMARY
            if hasattr(Colors, "ACCENT_PRIMARY")
            else fg_color
        )
        self.plot_widget.setTitle(
            "Predicted Protein & RNA Expression Levels Over Time",
            color=title_color,
            size="12pt",
        )
        self.plot_widget.setLabel("left", "Concentration (RPU / au)", color=fg_color)
        self.plot_widget.setLabel("bottom", "Time (minutes)", color=fg_color)

        view_qss = f"""
            QComboBox {{
                background: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: none;
            }}
            QComboBox::down-arrow {{
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {Colors.FG_PRIMARY};
                margin-right: 6px;
            }}
            QSplitter::handle {{
                background-color: {Colors.BORDER};
            }}
            QSplitter::handle:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
            }}
        """
        self.setStyleSheet(view_qss)

    def _connect_signals(self):
        # Connect View -> Controller
        self.simulation_requested.connect(self.controller.handle_simulation_request)

        # Connect Controller -> View
        self.controller.simulation_ready.connect(self.render_simulation_results)
        self.controller.error_raised.connect(self._show_error)

    def _load_preset(self, preset_name: str):
        if preset_name == "Repressilator (3-Gene Oscillator)":
            self._active_components, self._active_edges = (
                CircuitSimulationEngine.create_preset_repressilator()
            )
        elif preset_name == "Genetic Toggle Switch":
            c1 = CircuitComponent(
                id="LacI",
                name="LacI",
                component_type="cds",
                y_min=0.001,
                y_max=10.0,
                K_d=1.0,
                n=2.0,
                degradation_rate=0.15,
                initial_concentration=5.0,
            )
            c2 = CircuitComponent(
                id="TetR",
                name="TetR",
                component_type="cds",
                y_min=0.001,
                y_max=10.0,
                K_d=1.0,
                n=2.0,
                degradation_rate=0.15,
                initial_concentration=0.0,
            )
            edges = [
                CircuitEdge(
                    source_id="LacI", target_id="TetR", interaction_type="repression"
                ),
                CircuitEdge(
                    source_id="TetR", target_id="LacI", interaction_type="repression"
                ),
            ]
            self._active_components = [c1, c2]
            self._active_edges = edges
        elif preset_name == "Single Inverter (NOT Gate)":
            c1 = CircuitComponent(
                id="Repressor",
                name="Repressor",
                component_type="cds",
                y_min=0.001,
                y_max=8.0,
                K_d=1.0,
                n=2.0,
                degradation_rate=0.2,
                initial_concentration=2.0,
            )
            c2 = CircuitComponent(
                id="GFP",
                name="GFP Reporter",
                component_type="cds",
                y_min=0.01,
                y_max=10.0,
                K_d=1.0,
                n=2.0,
                degradation_rate=0.05,
                initial_concentration=0.1,
            )
            edges = [
                CircuitEdge(
                    source_id="Repressor",
                    target_id="GFP",
                    interaction_type="repression",
                )
            ]
            self._active_components = [c1, c2]
            self._active_edges = edges

    def _on_run_sim_clicked(self):
        # Update Hill n on components
        hill_n = self.hill_n_spin.value()
        for comp in self._active_components:
            comp.n = hill_n

        params = SimulationParameters(
            t_start=0.0,
            t_end=self.t_end_spin.value(),
            num_points=self.num_points_spin.value(),
            solver_method=self.solver_combo.currentText(),
        )

        self.simulation_requested.emit(
            self._active_components, self._active_edges, params
        )

    @pyqtSlot(SimulationResult)
    def render_simulation_results(self, result: SimulationResult):
        """Plots time-series curves on PyQtGraph PlotWidget."""
        self.plot_widget.clear()
        self.plot_widget.addLegend(offset=(10, 10))

        if not result.success:
            self._show_error(result.status_message)
            return

        t_points = result.time_points
        color_palette = [
            "#38BDF8",  # Sky Blue
            "#F43F5E",  # Rose Red
            "#34D399",  # Emerald Green
            "#F59E0B",  # Amber
            "#A855F7",  # Purple
        ]

        for idx, (species_name, conc_values) in enumerate(
            result.species_concentrations.items()
        ):
            color = color_palette[idx % len(color_palette)]
            pen = pg.mkPen(color=color, width=2.5)
            self.plot_widget.plot(t_points, conc_values, name=species_name, pen=pen)

    @pyqtSlot(str)
    def _show_error(self, message: str):
        QMessageBox.critical(self, "Simulation Engine Error", message)

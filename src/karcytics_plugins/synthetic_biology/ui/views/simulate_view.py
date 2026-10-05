"""Simulation view for plotting ODE and Gillespie kinetic simulations."""

# Matplotlib PyQt6 integration
import matplotlib
import numpy as np
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot  # noqa: TID251
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from ...analysis.parts.components import CDS, Promoter, sgRNA
from ...analysis.prediction.graphing_utils import apply_standard_axes

MAX_DOWNSAMPLE_POINTS = 1000


class SimulateWorker(QThread):
    """Background worker QThread executing Tellurium ODE / Gillespie numerical
    simulation routines completely off the main GUI thread.
    """

    simulation_finished = pyqtSignal(dict)
    simulation_error = pyqtSignal(str)

    def __init__(
        self,
        model_str: str,
        method: str,
        max_time: int,
        title: str,
        parent=None,
    ):
        super().__init__(parent)
        self.model_str = model_str
        self.method = method
        self.max_time = max_time
        self.title = title

    def run(self) -> None:
        """Executes non-blocking numerical integration without touching Matplotlib GUI."""
        try:
            import tellurium as te

            r = te.loada(self.model_str)
            if self.method == "gillespie":
                r.setIntegrator("gillespie")
                r.integrator.seed = int(np.random.randint(1000000))
                result = r.simulate(0, self.max_time, self.max_time * 5)
            else:
                result = r.simulate(0, self.max_time, self.max_time * 2)

            # Data Decimation (Downsampling): reduce data points if time steps exceed MAX_DOWNSAMPLE_POINTS
            if result is not None and len(result) > MAX_DOWNSAMPLE_POINTS:
                step = len(result) // MAX_DOWNSAMPLE_POINTS
                result = result[::step]

            payload = {
                "result": result,
                "method": self.method,
                "title": self.title,
            }
            self.simulation_finished.emit(payload)
        except Exception as e:
            self.simulation_error.emit(str(e))


class SafeFigureCanvasQTAgg(FigureCanvasQTAgg):
    """Subclass of FigureCanvasQTAgg guarding against 0-dimension canvas drawing
    that triggers Matplotlib C++ Agg backend Invalid affine transformation matrix
    segfaults.
    """

    def _is_dimension_valid(self) -> bool:
        if self.width() <= 1 or self.height() <= 1:
            return False
        if hasattr(self, "figure") and self.figure is not None:
            bbox = getattr(self.figure, "bbox", None)
            if bbox is not None and (bbox.width <= 1 or bbox.height <= 1):
                return False
        return True

    def draw(self):
        if not self._is_dimension_valid():
            return
        try:
            super().draw()
        except ValueError as e:
            if "Invalid affine transformation matrix" in str(e):
                return
            raise

    def paintEvent(self, event):
        if not self._is_dimension_valid():
            return
        try:
            super().paintEvent(event)
        except ValueError as e:
            if "Invalid affine transformation matrix" in str(e):
                return
            raise

    def resizeEvent(self, event):
        if event.size().width() <= 1 or event.size().height() <= 1:
            return
        try:
            super().resizeEvent(event)
        except ValueError as e:
            if "Invalid affine transformation matrix" in str(e):
                return
            raise


class SimulateView(QWidget):
    """Central view for running and plotting mathematical simulations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parts = []
        self._last_simulation_result = None
        self._last_simulation_method = None
        self._last_simulation_title = None
        self._active_worker: SimulateWorker | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Info Label
        self.info_label = QLabel(
            "Run kinetic simulations (Deterministic ODE or Stochastic Gillespie)."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        # Main Splitter: Canvas Container on left (80%), Control Panel on right (20%)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter, 1)

        # Left Container: Matplotlib Plot Canvas with Static Constrained Layout
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(8, 6), dpi=100, layout="constrained")
        self.canvas = SafeFigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumSize(100, 100)
        canvas_layout.addWidget(self.canvas, 1)

        self.splitter.addWidget(canvas_container)

        # Right Container: Control Panel with Species Selector ListWidget
        self.control_panel = QWidget()
        control_layout = QVBoxLayout(self.control_panel)
        control_layout.setContentsMargins(8, 0, 0, 0)
        control_layout.setSpacing(8)

        self.species_header = QLabel("Species / Molecule Filter")
        self.species_header.setStyleSheet("font-weight: bold; font-size: 13px;")

        self.species_list = QListWidget()
        self.species_list.itemChanged.connect(self._on_species_item_changed)

        control_layout.addWidget(self.species_header)
        control_layout.addWidget(self.species_list, 1)

        # Quick Selection Action Buttons
        btn_box = QHBoxLayout()
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all_species)
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.clicked.connect(self._clear_all_species)
        btn_box.addWidget(self.select_all_btn)
        btn_box.addWidget(self.clear_all_btn)
        control_layout.addLayout(btn_box)

        self.splitter.addWidget(self.control_panel)

        # Configure Splitter initial sizes: 80% left canvas (800px), 20% right panel (200px)
        self.splitter.setSizes([800, 200])

        # Initially hide species selector until a time-series simulation is run
        self.control_panel.setVisible(False)

        # Eager Initialization (Pre-warming): Instantiate default axes and pre-draw blank canvas in __init__
        self.ax = self.figure.add_subplot(111)
        self.ax.text(
            0.5,
            0.5,
            "Run a kinetic simulation to plot time-series traces.",
            ha="center",
            va="center",
            color="#8b949e",
            fontsize=11,
        )
        self.ax.set_xlim(-0.1, 1.1)
        self.ax.set_ylim(-0.1, 1.1)
        for spine in self.ax.spines.values():
            spine.set_color("#30363d")
        self.ax.set_facecolor("#0d1117")
        self.canvas.draw()

        # Apply dark theme
        self._apply_theme()

    def refresh_styles(self) -> None:
        """Alias for _apply_theme for theme update signals."""
        self._apply_theme()

    def _apply_theme(self):
        from karcytics_sdk.plugin.theme_fallback import Colors, Fonts

        dark_bg = getattr(Colors, "BG_DARKEST", "#0d1117")
        dark_panel = getattr(Colors, "BG_DARK", "#161b22")
        fg_pri = getattr(Colors, "FG_PRIMARY", "#c9d1d9")
        fg_sec = getattr(Colors, "FG_SECONDARY", "#8b949e")
        border = getattr(Colors, "BORDER", "#30363d")
        accent = getattr(Colors, "ACCENT_PRIMARY", "#00bcd4")

        try:
            font_sz = int(str(getattr(Fonts, "SIZE_SMALL", 12)).replace("px", "")) + 2
        except (ValueError, TypeError, AttributeError):
            font_sz = 14

        self.figure.patch.set_facecolor(dark_bg)
        self.canvas.setStyleSheet(f"background-color: {dark_bg};")
        self.info_label.setStyleSheet(f"color: {fg_sec}; font-size: {font_sz}px;")
        self.species_header.setStyleSheet(f"color: {fg_pri}; font-weight: bold; font-size: 13px;")

        self.species_list.setStyleSheet(
            f"QListWidget {{ background: {dark_panel}; color: {fg_pri}; "
            f"border: 1px solid {border}; border-radius: 4px; padding: 4px; }}"
            f"QListWidget::item {{ padding: 6px; "
            f"border-bottom: 1px solid {border}; }}"
            f"QListWidget::item:hover {{ background: {dark_bg}; }}"
        )
        btn_style = (
            f"background: {dark_panel}; color: {accent}; "
            f"border: 1px solid {accent}; font-size: 11px; font-weight: bold; "
            f"padding: 4px; border-radius: 3px;"
        )
        self.select_all_btn.setStyleSheet(btn_style)
        self.clear_all_btn.setStyleSheet(btn_style)

        if hasattr(self, "splitter"):
            self.splitter.setStyleSheet(
                f"QSplitter::handle {{ background-color: {border}; }}"
                f"QSplitter::handle:horizontal {{ width: 2px; }}"
                f"QSplitter::handle:hover {{ background-color: {accent}; }}"
            )

    def set_parts(self, parts: list):
        """Update the active parts available for simulation."""
        self._parts = parts

    def _on_species_item_changed(self, item):
        """Redraw plot instantly when a user checks/unchecks a species item."""
        self.update_plot()

    def _select_all_species(self):
        """Check all species items in the list widget."""
        self.species_list.blockSignals(True)
        for i in range(self.species_list.count()):
            self.species_list.item(i).setCheckState(Qt.CheckState.Checked)
        self.species_list.blockSignals(False)
        self.update_plot()

    def _clear_all_species(self):
        """Uncheck all species items in the list widget."""
        self.species_list.blockSignals(True)
        for i in range(self.species_list.count()):
            self.species_list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.species_list.blockSignals(False)
        self.update_plot()

    def _render_invalid_simulation_error(self, ax):
        """Helper to clear figure and display clean UI warning message when invalid
        data (empty, NaN, inf) is encountered.
        """
        self.figure.clear()
        err_ax = self.figure.add_subplot(111)
        err_ax.text(
            0.5,
            0.5,
            "Simulation generated invalid or infinite values. Check kinetic parameters.",
            ha="center",
            va="center",
            color="red",
            fontsize=12,
        )
        err_ax.set_xlim(-0.1, 1.1)
        err_ax.set_ylim(-0.1, 1.1)
        self.canvas.draw()

    def update_plot(self):  # noqa: PLR0915
        """Redraw the simulation figure on the matplotlib canvas based on species
        selection.
        """
        if self._last_simulation_result is None:
            return

        result = self._last_simulation_result
        method = self._last_simulation_method or "ode"
        title = self._last_simulation_title or "Dynamic Circuit Simulation"

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # Read check states from species_list
        checked_columns = []
        for i in range(self.species_list.count()):
            item = self.species_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                col_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
                checked_columns.append((item.text(), col_name))

        if not checked_columns:
            ax.text(
                0.5,
                0.5,
                "No species selected.\nCheck items in the right-hand panel to view traces.",
                ha="center",
                va="center",
                color="white",
                fontsize=12,
            )
            ax.set_xlim(-0.1, 1.1)
            ax.set_ylim(-0.1, 1.1)
            self.canvas.draw()
            return

        # Fetch and sanitize time array
        try:
            raw_t = result["time"]
        except Exception:
            self._render_invalid_simulation_error(ax)
            return

        t_arr = np.asarray(raw_t, dtype=float)
        if t_arr.size == 0 or not np.all(np.isfinite(t_arr)):
            self._render_invalid_simulation_error(ax)
            return

        # Fetch and sanitize concentration arrays
        valid_traces = []
        for display_name, col_name in checked_columns:
            if (
                hasattr(result, "colnames")
                and col_name in result.colnames
                or hasattr(result, "__getitem__")
                and col_name in result
            ):
                data_y = result[col_name]
            else:
                continue

            y_arr = np.asarray(data_y, dtype=float)
            if y_arr.size == 0 or not np.all(np.isfinite(y_arr)):
                self._render_invalid_simulation_error(ax)
                return

            valid_traces.append((display_name, y_arr))

        if not valid_traces:
            ax.text(
                0.5,
                0.5,
                "No valid species data found to plot.",
                ha="center",
                va="center",
                color="white",
                fontsize=12,
            )
            ax.set_xlim(-0.1, 1.1)
            ax.set_ylim(-0.1, 1.1)
            self.canvas.draw()
            return

        palette = [
            "#00bcd4",
            "#4caf50",
            "#ff9800",
            "#e91e63",
            "#9c27b0",
            "#03a9f4",
            "#ff5722",
            "#8bc34a",
        ]

        for idx, (display_name, y_arr) in enumerate(valid_traces):
            color = palette[idx % len(palette)]
            lw = 1.0 if method == "gillespie" else 2.0

            ax.plot(
                t_arr,
                y_arr,
                label=display_name,
                color=color,
                linewidth=lw,
            )

        x_label = "Time (seconds)"
        y_label = "Concentration" if method == "ode" else "Molecule Count"

        try:
            apply_standard_axes(
                ax=ax,
                fig=self.figure,
                x_label=x_label,
                y_label=y_label,
                title=title,
            )
        except Exception:
            for spine in ax.spines.values():
                spine.set_color("#30363d")
            ax.set_facecolor("#0d1117")

        # Enforce non-identical axis limits to prevent singular transformation matrix
        xmin, xmax = ax.get_xlim()
        if np.isnan(xmin) or np.isnan(xmax) or np.isinf(xmin) or np.isinf(xmax):
            xmin, xmax = 0.0, 1.0
        if xmin == xmax:
            delta = 1.0 if xmin == 0.0 else abs(xmin) * 0.1
            xmin -= delta
            xmax += delta
        ax.set_xlim(xmin, xmax)

        ymin, ymax = ax.get_ylim()
        if np.isnan(ymin) or np.isnan(ymax) or np.isinf(ymin) or np.isinf(ymax):
            ymin, ymax = 0.0, 1.0
        if ymin == ymax:
            delta = 1.0 if ymin == 0.0 else abs(ymin) * 0.1
            ymin -= delta
            ymax += delta
        ax.set_ylim(ymin, ymax)

        self.canvas.draw()

    @pyqtSlot(dict)
    def _on_simulation_finished(self, payload: dict) -> None:
        """Callback slot handling successful Tellurium calculation from QThread worker.
        Executes strictly on the Main Qt GUI thread.
        """
        result = payload.get("result")
        method = payload.get("method", "ode")
        title = payload.get("title", "Dynamic Circuit Simulation")

        self._last_simulation_result = result
        self._last_simulation_method = method
        self._last_simulation_title = title

        # Populate Species Selector ListWidget
        self.control_panel.setVisible(True)
        self.species_list.blockSignals(True)
        self.species_list.clear()

        colnames = getattr(result, "colnames", [])
        for col in colnames[1:]:
            clean_name = col.replace("[", "").replace("]", "")
            item = QListWidgetItem(clean_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, col)
            self.species_list.addItem(item)

        self.species_list.blockSignals(False)

        # Render selected traces on canvas safely on main GUI thread
        self.update_plot()

    @pyqtSlot(str)
    def _on_simulation_error(self, err_msg: str) -> None:
        """Callback slot handling calculation errors from background QThread worker.
        Executes strictly on the Main Qt GUI thread.
        """
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            f"Simulation Error:\n{err_msg}",
            ha="center",
            va="center",
            color="red",
            fontsize=10,
        )
        self.canvas.draw()

    def plot_time_series(self, max_time: int = 1000, method: str = "ode"):  # noqa: PLR0915
        """Run and plot a dynamic ODE or Stochastic simulation using Tellurium."""
        method_name = (
            "Time-Series Simulation (ODE)"
            if method == "ode"
            else "Stochastic Simulation (Gillespie)"
        )
        self.info_label.setText(
            f"<b>{method_name}:</b> Shows how the concentrations of your genetic "
            "circuit components change dynamically over time as proteins are "
            "produced and degraded."
        )

        try:
            import tellurium as te  # noqa: F401
        except ImportError:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                "Tellurium is not installed. Run 'pip install tellurium'.",
                ha="center",
                va="center",
                color="red",
                fontsize=12,
            )
            self.canvas.draw()
            return

        promoters = [p for p in self._parts if isinstance(p, Promoter)]
        cdss = [c for c in self._parts if isinstance(c, (CDS, sgRNA))]

        if not promoters or not cdss:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.text(
                0.5,
                0.5,
                "Circuit requires at least one Promoter and one CDS.",
                ha="center",
                va="center",
                color="white",
                fontsize=12,
            )
            self.canvas.draw()
            return

        # 1. Generate an Antimony Model string dynamically
        antimony_lines = ["model circuit()"]

        current_promoter = None
        products = set()

        # Track initial conditions (give the first product a kick to start oscillators)
        is_first_product = True

        for part in self._parts:
            if isinstance(part, Promoter):
                current_promoter = part
            elif isinstance(part, (CDS, sgRNA)) and current_promoter:
                product_name = getattr(
                    part, "product", part.name.replace(" ", "_").replace("-", "_")
                )
                if not product_name:
                    product_name = f"Protein_{part.id}"

                products.add(product_name)

                # Determine Promoter Equation
                reps = getattr(current_promoter, "repressors", [])
                y_min = current_promoter.y_min if current_promoter.y_min is not None else 0.0
                y_max = current_promoter.y_max if current_promoter.y_max is not None else 1.0
                K_d = current_promoter.K_d if current_promoter.K_d is not None else 0.1
                n = current_promoter.n if current_promoter.n is not None else 2.0

                if reps:
                    rep_name = reps[0]  # primary repressor
                    equation = f"{y_min} + ({y_max} - {y_min}) / (1 + ({rep_name} / {K_d})^{n})"
                else:
                    equation = f"{y_max}"  # Constitutive

                deg_rate = part.degradation_rate if part.degradation_rate is not None else 0.01

                # Species Definition
                init_val = 10 if is_first_product else 0
                if method == "gillespie":
                    init_val = init_val * 10
                antimony_lines.append(f"  species {product_name} = {init_val};")
                is_first_product = False

                # Reactions
                antimony_lines.append(f"  J_prod_{product_name}: => {product_name}; {equation};")
                antimony_lines.append(
                    f"  J_deg_{product_name}: {product_name} => ; {deg_rate} * {product_name};"
                )

        antimony_lines.append("end")
        model_str = "\n".join(antimony_lines)
        title = (
            "Dynamic Circuit Simulation (Stochastic Gillespie)"
            if method == "gillespie"
            else "Dynamic Circuit Simulation (Deterministic ODE)"
        )

        # Render immediate visual feedback on canvas while worker performs JIT compilation
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            "⚡ Computing ODE Kinetic Simulation (LSODA / Tellurium)...\nPlease wait...",
            ha="center",
            va="center",
            color="#00bcd4",
            fontsize=12,
            fontweight="bold",
        )
        ax.set_xlim(-0.1, 1.1)
        ax.set_ylim(-0.1, 1.1)
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.set_facecolor("#0d1117")
        self.canvas.draw()

        # 2. Launch background calculation worker (decoupled from GUI thread)
        if self._active_worker is not None and self._active_worker.isRunning():
            self._active_worker.terminate()
            self._active_worker.wait()

        self._active_worker = SimulateWorker(
            model_str=model_str,
            method=method,
            max_time=max_time,
            title=title,
        )
        self._active_worker.simulation_finished.connect(self._on_simulation_finished)
        self._active_worker.simulation_error.connect(self._on_simulation_error)
        self._active_worker.start()

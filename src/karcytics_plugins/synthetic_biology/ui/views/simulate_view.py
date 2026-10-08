"""Simulation view for plotting ODE and Gillespie kinetic simulations with PyQtGraph and msgpack IPC."""

from __future__ import annotations

import time
from typing import Any

import matplotlib
import msgpack  # type: ignore[import-untyped]
import numpy as np
import pyqtgraph as pg
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

try:
    import tellurium as te
except ImportError:
    te = None

from ...analysis.parts.components import CDS, Promoter, sgRNA
from ...analysis.prediction.graphing_utils import apply_standard_axes  # noqa: F401

MAX_DOWNSAMPLE_POINTS = 1000


class SimulateWorker(QThread):
    """Background worker QThread executing Tellurium ODE / Gillespie numerical
    simulation routines completely off the main GUI thread.
    Serializes array payloads using msgpack binary format.
    """

    simulation_finished = pyqtSignal(object)  # Emits bytes (msgpack) or dict
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
        """Executes non-blocking numerical integration off the main thread."""
        try:
            t_sim_start = time.perf_counter()

            if te is None:
                raise RuntimeError("Tellurium is not installed.")

            r = te.loada(self.model_str)
            if self.method == "gillespie":
                r.setIntegrator("gillespie")
                r.integrator.seed = int(np.random.randint(1000000))
                result = r.simulate(0, self.max_time, self.max_time * 5)
            else:
                result = r.simulate(0, self.max_time, self.max_time * 2)

            t_sim_end = time.perf_counter()
            sim_ms = (t_sim_end - t_sim_start) * 1000

            # Data Decimation (Downsampling): reduce data points if time steps exceed MAX_DOWNSAMPLE_POINTS
            if result is not None and len(result) > MAX_DOWNSAMPLE_POINTS:
                step = len(result) // MAX_DOWNSAMPLE_POINTS
                result = result[::step]

            # Fast Binary Serialization with Msgpack
            t_ser_start = time.perf_counter()
            colnames = list(result.colnames) if hasattr(result, "colnames") else []
            arr = np.asarray(result, dtype=np.float64)

            packed_payload = msgpack.packb(
                {
                    "colnames": colnames,
                    "arr_bytes": arr.tobytes(),
                    "shape": list(arr.shape),
                    "dtype": str(arr.dtype),
                    "method": self.method,
                    "title": self.title,
                    "sim_duration_ms": sim_ms,
                }
            )
            t_ser_end = time.perf_counter()
            ser_ms = (t_ser_end - t_ser_start) * 1000

            print(  # noqa: T201
                f"[PROFILING] Worker Sim Time: {sim_ms:.2f} ms | "
                f"Msgpack Serialization: {ser_ms:.2f} ms | "
                f"Payload Size: {len(packed_payload)} bytes"
            )
            self.simulation_finished.emit(packed_payload)
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
    """Central view for running and plotting mathematical simulations using PyQtGraph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parts = []
        self._last_simulation_result = None
        self._last_simulation_method = None
        self._last_simulation_title = None
        self._active_worker: SimulateWorker | None = None
        self._setup_ui()

    def _setup_ui(self):  # noqa: PLR0915
        t0 = time.perf_counter()
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

        # Left Container: PyQtGraph GPU-Accelerated Plot Widget
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

        pg.setConfigOption("antialias", True)
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setBackground("#0d1117")
        self.legend = self.plot_widget.addLegend(offset=(-10, 10))
        if self.legend:
            self.legend.anchor((1, 0), (1, 0))
            self.legend.setBrush(pg.mkBrush(color=(30, 30, 30, 220)))

        self.plot_widget.setMinimumSize(100, 100)
        canvas_layout.addWidget(self.plot_widget, 1)

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

        # Eager Initialization (Pre-warming): set default title and labels
        self.plot_widget.setTitle(
            "<span style='color: #8b949e; font-size: 13px;'>"
            "Run a kinetic simulation to plot time-series traces.</span>"
        )
        self.plot_widget.setLabel("bottom", "Time (seconds)", color="#8b949e")
        self.plot_widget.setLabel("left", "Concentration", color="#8b949e")

        # Matplotlib compatibility fallback attributes for tests/inspectors if referenced
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = SafeFigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)

        # Apply dark theme
        self._apply_theme()
        t1 = time.perf_counter()
        print(f"[PROFILING] SimulateView UI Setup Time: {(t1 - t0) * 1000:.2f} ms")  # noqa: T201

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

        self.plot_widget.setBackground(dark_bg)
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

    def _render_invalid_simulation_error(
        self,
        message: str = "Simulation generated invalid or infinite values. Check kinetic parameters.",
    ):
        """Helper to clear figure and display clean UI warning message when invalid
        data (empty, NaN, inf) is encountered.
        """
        self.plot_widget.clear()
        self.plot_widget.setTitle(
            f"<span style='color: #ff5555; font-weight: bold; font-size: 13px;'>{message}</span>"
        )

    def update_plot(self):  # noqa: PLR0915
        """Redraw the simulation traces on the PyQtGraph widget based on species selection."""
        t_render_start = time.perf_counter()

        if self._last_simulation_result is None:
            return

        result = self._last_simulation_result
        method = self._last_simulation_method or "ode"
        title = self._last_simulation_title or "Dynamic Circuit Simulation"

        self.plot_widget.clear()
        if hasattr(self, "legend") and self.legend is not None:
            self.legend.clear()

        # Read check states from species_list
        checked_columns = []
        for i in range(self.species_list.count()):
            item = self.species_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                col_name = item.data(Qt.ItemDataRole.UserRole) or item.text()
                checked_columns.append((item.text(), col_name))

        if not checked_columns:
            self.plot_widget.setTitle(
                "<span style='color: #8b949e; font-size: 13px;'>"
                "No species selected.<br/>Check items in the right-hand panel to view traces.</span>"
            )
            t_render_end = time.perf_counter()
            print(  # noqa: T201
                f"[PROFILING] PyQtGraph Render Step (Empty Selection): "
                f"{(t_render_end - t_render_start) * 1000:.2f} ms"
            )
            return

        # Fetch and sanitize time array
        try:
            if hasattr(result, "__getitem__"):
                raw_t = result["time"]
            elif isinstance(result, dict):
                raw_t = result.get("time", [])
            else:
                raw_t = getattr(result, "time", [])
        except Exception:
            self._render_invalid_simulation_error()
            return

        t_arr = np.asarray(raw_t, dtype=float)
        if t_arr.size == 0 or not np.all(np.isfinite(t_arr)):
            self._render_invalid_simulation_error()
            return

        # Fetch and sanitize concentration arrays
        valid_traces = []
        for display_name, col_name in checked_columns:
            data_y = None
            if hasattr(result, "colnames") and col_name in result.colnames:
                data_y = result[col_name]
            elif hasattr(result, "__getitem__"):
                try:
                    data_y = result[col_name]
                except (KeyError, TypeError, IndexError):
                    if display_name in result:
                        data_y = result[display_name]
            elif isinstance(result, dict):
                data_y = result.get(col_name, result.get(display_name))

            if data_y is None:
                continue

            y_arr = np.asarray(data_y, dtype=float)
            if y_arr.size == 0 or not np.all(np.isfinite(y_arr)):
                self._render_invalid_simulation_error()
                return

            valid_traces.append((display_name, y_arr))

        if not valid_traces:
            self.plot_widget.setTitle(
                "<span style='color: #8b949e; font-size: 13px;'>"
                "No valid species data found to plot.</span>"
            )
            t_render_end = time.perf_counter()
            print(  # noqa: T201
                f"[PROFILING] PyQtGraph Render Step (No Valid Traces): "
                f"{(t_render_end - t_render_start) * 1000:.2f} ms"
            )
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
            pen = pg.mkPen(color=color, width=1.5 if method == "gillespie" else 2.5)
            min_len = min(len(t_arr), len(y_arr))
            self.plot_widget.plot(
                t_arr[:min_len],
                y_arr[:min_len],
                name=display_name,
                pen=pen,
            )

        y_label = "Concentration" if method == "ode" else "Molecule Count"
        self.plot_widget.setTitle(
            f"<span style='color: #c9d1d9; font-weight: bold; font-size: 14px;'>{title}</span>"
        )
        self.plot_widget.setLabel("bottom", "Time (seconds)", color="#8b949e")
        self.plot_widget.setLabel("left", y_label, color="#8b949e")

        t_render_end = time.perf_counter()
        print(  # noqa: T201
            f"[PROFILING] PyQtGraph Render Step: "
            f"{(t_render_end - t_render_start) * 1000:.2f} ms ({len(valid_traces)} traces plotted)"
        )

    @pyqtSlot(object)
    def _on_simulation_finished(self, payload: object) -> None:  # noqa: PLR0915
        """Callback slot handling calculation result from QThread worker.
        Executes strictly on the Main Qt GUI thread.
        """
        t_deser_start = time.perf_counter()

        result_data: Any = None
        if isinstance(payload, bytes):
            unpacked = msgpack.unpackb(payload, raw=False)
            colnames = unpacked.get("colnames", [])
            arr_bytes = unpacked.get("arr_bytes", b"")
            shape = tuple(unpacked.get("shape", (0, 0)))
            dtype_str = unpacked.get("dtype", "float64")
            method = unpacked.get("method", "ode")
            title = unpacked.get("title", "Dynamic Circuit Simulation")
            sim_ms = unpacked.get("sim_duration_ms", 0.0)

            arr = np.frombuffer(arr_bytes, dtype=np.dtype(dtype_str)).reshape(shape)

            dict_res: dict[str, Any] = {}
            if colnames and arr.shape[1] >= len(colnames):
                for idx, col in enumerate(colnames):
                    dict_res[col] = arr[:, idx]
                    clean_name = col.replace("[", "").replace("]", "")
                    dict_res[clean_name] = arr[:, idx]
                dict_res["colnames"] = colnames
            else:
                dict_res["time"] = arr[:, 0] if arr.shape[1] > 0 else np.array([])
                for c_idx in range(1, arr.shape[1]):
                    dict_res[f"Species_{c_idx}"] = arr[:, c_idx]
                dict_res["colnames"] = list(dict_res.keys())

            result_data = dict_res
            t_deser_end = time.perf_counter()
            deser_ms = (t_deser_end - t_deser_start) * 1000
            print(  # noqa: T201
                f"[PROFILING] IPC Msgpack Deserialization: {deser_ms:.2f} ms | "
                f"Worker Simulation: {sim_ms:.2f} ms"
            )
        else:
            result_data = payload.get("result") if isinstance(payload, dict) else payload
            method = payload.get("method", "ode") if isinstance(payload, dict) else "ode"
            title = (
                payload.get("title", "Dynamic Circuit Simulation")
                if isinstance(payload, dict)
                else "Dynamic Circuit Simulation"
            )

        self._last_simulation_result = result_data
        self._last_simulation_method = str(method)
        self._last_simulation_title = str(title)

        # Populate Species Selector ListWidget
        self.control_panel.setVisible(True)
        self.species_list.blockSignals(True)
        self.species_list.clear()

        colnames = getattr(result_data, "colnames", [])
        if not colnames and isinstance(result_data, dict):
            colnames = result_data.get("colnames", list(result_data.keys()))

        time_col = "time"
        for col in colnames:
            if col.lower() == time_col:
                continue
            clean_name = col.replace("[", "").replace("]", "")
            item = QListWidgetItem(clean_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, col)
            self.species_list.addItem(item)

        self.species_list.blockSignals(False)

        # Render selected traces on pyqtgraph plot widget
        self.update_plot()

    @pyqtSlot(str)
    def _on_simulation_error(self, err_msg: str) -> None:
        """Callback slot handling calculation errors from background QThread worker.
        Executes strictly on the Main Qt GUI thread.
        """
        self.plot_widget.clear()
        self.plot_widget.setTitle(
            f"<span style='color: #ff5555; font-weight: bold; font-size: 12px;'>"
            f"Simulation Error:<br/>{err_msg}</span>"
        )

    def plot_time_series(self, max_time: int = 1000, method: str = "ode"):  # noqa: PLR0915
        """Run and plot a dynamic ODE or Stochastic simulation using Tellurium."""
        t_click_start = time.perf_counter()
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

        if te is None:
            self.plot_widget.clear()
            self.plot_widget.setTitle(
                "<span style='color: #ff5555; font-weight: bold; font-size: 13px;'>"
                "Tellurium is not installed. Run 'pip install tellurium'.</span>"
            )
            return

        promoters = [p for p in self._parts if isinstance(p, Promoter)]
        cdss = [c for c in self._parts if isinstance(c, (CDS, sgRNA))]

        if not promoters or not cdss:
            self.plot_widget.clear()
            self.plot_widget.setTitle(
                "<span style='color: #c9d1d9; font-size: 13px;'>"
                "Circuit requires at least one Promoter and one CDS.</span>"
            )
            return

        # Generate Antimony Model string dynamically
        antimony_lines = ["model circuit()"]

        current_promoter = None
        products = set()

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
                    rep_name = reps[0]
                    equation = f"{y_min} + ({y_max} - {y_min}) / (1 + ({rep_name} / {K_d})^{n})"
                else:
                    equation = f"{y_max}"

                deg_rate = part.degradation_rate if part.degradation_rate is not None else 0.01

                init_val = 10 if is_first_product else 0
                if method == "gillespie":
                    init_val = init_val * 10
                antimony_lines.append(f"  species {product_name} = {init_val};")
                is_first_product = False

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

        # Render immediate visual feedback on plot widget while worker computes simulation off-thread
        self.plot_widget.clear()
        self.plot_widget.setTitle(
            "<span style='color: #00bcd4; font-weight: bold; font-size: 13px;'>"
            "⚡ Computing ODE Kinetic Simulation (LSODA / Tellurium)... Please wait...</span>"
        )

        t_prep_end = time.perf_counter()
        print(  # noqa: T201
            f"[PROFILING] Simulate Tab Click -> Antimony Model Generation: "
            f"{(t_prep_end - t_click_start) * 1000:.2f} ms"
        )

        # Launch background calculation worker
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

    def teardown(self) -> None:
        """Stops active background worker thread if running."""
        if self._active_worker is not None and self._active_worker.isRunning():
            self._active_worker.requestInterruption()
            self._active_worker.quit()
            self._active_worker.wait(1000)
            self._active_worker = None

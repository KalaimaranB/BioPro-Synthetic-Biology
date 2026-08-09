"""Simulation view for plotting steady-state curves and ODEs with species filtering."""

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter,
    QListWidget, QListWidgetItem, QPushButton
)

# Matplotlib PyQt6 integration
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

try:
    from ...analysis.parts.components import Promoter, CDS, sgRNA
except ImportError:
    try:
        from analysis.parts.components import Promoter, CDS, sgRNA
    except ImportError:
        from biopro.plugins.synthetic_biology.analysis.parts.components import Promoter, CDS, sgRNA

try:
    from ...analysis.prediction.graphing_utils import apply_standard_axes
except ImportError:
    try:
        from analysis.prediction.graphing_utils import apply_standard_axes
    except ImportError:
        from biopro.plugins.synthetic_biology.analysis.prediction.graphing_utils import apply_standard_axes




class SimulateView(QWidget):
    """Central view for running and plotting mathematical simulations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parts = []
        self._last_simulation_result = None
        self._last_simulation_method = None
        self._last_simulation_title = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Info Label
        self.info_label = QLabel("Run a simulation or view steady-state logic curves.")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        # Main Splitter: Canvas Container on left (80%), Control Panel on right (20%)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter, 1)

        # Left Container: Matplotlib Plot Canvas
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
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

        # Apply dark theme
        self._apply_theme()

    def _apply_theme(self):
        try:
            from biopro.ui.theme import Colors, Fonts
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
                f"QListWidget::item {{ padding: 6px; border-bottom: 1px solid {border}; }}"
                f"QListWidget::item:hover {{ background: {dark_bg}; }}"
            )
            btn_style = (
                f"background: {dark_panel}; color: {accent}; border: 1px solid {accent}; "
                f"font-size: 11px; font-weight: bold; padding: 4px; border-radius: 3px;"
            )
            self.select_all_btn.setStyleSheet(btn_style)
            self.clear_all_btn.setStyleSheet(btn_style)
        except Exception:
            self.figure.patch.set_facecolor('#0d1117')
            self.canvas.setStyleSheet("background-color: #0d1117;")
            self.info_label.setStyleSheet("color: #8b949e; font-size: 14px;")


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

    def update_plot(self):
        """Redraw the simulation figure on the matplotlib canvas based on species selection."""
        if self._last_simulation_result is None:
            return

        result = self._last_simulation_result
        method = self._last_simulation_method or 'ode'
        title = self._last_simulation_title or 'Dynamic Circuit Simulation'

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
        else:
            palette = ["#00bcd4", "#4caf50", "#ff9800", "#e91e63", "#9c27b0", "#03a9f4", "#ff5722", "#8bc34a"]

            for idx, (display_name, col_name) in enumerate(checked_columns):
                color = palette[idx % len(palette)]
                lw = 1.0 if method == 'gillespie' else 2.0

                # Fetch data array matching column name
                if hasattr(result, "colnames") and col_name in result.colnames:
                    data_y = result[col_name]
                elif hasattr(result, "__getitem__") and col_name in result:
                    data_y = result[col_name]
                else:
                    continue

                ax.plot(result['time'], data_y, label=display_name, color=color, linewidth=lw)

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
                self.figure.tight_layout()

        self.canvas.draw()

    def plot_steady_state(self):
        """Plot the transfer function (Input Repressor vs Output Expression) for Promoters."""
        from ...analysis.simulation.transfer_curve import calculate_steady_state_curve

        self.control_panel.setVisible(False)
        self._last_simulation_result = None

        self.info_label.setText(
            "<b>Steady-State Transfer Curve:</b> Demonstrates the transfer function "
            "y = y_min + (y_max - y_min) / (1 + (R / K_d)^n) showing how promoter output expression "
            "changes as a function of input repressor concentration R."
        )
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        promoters = [p for p in self._parts if isinstance(p, Promoter)]

        # Fallback to Cello default promoters if active parts cache is empty
        if not promoters:
            try:
                try:
                    from ...analysis.api.kinetics import CelloKineticsDatabase
                except ImportError:
                    from analysis.api.kinetics import CelloKineticsDatabase

                CelloKineticsDatabase.get_parameters("AmtR")
                classic = CelloKineticsDatabase._classic_params
                for pid, params in classic.items():
                    if "y_max" in params:
                        promoters.append(
                            Promoter(
                                id=pid,
                                name=params.get("description", pid),
                                y_max=params.get("y_max"),
                                y_min=params.get("y_min", 0.0),
                                K_d=params.get("K_d"),
                                n=params.get("n"),
                            )
                        )
            except Exception:
                pass

        valid_promoters = [
            p for p in promoters
            if p.y_max is not None and p.K_d is not None and p.n is not None
        ]

        if not valid_promoters:
            ax.text(
                0.5,
                0.5,
                "No Promoters with quantitative parameters (K_d, y_max, n) found.",
                ha="center",
                va="center",
                color="white",
                fontsize=12,
            )
        else:
            palette = ["#00bcd4", "#4caf50", "#ff9800", "#e91e63", "#9c27b0", "#03a9f4"]

            for idx, p in enumerate(valid_promoters):
                y_min = p.y_min if p.y_min is not None else 0.0
                curve_data = calculate_steady_state_curve(
                    K_d=p.K_d,
                    y_max=p.y_max,
                    y_min=y_min,
                    n=p.n,
                )

                color = palette[idx % len(palette)]
                label = f"{p.id} ({p.name})" if p.name != p.id else p.id

                ax.plot(
                    curve_data["R"],
                    curve_data["y"],
                    label=label,
                    color=color,
                    linewidth=2.5,
                )

                # Vertical marker at Kd threshold
                ax.axvline(
                    x=curve_data["K_d"],
                    color=color,
                    linestyle="--",
                    alpha=0.4,
                )

            ax.set_xscale("log")
            ax.set_yscale("log")
            x_label = "Input Repressor Concentration R (RPU)"
            y_label = "Output Promoter Activity y (RPU)"

            if len(valid_promoters) == 1:
                p0 = valid_promoters[0]
                ymin0 = p0.y_min if p0.y_min is not None else 0.0
                title = f"Steady-State Transfer Curve: {p0.id} (Kd={p0.K_d}, ymax={p0.y_max}, ymin={ymin0}, n={p0.n})"
            else:
                title = f"Steady-State Transfer Functions ({len(valid_promoters)} Promoters)"

            try:
                apply_standard_axes(
                    ax=ax,
                    fig=self.figure,
                    x_label=x_label,
                    y_label=y_label,
                    title=title,
                    is_log_x=True,
                    is_log_y=True,
                )
            except Exception:
                for spine in ax.spines.values():
                    spine.set_color("#30363d")
                ax.set_facecolor("#0d1117")
                self.figure.tight_layout()

        self.canvas.draw()


    def plot_time_series(self, max_time: int = 1000, method: str = 'ode'):
        """Run and plot a dynamic ODE or Stochastic simulation using Tellurium."""
        method_name = "Time-Series Simulation (ODE)" if method == 'ode' else "Stochastic Simulation (Gillespie)"
        self.info_label.setText(
            f"<b>{method_name}:</b> Shows how the concentrations of your genetic circuit components "
            "change dynamically over time as proteins are produced and degraded."
        )
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        try:
            import tellurium as te
        except ImportError:
            ax.text(0.5, 0.5, "Tellurium is not installed. Run 'pip install tellurium'.", 
                    ha='center', va='center', color='red', fontsize=12)
            self.canvas.draw()
            return

        promoters = [p for p in self._parts if isinstance(p, Promoter)]
        cdss = [c for c in self._parts if isinstance(c, (CDS, sgRNA))]

        if not promoters or not cdss:
            ax.text(0.5, 0.5, "Circuit requires at least one Promoter and one CDS.", 
                    ha='center', va='center', color='white', fontsize=12)
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
                product_name = getattr(part, "product", part.name.replace(" ", "_").replace("-", "_"))
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
                if method == 'gillespie':
                    init_val = init_val * 10
                antimony_lines.append(f"  species {product_name} = {init_val};")
                is_first_product = False

                # Reactions
                antimony_lines.append(f"  J_prod_{product_name}: => {product_name}; {equation};")
                antimony_lines.append(f"  J_deg_{product_name}: {product_name} => ; {deg_rate} * {product_name};")

        antimony_lines.append("end")
        model_str = "\n".join(antimony_lines)

        try:
            # 2. Load and simulate
            r = te.loada(model_str)
            if method == 'gillespie':
                r.setIntegrator('gillespie')
                r.integrator.seed = np.random.randint(1000000)
                result = r.simulate(0, max_time, max_time * 5)
                title = 'Dynamic Circuit Simulation (Stochastic Gillespie)'
            else:
                result = r.simulate(0, max_time, max_time * 2)
                title = 'Dynamic Circuit Simulation (Deterministic ODE)'

            # Cache simulation result
            self._last_simulation_result = result
            self._last_simulation_method = method
            self._last_simulation_title = title

            # 3. Populate Species Selector ListWidget
            self.control_panel.setVisible(True)
            self.species_list.blockSignals(True)
            self.species_list.clear()

            colnames = getattr(result, "colnames", [])
            for col in colnames[1:]:
                clean_name = col.replace('[', '').replace(']', '')
                item = QListWidgetItem(clean_name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                item.setData(Qt.ItemDataRole.UserRole, col)
                self.species_list.addItem(item)

            self.species_list.blockSignals(False)

            # 4. Render selected traces on canvas
            self.update_plot()

        except Exception as e:
            ax.text(0.5, 0.5, f"Simulation Error:\n{str(e)}", 
                    ha='center', va='center', color='red', fontsize=10)
            self.figure.tight_layout()
            self.canvas.draw()

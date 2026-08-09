"""Simulation view for plotting steady-state curves and ODEs."""

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

# Matplotlib PyQt6 integration
import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from biopro.plugins.synthetic_biology.analysis.parts.components import Promoter


class SimulateView(QWidget):
    """Central view for running and plotting mathematical simulations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parts = []
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

        # Setup Matplotlib Canvas
        self.figure = Figure(figsize=(8, 6), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas, 1)  # Give canvas stretch factor

        # Apply dark theme
        self._apply_theme()

    def _apply_theme(self):
        try:
            from biopro.ui.theme import Colors, Fonts

            self.figure.patch.set_facecolor(Colors.BG_DARKEST)
            self.canvas.setStyleSheet(f"background-color: {Colors.BG_DARKEST};")
            self.info_label.setStyleSheet(
                f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL + 2}px;"
            )
        except ImportError:
            self.figure.patch.set_facecolor("#0d1117")
            self.info_label.setStyleSheet("color: #8b949e; font-size: 14px;")

    def set_parts(self, parts: list):
        """Update the active parts available for simulation."""
        self._parts = parts

    def plot_steady_state(self):
        """Plot the transfer function (Input vs Output RPU) for Promoters."""
        self.info_label.setText(
            "<b>Steady-State Transfer Curve:</b> Shows how the output of your logic gates (promoters) changes "
            "based on the input repressor concentration. This demonstrates the 'snap' threshold of the gate."
        )
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        promoters = [p for p in self._parts if isinstance(p, Promoter)]
        if not promoters:
            ax.text(
                0.5,
                0.5,
                "No Promoters found to plot transfer curve.",
                ha="center",
                va="center",
                color="white",
                fontsize=12,
            )
        else:
            inputs = np.logspace(-3, 2, 500)  # RPU inputs from 0.001 to 100

            for p in promoters:
                if p.y_max is None or p.K_d is None or p.n is None:
                    continue

                y_min = p.y_min if p.y_min is not None else 0.0

                # Hill equation for a repressor
                output = y_min + (p.y_max - y_min) / (1 + (inputs / p.K_d) ** p.n)

                ax.plot(inputs, output, label=f"{p.id} ({p.name})", linewidth=2)

            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlabel("Input Repressor Concentration (RPU)", color="white")
            ax.set_ylabel("Output Promoter Activity (RPU)", color="white")
            ax.set_title("Steady-State Transfer Functions", color="white")
            ax.tick_params(colors="white", which="both")
            ax.grid(True, which="both", ls="-", alpha=0.2)
            if ax.get_legend_handles_labels()[1]:
                ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white")

        # Style adjustments
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.set_facecolor("#0d1117")

        self.figure.tight_layout()
        self.canvas.draw()

    def plot_time_series(self, max_time: int = 1000, method: str = "ode"):
        """Run and plot a dynamic ODE or Stochastic simulation using Tellurium."""
        method_name = (
            "Time-Series Simulation (ODE)"
            if method == "ode"
            else "Stochastic Simulation (Gillespie)"
        )
        self.info_label.setText(
            f"<b>{method_name}:</b> Shows how the concentrations of your genetic circuit components "
            "change dynamically over time as proteins are produced and degraded."
        )
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        try:
            import tellurium as te
        except ImportError:
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

        from analysis.parts.components import Promoter, CDS, sgRNA

        promoters = [p for p in self._parts if isinstance(p, Promoter)]
        cdss = [c for c in self._parts if isinstance(c, (CDS, sgRNA))]

        if not promoters or not cdss:
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
                y_min = (
                    current_promoter.y_min
                    if current_promoter.y_min is not None
                    else 0.0
                )
                y_max = (
                    current_promoter.y_max
                    if current_promoter.y_max is not None
                    else 1.0
                )
                K_d = current_promoter.K_d if current_promoter.K_d is not None else 0.1
                n = current_promoter.n if current_promoter.n is not None else 2.0

                if reps:
                    rep_name = reps[0]  # primary repressor
                    equation = f"{y_min} + ({y_max} - {y_min}) / (1 + ({rep_name} / {K_d})^{n})"
                else:
                    equation = f"{y_max}"  # Constitutive

                deg_rate = (
                    part.degradation_rate if part.degradation_rate is not None else 0.01
                )

                # Species Definition
                init_val = 10 if is_first_product else 0
                if method == "gillespie":
                    # Scale initial value up slightly for Gillespie to prevent immediate extinction
                    init_val = init_val * 10
                antimony_lines.append(f"  species {product_name} = {init_val};")
                is_first_product = False

                # Reactions
                antimony_lines.append(
                    f"  J_prod_{product_name}: => {product_name}; {equation};"
                )
                antimony_lines.append(
                    f"  J_deg_{product_name}: {product_name} => ; {deg_rate} * {product_name};"
                )

        antimony_lines.append("end")
        model_str = "\n".join(antimony_lines)

        try:
            # 2. Load and simulate
            r = te.loada(model_str)
            if method == "gillespie":
                r.setIntegrator("gillespie")
                r.integrator.seed = np.random.randint(1000000)
                result = r.simulate(0, max_time, max_time * 5)
                title = "Dynamic Circuit Simulation (Stochastic Gillespie)"
            else:
                result = r.simulate(0, max_time, max_time * 2)
                title = "Dynamic Circuit Simulation (Deterministic ODE)"

            # 3. Plot
            for col in result.colnames[1:]:
                # Use slightly thinner lines for Gillespie so it looks like a noisy trace
                lw = 1.0 if method == "gillespie" else 2.0
                ax.plot(
                    result["time"],
                    result[col],
                    label=col.replace("[", "").replace("]", ""),
                    linewidth=lw,
                )

            ax.set_xlabel("Time (seconds)", color="white")
            ax.set_ylabel(
                "Concentration" if method == "ode" else "Molecule Count", color="white"
            )
            ax.set_title(title, color="white")
            ax.tick_params(colors="white")
            ax.grid(True, ls="-", alpha=0.2)
            if ax.get_legend_handles_labels()[1]:
                ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white")

            for spine in ax.spines.values():
                spine.set_color("#30363d")
            ax.set_facecolor("#0d1117")

        except Exception as e:
            ax.text(
                0.5,
                0.5,
                f"Simulation Error:\n{str(e)}",
                ha="center",
                va="center",
                color="red",
                fontsize=10,
            )

        self.figure.tight_layout()
        self.canvas.draw()

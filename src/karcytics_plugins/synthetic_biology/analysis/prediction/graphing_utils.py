"""Mathematical Graphing Engine for BioPro Synthetic Biology.

Provides comparative visualization of steady state protein expression curves
between wild-type baseline parts and mutated sequences.
"""

from typing import Any, Dict, Optional

import matplotlib

matplotlib.use("QtAgg")
import numpy as np
from karcytics_sdk.plugin.theme_fallback import Colors
from matplotlib.figure import Figure

DARK_BG = getattr(Colors, "BG_DARKEST", "#0d1117")
TEXT_COLOR = getattr(Colors, "FG_PRIMARY", "#c9d1d9")
WT_COLOR = getattr(Colors, "SUCCESS", "#4caf50")
MUT_COLOR = getattr(Colors, "ACCENT_PRIMARY", "#f44336")


def apply_standard_axes(
    ax: matplotlib.axes.Axes,
    fig: Figure,
    x_label: str,
    y_label: str,
    title: str,
    is_log_x: bool = False,
    is_log_y: bool = False,
) -> None:
    """Apply centralized base formatting to Matplotlib axes and figure for Light
    Theme aesthetics.

    Steps:
    1. Set figure background to #ffffff and axes facecolor to #F8F9FA.
    2. Set crisp dark text (#333333) for title, axis labels, and tick labels.
    3. Hide top and right spines to create a clean modern look:
       ax.spines['top'].set_visible(False).
    4. Set bottom and left spine colors to dark gray (#333333).
    5. Set label font size to 12 and tick label font size to 10.
    6. Implement autoscale with protective margins (x=0.02, y=0.05).
    7. Enable clean light dashed gridlines:
       ax.grid(True, color='#D3D3D3', linestyle='--', alpha=0.7).
    8. Execute fig.tight_layout() to prevent label truncation.
    """
    light_bg_fig = "#ffffff"
    light_bg_ax = "#F8F9FA"
    dark_text_color = "#333333"
    spine_color = "#333333"
    grid_color = "#D3D3D3"

    # Set background colors
    fig.patch.set_facecolor(light_bg_fig)
    ax.set_facecolor(light_bg_ax)

    # Set Title and Labels with font size 12 and crisp dark text
    ax.set_title(title, color=dark_text_color, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(x_label, color=dark_text_color, fontsize=12, fontweight="bold")
    ax.set_ylabel(y_label, color=dark_text_color, fontsize=12, fontweight="bold")

    # Hide top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Style bottom and left spines
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(spine_color)
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color(spine_color)

    # Style ticks with font size 10 and dark text color
    ax.tick_params(
        axis="both",
        which="both" if (is_log_x or is_log_y) else "major",
        colors=dark_text_color,
        labelsize=10,
    )

    # Dynamic scaling & protective margins
    ax.autoscale(enable=True, axis="both", tight=False)
    ax.margins(x=0.02, y=0.05)

    # Light dashed grid lines
    if is_log_x or is_log_y:
        ax.grid(True, which="both", color=grid_color, linestyle="--", alpha=0.7)
    else:
        ax.grid(True, which="major", color=grid_color, linestyle="--", alpha=0.7)

    # Legend styling
    if ax.get_legend_handles_labels()[1]:
        legend = ax.legend(facecolor=light_bg_fig, edgecolor=grid_color, loc="best")
        if legend:
            for text in legend.get_texts():
                text.set_color(dark_text_color)

    # Call tight_layout to protect layout
    fig.tight_layout()


def generate_transfer_curve(
    wt_params: Dict[str, Any],
    mut_params: Dict[str, Any],
    part_type: str = "promoter",
    title: Optional[str] = None,
) -> Figure:
    """Generate a comparative transfer/accumulation curve figure contrasting wild type
    vs mutation.

    Biophysical & Mathematical Rationale:
    1. Promoters (Repressive Hill Equation):
       Steady state promoter output expression P is modeled as a function of
       repressor concentration [R]:
       P = y_min + (y_max - y_min) / (1 + ([R] / K_d)^n)
       - Logarithmic array of repressor concentrations [R] is generated via
         numpy.logspace.
       - Lower binding penalty in wild-type allows higher maximum promoter activity
         (y_max) and distinct repression threshold (K_d) compared to mutated sequence.

    2. Coding Sequences (CDS Protein Accumulation Kinetics):
       Simple protein concentration over time t is modeled via first-order kinetics:
       dP/dt = alpha - gamma * P
       Analytical solution assuming initial P(0) = 0:
       P(t) = (alpha / gamma) * (1 - exp(-gamma * t))
       where alpha is derived from translation_rate (min^-1) and gamma is
       degradation_rate (min^-1).
       - Linear array of time points t (min) is generated via numpy.linspace.
       - Codon bias (CAI) and BLOSUM62 folding stability determine translation speed
         alpha and proteolytic degradation rate gamma respectively.

    3. Visual Styling:
       - Wild Type (WT): Solid green line ('g-' / '#4caf50').
       - Mutated Sequence: Dashed red line ('r--' / '#f44336').
       - Styled legend, grid, title, and axis labels.

    Args:
        wt_params: Dictionary containing wild type kinetic parameters (K_d, y_max,
            y_min, n or translation_rate, degradation_rate).
        mut_params: Dictionary containing mutated sequence kinetic parameters.
        part_type: Part classification ("promoter" or "cds").
        title: Optional custom plot title.

    Returns:
        matplotlib.figure.Figure object containing the rendered comparative graph.
    """
    fig = Figure(figsize=(7, 4.5), dpi=100)
    ax = fig.add_subplot(111)

    clean_type = (part_type or "promoter").lower().strip()

    if clean_type == "promoter":
        # Extract promoter parameters
        wt_kd = float(wt_params.get("K_d") or wt_params.get("wt_kd") or 0.05)
        wt_ymax = float(wt_params.get("y_max") or wt_params.get("wt_ymax") or 250.0)
        wt_ymin = float(wt_params.get("y_min") or wt_params.get("wt_ymin") or 0.01)
        wt_n = float(wt_params.get("n") or wt_params.get("wt_n") or 2.0)

        mut_kd = float(mut_params.get("K_d") or mut_params.get("mut_kd") or 0.05)
        mut_ymax = float(mut_params.get("y_max") or mut_params.get("mut_ymax") or 250.0)
        mut_ymin = float(mut_params.get("y_min") or mut_params.get("mut_ymin") or 0.01)
        mut_n = float(mut_params.get("n") or mut_params.get("mut_n") or 2.0)

        # Concentration range spanning across K_d thresholds
        min_kd = min(wt_kd, mut_kd)
        max_kd = max(wt_kd, mut_kd)
        r_min = max(1e-4, min_kd / 100.0)
        r_max = max(100.0, max_kd * 100.0)

        # Logarithmic repressor concentration array using numpy.logspace
        R = np.logspace(np.log10(r_min), np.log10(r_max), 500)

        # Repressive Hill Equation calculation
        wt_P = wt_ymin + (wt_ymax - wt_ymin) / (
            1.0 + (R / max(1e-6, wt_kd)) ** max(0.1, wt_n)
        )
        mut_P = mut_ymin + (mut_ymax - mut_ymin) / (
            1.0 + (R / max(1e-6, mut_kd)) ** max(0.1, mut_n)
        )

        # Plot curves: solid green for wild type, dashed red for mutation
        ax.plot(R, wt_P, "g-", label="Wild Type Baseline", linewidth=2.2, alpha=0.9)
        ax.plot(R, mut_P, "r--", label="Mutated Sequence", linewidth=2.2, alpha=0.9)

        ax.set_xscale("log")
        if not title:
            title = "Promoter Steady-State Transfer Function (WT vs Mutation)"

        apply_standard_axes(
            ax=ax,
            fig=fig,
            x_label="Repressor Concentration ([R])",
            y_label="Output Expression (RPU)",
            title=title,
            is_log_x=True,
        )

    elif clean_type == "cds":
        # Extract CDS kinetics parameters
        wt_alpha = float(
            wt_params.get("translation_rate")
            or wt_params.get("wt_translation_rate")
            or 0.1
        )
        wt_gamma = float(
            wt_params.get("degradation_rate")
            or wt_params.get("wt_degradation_rate")
            or 0.01
        )

        mut_alpha = float(
            mut_params.get("translation_rate")
            or mut_params.get("mut_translation_rate")
            or 0.1
        )
        mut_gamma = float(
            mut_params.get("degradation_rate")
            or mut_params.get("mut_degradation_rate")
            or 0.01
        )

        # Time array using numpy.linspace
        t = np.linspace(0, 100, 500)

        # Analytical solution for dP/dt = alpha - gamma * P ->
        # P(t) = (alpha/gamma) * (1 - exp(-gamma*t))
        wt_steady = wt_alpha / max(1e-5, wt_gamma)
        mut_steady = mut_alpha / max(1e-5, mut_gamma)

        wt_P = wt_steady * (1.0 - np.exp(-max(1e-5, wt_gamma) * t))
        mut_P = mut_steady * (1.0 - np.exp(-max(1e-5, mut_gamma) * t))

        # Plot curves: solid green for wild type, dashed red for mutation
        ax.plot(t, wt_P, "g-", label="Wild Type Baseline", linewidth=2.2, alpha=0.9)
        ax.plot(t, mut_P, "r--", label="Mutated Sequence", linewidth=2.2, alpha=0.9)

        if not title:
            title = "CDS Protein Accumulation Kinetics (WT vs Mutation)"

        apply_standard_axes(
            ax=ax,
            fig=fig,
            x_label="Time (min)",
            y_label="Protein Concentration (P)",
            title=title,
        )

    else:
        raise ValueError(
            f"Unsupported part type '{part_type}' for transfer curve generation."
        )

    return fig

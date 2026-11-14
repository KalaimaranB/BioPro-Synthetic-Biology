"""Mathematical Graphing Engine for Karcytics Synthetic Biology.

Provides comparative visualization of steady state protein expression curves
between wild-type baseline parts and mutated sequences.
"""

from typing import Any

import matplotlib

matplotlib.use("QtAgg")
import numpy as np
from karcytics_sdk.plugin.theme_fallback import Colors
from matplotlib.figure import Figure

from ..units import PROMOTER_OUTPUT_AXIS_LABEL

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
    """Apply the module's standard formatting to a Matplotlib axes and figure.

    Colours are taken from the active Karcytics theme (``theme_fallback.Colors``)
    rather than hard-coded, so a figure matches whichever theme is loaded. This
    docstring previously described a fixed light palette (#ffffff figure, #F8F9FA
    axes, #333333 text) that the function has never applied.

    What it does:

    1. Figure background from ``BG_DARKEST``, axes face from ``BG_DARK``.
    2. Title, axis labels and tick labels in ``FG_PRIMARY``; labels at 12 pt
       bold, ticks at 10 pt.
    3. Hides the top and right spines; the remaining two take ``BORDER``.
    4. Autoscales with protective margins (x=0.02, y=0.05), then repairs any
       axis limit that came back NaN, infinite, or zero-width — an all-constant
       trace otherwise renders as an empty panel.
    5. Draws a dashed ``BORDER`` grid, on both major and minor ticks when either
       axis is logarithmic.
    6. Adds a legend only when some artist carries a label, so an unlabelled
       figure does not get an empty legend box.
    7. Calls ``fig.tight_layout()`` so long axis labels are not truncated.

    Args:
        ax: Axes to format.
        fig: The figure owning ``ax``.
        x_label: X-axis label; include the unit.
        y_label: Y-axis label; include the unit.
        title: Axes title.
        is_log_x: True when the x-axis is log-scaled, for minor gridlines.
        is_log_y: True when the y-axis is log-scaled, for minor gridlines.
    """
    bg_fig = getattr(Colors, "BG_DARKEST", "#0d1117")
    bg_ax = getattr(Colors, "BG_DARK", "#161b22")
    text_color = getattr(Colors, "FG_PRIMARY", "#c9d1d9")
    spine_color = getattr(Colors, "BORDER", "#30363d")
    grid_color = getattr(Colors, "BORDER", "#30363d")

    # Set background colors
    fig.patch.set_facecolor(bg_fig)
    ax.set_facecolor(bg_ax)

    # Set Title and Labels with font size 12 and theme text
    ax.set_title(title, color=text_color, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(x_label, color=text_color, fontsize=12, fontweight="bold")
    ax.set_ylabel(y_label, color=text_color, fontsize=12, fontweight="bold")

    # Hide top and right spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Style bottom and left spines
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(spine_color)
    ax.spines["left"].set_visible(True)
    ax.spines["left"].set_color(spine_color)

    # Style ticks with font size 10 and theme text color
    ax.tick_params(
        axis="both",
        which="both" if (is_log_x or is_log_y) else "major",
        colors=text_color,
        labelsize=10,
    )

    # Dynamic scaling & protective margins
    ax.autoscale(enable=True, axis="both", tight=False)
    ax.margins(x=0.02, y=0.05)

    # Ensure xlim and ylim min/max are never identical or non-finite
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

    # Light dashed grid lines
    if is_log_x or is_log_y:
        ax.grid(True, which="both", color=grid_color, linestyle="--", alpha=0.7)
    else:
        ax.grid(True, which="major", color=grid_color, linestyle="--", alpha=0.7)

    # Legend styling - top-right with semi-opaque dark background
    if ax.get_legend_handles_labels()[1]:
        legend = ax.legend(
            loc="upper right",
            facecolor=bg_ax,
            edgecolor=grid_color,
            framealpha=0.86,
        )
        if legend:
            for text in legend.get_texts():
                # Themed, not hard-coded white: on a light theme white-on-light
                # legend text is unreadable.
                text.set_color(text_color)

    # Call tight_layout to protect layout
    fig.tight_layout()


def generate_transfer_curve(
    wt_params: dict[str, Any],
    mut_params: dict[str, Any],
    part_type: str = "promoter",
    title: str | None = None,
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
        R = np.logspace(np.log10(r_min), np.log10(r_max), 500)  # noqa: N806

        # Repressive Hill Equation calculation
        wt_P = wt_ymin + (wt_ymax - wt_ymin) / (1.0 + (R / max(1e-6, wt_kd)) ** max(0.1, wt_n))  # noqa: N806
        mut_P = mut_ymin + (mut_ymax - mut_ymin) / (  # noqa: N806
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
            y_label=PROMOTER_OUTPUT_AXIS_LABEL,
            title=title,
            is_log_x=True,
        )

    elif clean_type == "cds":
        # Extract CDS kinetics parameters
        wt_alpha = float(
            wt_params.get("translation_rate") or wt_params.get("wt_translation_rate") or 0.1
        )
        wt_gamma = float(
            wt_params.get("degradation_rate") or wt_params.get("wt_degradation_rate") or 0.01
        )

        mut_alpha = float(
            mut_params.get("translation_rate") or mut_params.get("mut_translation_rate") or 0.1
        )
        mut_gamma = float(
            mut_params.get("degradation_rate") or mut_params.get("mut_degradation_rate") or 0.01
        )

        # Time array using numpy.linspace
        t = np.linspace(0, 100, 500)

        # Analytical solution for dP/dt = alpha - gamma * P ->
        # P(t) = (alpha/gamma) * (1 - exp(-gamma*t))
        wt_steady = wt_alpha / max(1e-5, wt_gamma)
        mut_steady = mut_alpha / max(1e-5, mut_gamma)

        wt_P = wt_steady * (1.0 - np.exp(-max(1e-5, wt_gamma) * t))  # noqa: N806
        mut_P = mut_steady * (1.0 - np.exp(-max(1e-5, mut_gamma) * t))  # noqa: N806

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
        raise ValueError(f"Unsupported part type '{part_type}' for transfer curve generation.")

    return fig

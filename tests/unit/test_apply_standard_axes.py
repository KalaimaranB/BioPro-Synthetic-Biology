"""Unit tests for apply_standard_axes centralized plot formatting function."""

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.figure import Figure

from analysis.prediction.graphing_utils import apply_standard_axes


def test_apply_standard_axes_formatting():
    """Test that apply_standard_axes applies spine, label, tick, and layout styling."""
    fig = Figure(figsize=(6, 4), dpi=100)
    ax = fig.add_subplot(111)
    ax.plot([0, 1, 2], [0, 5, 10], label="Test Line")

    apply_standard_axes(
        ax=ax,
        fig=fig,
        x_label="Time (s)",
        y_label="Concentration (nM)",
        title="Stochastic Gillespie Simulation",
    )

    # 1. Top and right spines hidden
    assert not ax.spines["top"].get_visible()
    assert not ax.spines["right"].get_visible()
    assert ax.spines["bottom"].get_visible()
    assert ax.spines["left"].get_visible()

    # 2. Labels and Title
    assert ax.get_xlabel() == "Time (s)"
    assert ax.get_ylabel() == "Concentration (nM)"
    assert ax.get_title() == "Stochastic Gillespie Simulation"

    # 3. Label font sizes
    assert ax.xaxis.label.get_fontsize() == 12
    assert ax.yaxis.label.get_fontsize() == 12

    # 4. Margins & autoscale
    x_margin, y_margin = ax.margins()
    assert x_margin == 0.02
    assert y_margin == 0.05

    # 5. Light theme facecolors & dark text
    assert fig.patch.get_facecolor() == matplotlib.colors.to_rgba("#ffffff")
    assert ax.get_facecolor() == matplotlib.colors.to_rgba("#F8F9FA")
    assert ax.xaxis.label.get_color() == "#333333"

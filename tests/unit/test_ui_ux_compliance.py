"""Unit tests verifying UI/UX compliance with Karcytics SDK standards.

Covers:
1. Version check and welcome toast triggering during begin_async_init().
2. Main tab bar iconography, mode routing, and theme-managed styling.
3. BioTabWidget usage and theme reactivity in sub-views.
"""

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QTabBar

from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel
from karcytics_plugins.synthetic_biology.ui.views.empirical_analytics_view import (
    EmpiricalAnalyticsView,
)
from karcytics_plugins.synthetic_biology.ui.views.laboratory_execution_view import (
    LaboratoryExecutionView,
)
from karcytics_plugins.synthetic_biology.ui.widgets.bio_tab_widget import BioTabWidget
from karcytics_plugins.synthetic_biology.ui.widgets.part_inspector import PartInspector


def test_synbio_panel_triggers_update_check_on_begin_async_init(destroy_after):
    """Verify that begin_async_init invokes check_for_updates to show the version toast."""
    panel = destroy_after(SynBioPanel())

    with patch.object(panel, "check_for_updates") as mock_check:
        panel.begin_async_init()
        mock_check.assert_called_once_with(
            repo_url="https://github.com/KalaimaranB/Karcytics-SyntheticBiology",
            display_name="Synthetic Biology",
        )


def test_synbio_panel_tab_bar_has_icons_and_11_tabs(destroy_after):
    """Verify that all 11 workspace tabs exist with standard iconography."""
    panel = destroy_after(SynBioPanel())
    tab_bar = panel._tab_bar
    assert isinstance(tab_bar, QTabBar)
    assert tab_bar.count() == 11

    tab_titles = [tab_bar.tabText(i) for i in range(11)]
    assert "🎨 Design" in tab_titles[0]
    assert "🔬 Biological View" in tab_titles[1]
    assert "🧬 Plasmid Assembly" in tab_titles[2]
    assert "✂️ CRISPR Design" in tab_titles[3]
    assert "⚡ Circuit Simulation" in tab_titles[4]
    assert "📊 Empirical Analytics" in tab_titles[5]
    assert "🧫 Laboratory Execution" in tab_titles[6]
    assert "📈 Simulate" in tab_titles[7]
    assert "🔢 Quantitative Data" in tab_titles[8]
    assert "📦 Parts Catalogue" in tab_titles[9]
    assert "🚀 Demo Showcase" in tab_titles[10]


def test_bio_tab_widget_structure():
    """Verify BioTabWidget initializes properly with document mode enabled."""
    tab_widget = BioTabWidget()
    assert tab_widget.documentMode() is True


def test_laboratory_execution_view_uses_bio_tab_widget(destroy_after):
    """Verify LaboratoryExecutionView uses the standardized BioTabWidget."""
    view = destroy_after(LaboratoryExecutionView())
    assert isinstance(view.tabs, BioTabWidget)
    assert view.tabs.count() == 3


def test_empirical_analytics_view_uses_bio_tab_widget(destroy_after):
    """Verify EmpiricalAnalyticsView uses the standardized BioTabWidget."""
    state = SynBioState()
    mock_ctrl = MagicMock()
    view = destroy_after(EmpiricalAnalyticsView(state=state, controller=mock_ctrl))
    assert isinstance(view.tabs, BioTabWidget)
    assert view.tabs.count() == 3


def test_part_inspector_uses_bio_tab_widget(destroy_after):
    """Verify PartInspector uses the standardized BioTabWidget."""
    inspector = destroy_after(PartInspector())
    assert isinstance(inspector.tabs, BioTabWidget)
    assert inspector.tabs.count() == 3

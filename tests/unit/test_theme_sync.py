"""The footer and the circuit canvas must follow a theme change, not just the theme at start-up."""

import pytest
from karcytics_sdk.plugin.theme_fallback import Colors, theme_manager
from PySide6.QtGui import QColor

from karcytics_plugins.synthetic_biology import initialize
from karcytics_plugins.synthetic_biology.analysis.parts.components import CDS


@pytest.fixture
def panel():
    widget = initialize().create_panel()
    yield widget
    theme_manager.set_theme("dark")
    widget.deleteLater()


def test_footer_and_canvas_follow_theme_change(panel):
    canvas = panel._circuit_canvas
    canvas.add_part(CDS(id="laci", name="LacI"))
    theme_manager.set_theme("dark")
    dark_background = canvas.backgroundBrush().color().name()

    theme_manager.set_theme("light")

    assert canvas.backgroundBrush().color() == QColor(Colors.BG_DARKEST)
    assert canvas.backgroundBrush().color().name() != dark_background
    assert canvas.c_text == QColor(Colors.FG_PRIMARY)
    labels = [item for item in canvas.scene().items() if hasattr(item, "defaultTextColor")]
    assert labels and all(label.defaultTextColor() == QColor(Colors.FG_PRIMARY) for label in labels)
    assert f"background: {Colors.BG_DARK}" in panel._status_label.styleSheet()
    assert f"color: {Colors.FG_SECONDARY}" in panel._status_label.styleSheet()

"""Standardized, theme-aware tab widget aligned with Karcytics SDK."""

from __future__ import annotations

from karcytics_sdk.plugin.theme_fallback import theme_manager
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTabWidget

_BIO_TAB_WIDGET_TEMPLATE = """
QTabWidget::pane {
    border: 1px solid {BORDER};
    background-color: {BG_DARK};
    border-radius: 6px;
    top: -1px;
}
QTabBar {
    background-color: transparent;
    border: none;
}
QTabBar::tab {
    background-color: {BG_DARKEST};
    color: {FG_SECONDARY};
    padding: 8px 16px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    margin-right: 4px;
}
QTabBar::tab:hover {
    background-color: {BG_MEDIUM};
    color: {FG_PRIMARY};
}
QTabBar::tab:selected {
    background-color: {BG_DARK};
    color: {ACCENT_PRIMARY};
    font-weight: 600;
    border-color: {BORDER};
    border-bottom: 2px solid {ACCENT_PRIMARY};
}
"""


class BioTabWidget(QTabWidget):
    """Standardized themed tab widget for views and sub-panels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setDocumentMode(True)
        if hasattr(theme_manager, "apply_style"):
            theme_manager.apply_style(self, _BIO_TAB_WIDGET_TEMPLATE)
        else:
            self.setStyleSheet(_BIO_TAB_WIDGET_TEMPLATE)

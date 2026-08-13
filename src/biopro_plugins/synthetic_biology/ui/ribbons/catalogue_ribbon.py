from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel

try:
    from biopro.ui.theme import Colors, Fonts
except ImportError:
    try:
        from biopro_sdk.plugin.theme_fallback import Colors, Fonts
    except ImportError:

        class Colors:
            FG_PRIMARY = "#e6edf3"

        class Fonts:
            SIZE_SMALL = 11


class CatalogueRibbon(QWidget):
    """Ribbon toolbar for the Parts Catalogue tab."""

    def __init__(self, factory, parent=None):
        super().__init__(parent)
        self.factory = factory
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)

        title = QLabel("Parts Catalogue")
        title.setStyleSheet(
            f"color: {Colors.FG_PRIMARY}; "
            f"font-size: {Fonts.SIZE_SMALL + 2}px; font-weight: bold;"
        )
        layout.addWidget(title)

        layout.addStretch()

    def refresh_styles(self):
        # Refresh theme colors
        pass

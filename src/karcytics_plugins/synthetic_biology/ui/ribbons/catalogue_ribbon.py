from karcytics_sdk.plugin.theme_fallback import Colors, Fonts
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


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

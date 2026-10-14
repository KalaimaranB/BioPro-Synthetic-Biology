from karcytics_sdk.plugin.ribbon import BioRibbon
from karcytics_sdk.plugin.theme_fallback import Colors, Fonts
from PyQt6.QtWidgets import QLabel


class CatalogueRibbon(BioRibbon):
    """Ribbon toolbar for the Parts Catalogue tab."""

    def __init__(self, factory, parent=None):
        super().__init__(parent)
        self.factory = factory
        self.run_button.hide()
        self.cancel_button.hide()
        self._setup_ui()

    def _setup_ui(self):
        title = QLabel("Parts Catalogue")
        title.setStyleSheet(
            f"color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_NORMAL}; font-weight: bold;"
        )
        self.add_widget(title)
        self.add_stretch()

    def refresh_styles(self):
        # Refresh theme colors
        pass

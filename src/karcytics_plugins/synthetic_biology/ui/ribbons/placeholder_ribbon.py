"""Placeholder ribbon toolbar for tabs without specialized controls."""

from karcytics_sdk.plugin.ribbon import BioRibbon
from karcytics_sdk.plugin.theme_fallback import Colors, Fonts
from PyQt6.QtWidgets import QLabel


class PlaceholderRibbon(BioRibbon):
    """Standard placeholder ribbon inheriting from BioRibbon."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title_text = title
        self.run_button.hide()
        self.cancel_button.hide()

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            f"color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_NORMAL}; font-weight: bold;"
        )
        self.add_widget(self.title_label)
        self.add_stretch()

"""Biological View Ribbon — Diagram styling and display options."""

from karcytics_sdk.plugin.components import BioToggleButton
from PyQt6.QtWidgets import QHBoxLayout, QWidget


class BiologicalViewRibbon(QWidget):
    """Ribbon for biological diagram visual settings."""

    def __init__(self, service_factory, parent=None):
        super().__init__(parent)
        self._factory = service_factory
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        self.toggle_seq = BioToggleButton("Show Sequences")
        self.toggle_seq.setCheckable(True)
        layout.addWidget(self.toggle_seq)

        self.toggle_stubs = BioToggleButton("Show Repression Stubs")
        self.toggle_stubs.setCheckable(True)
        self.toggle_stubs.setChecked(True)
        layout.addWidget(self.toggle_stubs)

        layout.addStretch()

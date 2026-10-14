"""Biological View Ribbon — Diagram styling and display options."""

from karcytics_sdk.plugin.components import BioToggleButton
from karcytics_sdk.plugin.ribbon import BioRibbon


class BiologicalViewRibbon(BioRibbon):
    """Ribbon for biological diagram visual settings."""

    def __init__(self, service_factory, parent=None):
        super().__init__(parent)
        self._factory = service_factory
        self.run_button.hide()
        self.cancel_button.hide()
        self._setup_ui()

    def _setup_ui(self):
        self.toggle_seq = BioToggleButton("Show Sequences")
        self.toggle_seq.setCheckable(True)
        self.add_widget(self.toggle_seq)

        self.toggle_stubs = BioToggleButton("Show Repression Stubs")
        self.toggle_stubs.setCheckable(True)
        self.toggle_stubs.setChecked(True)
        self.add_widget(self.toggle_stubs)

        self.add_stretch()

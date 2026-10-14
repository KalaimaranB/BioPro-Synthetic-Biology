"""Simulate Ribbon — Kinetic simulation controls."""

from karcytics_sdk.plugin.components import BioComboBox, BioSpinBox, PrimaryButton
from karcytics_sdk.plugin.ribbon import BioRibbon
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel


class SimulateRibbon(BioRibbon):
    """Ribbon for setting simulation parameters and running simulations."""

    run_simulation = Signal(int, str)

    def __init__(self, service_factory, parent=None):
        super().__init__(parent)
        self._factory = service_factory
        self.run_button.hide()
        self.cancel_button.hide()
        self._setup_ui()

    def _setup_ui(self):
        self.add_widget(QLabel("Max Time (s):"))
        self.time_spin = BioSpinBox()
        self.time_spin.setRange(10, 10000)
        self.time_spin.setValue(100)
        self.add_widget(self.time_spin)

        self.add_widget(QLabel("Method:"))
        self.method_combo = BioComboBox()
        self.method_combo.addItems(
            [
                "Deterministic (ODE)",
                "Stochastic (Gillespie)",
            ]
        )
        self.add_widget(self.method_combo)

        self.run_btn = PrimaryButton("▶️ Run Simulation")
        self.run_btn.clicked.connect(self._on_run_clicked)
        self.add_widget(self.run_btn)

        self.add_stretch()

    def _on_run_clicked(self):
        idx = self.method_combo.currentIndex()
        if idx == 0:
            method = "ode"
        else:
            method = "gillespie"
        self.run_simulation.emit(self.time_spin.value(), method)

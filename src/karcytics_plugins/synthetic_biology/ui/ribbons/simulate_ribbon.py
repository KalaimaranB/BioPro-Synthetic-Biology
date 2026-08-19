"""Simulate Ribbon — Kinetic simulation controls."""

from karcytics_sdk.plugin.components import BioSpinBox, PrimaryButton
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget


class SimulateRibbon(QWidget):
    """Ribbon for setting simulation parameters and running simulations."""

    run_simulation = pyqtSignal(int, str)

    def __init__(self, service_factory, parent=None):
        super().__init__(parent)
        self._factory = service_factory
        self._setup_ui()

    def _setup_ui(self):
        from PyQt6.QtWidgets import QComboBox

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Max Time (s):"))
        self.time_spin = BioSpinBox()
        self.time_spin.setRange(10, 10000)
        self.time_spin.setValue(100)
        layout.addWidget(self.time_spin)

        layout.addWidget(QLabel("Method:"))
        self.method_combo = QComboBox()
        self.method_combo.addItems(
            [
                "Deterministic (ODE)",
                "Stochastic (Gillespie)",
            ]
        )
        layout.addWidget(self.method_combo)

        self.run_btn = PrimaryButton("▶️ Run Simulation")
        self.run_btn.clicked.connect(self._on_run_clicked)
        layout.addWidget(self.run_btn)

        layout.addStretch()

    def _on_run_clicked(self):
        idx = self.method_combo.currentIndex()
        if idx == 0:
            method = "ode"
        else:
            method = "gillespie"
        self.run_simulation.emit(self.time_spin.value(), method)

"""Design Ribbon — Fetch and select biological parts."""

from PyQt6.QtCore import QStringListModel, Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QCompleter, QHBoxLayout, QLabel, QMessageBox, QWidget

try:
    from biopro.shared.ui.ui_components import BioLineEdit, PrimaryButton
except ImportError:
    from PyQt6.QtWidgets import QLineEdit as BioLineEdit
    from PyQt6.QtWidgets import QPushButton as PrimaryButton


class DesignRibbon(QWidget):
    """Ribbon for selecting and fetching biological parts from registries."""

    part_fetched = pyqtSignal(object)  # Emits the BiologicalPart

    # Predefined popular iGEM parts for autocomplete by role
    COMMON_PARTS = {
        "Promoter": [
            "BBa_R0040 - TetR repressible promoter",
            "BBa_R0010 - LacI repressible promoter",
            "BBa_J23100 - Constitutive promoter",
        ],
        "Ribosome Binding Site": [
            "BBa_B0034 - Strong RBS",
            "BBa_B0030 - Weak RBS",
        ],
        "Coding Sequence": [
            "BBa_E0040 - GFP mut3b (Reporter)",
            "BBa_C0040 - TetR repressor CDS",
            "BBa_C0012 - LacI repressor CDS",
        ],
        "Terminator": [
            "BBa_B0015 - Double terminator",
            "BBa_B0010 - T1 terminator",
        ]
    }

    def __init__(self, service_factory, parent=None):
        super().__init__(parent)
        self._factory = service_factory
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Role:"))
        self.role_combo = QComboBox()
        self.role_combo.addItems(["Promoter", "Ribosome Binding Site", "Coding Sequence", "Terminator"])
        self.role_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.role_combo.setMinimumWidth(250)
        self.role_combo.currentTextChanged.connect(self._update_completer)
        layout.addWidget(self.role_combo)

        self.search_input = BioLineEdit()
        self.search_input.setPlaceholderText("Enter iGEM Part ID (e.g., BBa_R0040)...")
        self.search_input.setMinimumWidth(300)

        self.completer = QCompleter([], self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_input.setCompleter(self.completer)
        self._update_completer("Promoter")  # Initialize

        layout.addWidget(self.search_input)

        self.fetch_btn = PrimaryButton("Fetch Part")
        self.fetch_btn.clicked.connect(self._on_fetch)
        layout.addWidget(self.fetch_btn)

        layout.addStretch()

        # Apply dark theme styling ONCE so the SDK global style migration can pick up the hex codes
        try:
            from biopro.ui.theme import Colors
            self.role_combo.setStyleSheet(f"""
                QComboBox {{
                    background: {Colors.BG_DARK};
                    color: {Colors.FG_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 4px;
                    padding: 4px 8px;
                }}
                QComboBox::drop-down {{
                    border: none;
                }}
                QComboBox QAbstractItemView {{
                    background: {Colors.BG_DARKEST};
                    color: {Colors.FG_PRIMARY};
                    selection-background-color: {Colors.ACCENT_PRIMARY};
                    border: 1px solid {Colors.BORDER};
                }}
            """)
        except ImportError:
            pass

    def _update_completer(self, role: str):
        """Update autocomplete suggestions based on selected role."""
        parts = self.COMMON_PARTS.get(role, [])
        model = QStringListModel(parts, self.completer)
        self.completer.setModel(model)

    def _on_fetch(self):
        raw_text = self.search_input.text().strip()
        if not raw_text:
            return

        # Extract just the ID if the user selected from the autocomplete dropdown
        part_id = raw_text.split(" - ")[0].strip()

        # Disable button during fetch (basic feedback)
        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching...")

        # In a real app, this should be an async worker, but for Phase 1 we block.
        try:
            client = self._factory.get("igem_client")
            if client:
                part = client.fetch_part(part_id)
                if part:
                    self.part_fetched.emit(part)
                    self.search_input.clear()
                else:
                    QMessageBox.warning(self, "Fetch Failed", f"Could not find part '{part_id}'.")
        finally:
            self.fetch_btn.setEnabled(True)
            self.fetch_btn.setText("Fetch Part")

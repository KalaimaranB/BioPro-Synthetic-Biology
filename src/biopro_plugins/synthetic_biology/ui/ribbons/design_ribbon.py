"""Design Ribbon — Fetch and select biological parts via dynamic dropdown."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox, QWidget

try:
    from biopro.shared.ui.ui_components import PrimaryButton
except ImportError:
    from PyQt6.QtWidgets import QPushButton as PrimaryButton

try:
    from ...analysis.parts.components import BiologicalPart
except ImportError:
    try:
        from analysis.parts.components import BiologicalPart
        
    except ImportError:
        # pyrefly: ignore [missing-import]
        from biopro.plugins.synthetic_biology.analysis.parts.components import (
            BiologicalPart,
        )


class DesignRibbon(QWidget):
    """Ribbon for selecting and fetching biological parts from registries."""

    part_fetched = pyqtSignal(object)  # Emits the BiologicalPart

    # Predefined popular iGEM parts fallback when database is empty
    COMMON_PARTS = {
        "Promoter": [
            ("BBa_R0040", "BBa_R0040 - TetR repressible promoter"),
            ("BBa_R0010", "BBa_R0010 - LacI repressible promoter"),
            ("BBa_J23100", "BBa_J23100 - Constitutive promoter"),
            ("P_tac", "P_tac - Hybrid IPTG-inducible promoter"),
        ],
        "Ribosome Binding Site": [
            ("BBa_B0034", "BBa_B0034 - Strong RBS"),
            ("BBa_B0030", "BBa_B0030 - Weak RBS"),
            ("RBS_riboJ", "RBS_riboJ - Insulated ribosome binding site"),
        ],
        "Coding Sequence": [
            ("BBa_E0040", "BBa_E0040 - GFP mut3b (Reporter)"),
            ("BBa_C0040", "BBa_C0040 - TetR repressor CDS"),
            ("BBa_C0012", "BBa_C0012 - LacI repressor CDS"),
            ("mCherry", "mCherry - Red fluorescent protein CDS"),
        ],
        "Terminator": [
            ("BBa_B0015", "BBa_B0015 - Double terminator"),
            ("BBa_B0010", "BBa_B0010 - T1 terminator"),
        ],
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
        self.role_combo.addItems(
            [
                "Promoter",
                "Ribosome Binding Site",
                "Coding Sequence",
                "Terminator",
            ]
        )
        self.role_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.role_combo.setMinimumWidth(160)
        layout.addWidget(self.role_combo)

        # Dynamic Part Selector QComboBox (replacing QLineEdit)
        layout.addWidget(QLabel("Part:"))
        self.part_selector_combo = QComboBox()
        self.part_selector_combo.setMinimumWidth(280)
        self.part_selector_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContents
        )
        layout.addWidget(self.part_selector_combo)

        # Connect Role dropdown to update_part_selector method
        self.role_combo.currentTextChanged.connect(self.update_part_selector)

        self.fetch_btn = PrimaryButton("Fetch Part")
        self.fetch_btn.clicked.connect(self._on_fetch)
        layout.addWidget(self.fetch_btn)

        layout.addStretch()

        # Apply dark theme styling
        self._apply_theme()

        # Initialize part selector dropdown with default role
        self.update_part_selector(self.role_combo.currentText())

    def _apply_theme(self):
        try:
            from biopro.ui.theme import Colors

            combo_style = f"""
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
            """
            self.role_combo.setStyleSheet(combo_style)
            self.part_selector_combo.setStyleSheet(combo_style)
        except ImportError:
            pass

    def update_part_selector(self, selected_role: str) -> None:
        """Dynamically populate part_selector_combo based on selected_role from database or fallbacks."""
        self.part_selector_combo.blockSignals(True)
        self.part_selector_combo.clear()

        selected_role_clean = (selected_role or "Promoter").strip()

        # Map display role string to database part types
        role_type_map = {
            "Promoter": ["promoter"],
            "Ribosome Binding Site": ["rbs", "ribosome binding site"],
            "Coding Sequence": ["cds", "coding sequence"],
            "Terminator": ["terminator"],
        }
        matching_types = role_type_map.get(
            selected_role_clean, [selected_role_clean.lower()]
        )

        # Query Parts Catalogue Service
        catalogue_parts = []
        try:
            if self._factory:
                catalogue_service = self._factory.get("parts_catalogue")
                if catalogue_service and hasattr(catalogue_service, "get_all_parts"):
                    all_parts = catalogue_service.get_all_parts()
                    for p in all_parts:
                        p_type = getattr(p, "part_type", "").lower().strip()
                        if p_type in matching_types:
                            catalogue_parts.append(p)
        except Exception:
            catalogue_parts = []

        # Case A: Populated from local catalogue database
        if catalogue_parts:
            for p in catalogue_parts:
                display_name = (
                    f"{p.id} - {p.name}"
                    if getattr(p, "name", None) and p.name != p.id
                    else p.id
                )
                self.part_selector_combo.addItem(display_name, userData=p)

        # Case B: Catalogue database empty or no matching parts -> Fall back to predefined popular iGEM parts
        else:
            fallback_list = self.COMMON_PARTS.get(selected_role_clean, [])
            if fallback_list:
                for pid, display_name in fallback_list:
                    self.part_selector_combo.addItem(display_name, userData=pid)
            else:
                self.part_selector_combo.addItem(
                    f"No {selected_role_clean} parts available", userData=None
                )

        self.part_selector_combo.blockSignals(False)

    def _update_part_selector(self, selected_role: str) -> None:
        """Alias for update_part_selector."""
        self.update_part_selector(selected_role)

    def _on_fetch(self):
        """Fetch the selected part using self.part_selector_combo.currentData()."""
        selected_data = self.part_selector_combo.currentData()
        current_text = self.part_selector_combo.currentText().strip()

        if selected_data is None and not current_text:
            return

        self.fetch_btn.setEnabled(False)
        self.fetch_btn.setText("Fetching...")

        try:
            # Case 1: userData is already a BiologicalPart object
            if isinstance(selected_data, BiologicalPart):
                self.part_fetched.emit(selected_data)
                return

            # Case 2: userData is part_id string
            part_id = (
                selected_data
                if isinstance(selected_data, str)
                else current_text.split(" - ")[0].strip()
            )

            # Attempt database lookup first
            catalogue_service = (
                self._factory.get("parts_catalogue") if self._factory else None
            )
            part = None
            if catalogue_service and hasattr(catalogue_service, "get_part"):
                part = catalogue_service.get_part(part_id)

            # Attempt iGEM Client lookup if not in local database
            if not part and self._factory:
                client = self._factory.get("igem_client")
                if client:
                    part = client.fetch_part(part_id)

            if part:
                self.part_fetched.emit(part)
            else:
                QMessageBox.warning(
                    self,
                    "Fetch Failed",
                    f"Could not find or instantiate part '{part_id}'.",
                )
        finally:
            self.fetch_btn.setEnabled(True)
            self.fetch_btn.setText("Fetch Part")

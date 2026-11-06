"""Design Ribbon — Fetch and select biological parts via dynamic dropdown."""

from karcytics_sdk.plugin.components import BioComboBox, PrimaryButton
from karcytics_sdk.plugin.dialogs import show_warning
from karcytics_sdk.plugin.ribbon import BioRibbon
from karcytics_sdk.plugin.theme_fallback import Colors
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel

from ...analysis.parts.components import BiologicalPart
from ..workers import RegistryFetchWorker


class DesignRibbon(BioRibbon):
    """Ribbon for selecting and fetching biological parts from registries."""

    part_fetched = Signal(object)  # Emits the BiologicalPart

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
        self._active_worker: RegistryFetchWorker | None = None
        self.run_button.hide()
        self.cancel_button.hide()
        self._setup_ui()

    def _setup_ui(self):
        self.add_widget(QLabel("Role:"))
        self.role_combo = BioComboBox()
        self.role_combo.addItems(
            [
                "Promoter",
                "Ribosome Binding Site",
                "Coding Sequence",
                "Terminator",
            ]
        )
        self.role_combo.setSizeAdjustPolicy(BioComboBox.SizeAdjustPolicy.AdjustToContents)
        self.role_combo.setMinimumWidth(160)
        self.add_widget(self.role_combo)

        # Dynamic Part Selector BioComboBox
        self.add_widget(QLabel("Part:"))
        self.part_selector_combo = BioComboBox()
        # Editable so a student can type a registry ID that is not in the
        # dropdown; _on_fetch's free-text branch is unreachable otherwise.
        self.part_selector_combo.setEditable(True)
        self.part_selector_combo.setInsertPolicy(BioComboBox.InsertPolicy.NoInsert)
        self.part_selector_combo.setMinimumWidth(280)
        self.part_selector_combo.setSizeAdjustPolicy(BioComboBox.SizeAdjustPolicy.AdjustToContents)
        self.add_widget(self.part_selector_combo)

        # Connect Role dropdown to update_part_selector method
        self.role_combo.currentTextChanged.connect(self.update_part_selector)

        self.fetch_btn = PrimaryButton("Fetch Part")
        self.fetch_btn.clicked.connect(self._on_fetch)
        self.add_widget(self.fetch_btn)

        self.add_stretch()

        # Apply dark theme styling
        self._apply_theme()

        # Initialize part selector dropdown with default role
        self.update_part_selector(self.role_combo.currentText())

    def _apply_theme(self):
        hover_color = Colors.ACCENT_PRIMARY_HOVER
        fetch_btn_style = f"""
            QPushButton {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.BG_DARKEST};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
                border-color: {hover_color};
                color: {Colors.BG_DARKEST};
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
            }}
            QPushButton:disabled {{
                background-color: {Colors.BG_MEDIUM};
                color: {Colors.FG_DISABLED};
                border-color: {Colors.BORDER};
            }}
        """
        self.fetch_btn.setStyleSheet(fetch_btn_style)

    def update_part_selector(self, selected_role: str) -> None:
        """Dynamically populate part_selector_combo based on selected_role from
        database or fallbacks.
        """
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
        matching_types = role_type_map.get(selected_role_clean, [selected_role_clean.lower()])

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
                    f"{p.id} - {p.name}" if getattr(p, "name", None) and p.name != p.id else p.id
                )
                self.part_selector_combo.addItem(display_name, userData=p)

        # Case B: Catalogue database empty or no matching parts -> Fall back to
        # predefined popular iGEM parts
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
        """Resolve the selected or typed part, locally then via the registry."""
        selected_data = self.part_selector_combo.currentData()
        current_text = self.part_selector_combo.currentText().strip()

        if selected_data is None and not current_text:
            return

        # Case 1: userData is already a BiologicalPart object — nothing to fetch.
        if isinstance(selected_data, BiologicalPart):
            self.part_fetched.emit(selected_data)
            return

        # Case 2: userData is a part_id string, or the user typed one. An
        # editable combo keeps currentData() from the previously selected row,
        # so typed text has to win when it no longer matches that row.
        part_id = self._resolve_part_id(selected_data, current_text)
        if not part_id:
            return

        # A local hit is a dict lookup; only the registry call needs a thread.
        catalogue_service = self._factory.get("parts_catalogue") if self._factory else None
        if catalogue_service and hasattr(catalogue_service, "get_part"):
            part = catalogue_service.get_part(part_id)
            if part:
                self.part_fetched.emit(part)
                return

        client = self._factory.get("igem_client") if self._factory else None
        if not client:
            self._warn_not_found(part_id)
            return

        self._set_fetching(True)
        self._active_worker = RegistryFetchWorker(
            client=client,
            part_id=part_id,
            parent=self,
        )
        self._active_worker.part_fetched.connect(
            lambda part, pid=part_id: self._on_registry_result(part, pid)
        )
        self._active_worker.error_occurred.connect(self._on_registry_error)
        self._active_worker.start()

    def _resolve_part_id(self, selected_data, current_text: str) -> str:
        """Prefer what the user typed over a stale selection in an editable combo."""
        typed = current_text.split(" - ")[0].strip()
        if isinstance(selected_data, str):
            display = self.part_selector_combo.currentText().strip()
            # currentText still matching the selected row means no free typing.
            if typed == selected_data or display.startswith(f"{selected_data} "):
                return selected_data
        return typed

    def _set_fetching(self, busy: bool) -> None:
        self.fetch_btn.setEnabled(not busy)
        self.fetch_btn.setText("Fetching..." if busy else "Fetch Part")

    def _on_registry_result(self, part, part_id: str) -> None:
        self._set_fetching(False)
        self._active_worker = None
        if part:
            self.part_fetched.emit(part)
        else:
            self._warn_not_found(part_id)

    def _on_registry_error(self, message: str) -> None:
        self._set_fetching(False)
        self._active_worker = None
        show_warning(self, title="Fetch Failed", message=message)

    def _warn_not_found(self, part_id: str) -> None:
        show_warning(
            self,
            title="Fetch Failed",
            message=f"Could not find or instantiate part '{part_id}'.",
        )

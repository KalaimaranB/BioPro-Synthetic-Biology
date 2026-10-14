"""PySide6 Graphical View & QThread Worker for Laboratory Execution & Phase 2 Build Cycle.

Provides Master Mix & Molar Ratio Calculation UI, Liquid Handler Worklist
Exporter (Tecan CSV), and LIMS Inventory & Oligo Tracker tabs. Implements
strict MVC architecture by offloading all computational engine routines to a
background QThread (ProtocolWorker).
"""

from __future__ import annotations

import dataclasses
from typing import Any

from karcytics_sdk.plugin.components import (
    BioComboBox,
    BioDoubleSpinBox,
    BioLineEdit,
    BioProgressDialog,
    BioSpinBox,
    BioSplitter,
    BioTableWidget,
    PrimaryButton,
    SecondaryButton,
)
from karcytics_sdk.plugin.dialogs import (
    get_save_path,
    show_error,
    show_info,
    show_warning,
)
from karcytics_sdk.plugin.theme_fallback import Colors, theme_manager
from karcytics_sdk.plugin.toast import show_toast
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...analysis.assembly.protocol_engine import (
    BenchProtocol,
    ProtocolEngine,
)
from ...analysis.base_worker import BaseSDKWorker
from ...models.inventory_models import (
    Oligo,
    PlasmidInventoryItem,
    Reagent,
    StorageLocation,
)
from ...utils.robot_exporter import RobotExportError, WorklistGenerator


class ProtocolWorker(BaseSDKWorker):
    """SDK AnalysisWorker compliant worker executing ProtocolEngine computational routines
    off the main GUI thread.
    """

    finished_ok = Signal(object)
    finished_err = Signal(str)

    def __init__(  # noqa: PLR0913
        self,
        num_reactions: int,
        vector_bp: int,
        vector_conc_ng_ul: float,
        inserts: list[dict[str, Any]],
        assembly_type: str = "Gibson",
        overage_pct: float = 10.0,
        vector_mass_ng: float = 50.0,
        default_molar_ratio: float = 3.0,
        reaction_volume_ul: float = 20.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.num_reactions = num_reactions
        self.vector_bp = vector_bp
        self.vector_conc_ng_ul = vector_conc_ng_ul
        self.inserts = inserts
        self.assembly_type = assembly_type
        self.overage_pct = overage_pct
        self.vector_mass_ng = vector_mass_ng
        self.default_molar_ratio = default_molar_ratio
        self.reaction_volume_ul = reaction_volume_ul
        self.engine = ProtocolEngine()

    def run(self) -> None:
        """Executes ProtocolEngine routines asynchronously."""
        try:
            if self.is_cancelled():
                return
            protocol = self.engine.generate_bench_protocol(
                num_reactions=self.num_reactions,
                vector_bp=self.vector_bp,
                vector_conc_ng_ul=self.vector_conc_ng_ul,
                inserts=self.inserts,
                assembly_type=self.assembly_type,
                overage_pct=self.overage_pct,
                vector_mass_ng=self.vector_mass_ng,
                default_molar_ratio=self.default_molar_ratio,
                reaction_volume_ul=self.reaction_volume_ul,
            )
            if not self.is_cancelled():
                payload = (
                    protocol.to_dict()
                    if hasattr(protocol, "to_dict")
                    else dataclasses.asdict(protocol)
                )
                self.finished_ok.emit(payload)
                self.finished.emit(payload)
        except Exception as exc:
            if not self.is_cancelled():
                self.finished_err.emit(str(exc))
                self.error.emit(str(exc))
        finally:
            self._is_running = False

    def _execute(self) -> Any:
        return self.run()


class LaboratoryExecutionView(QWidget):
    """PySide6 View for Laboratory Execution, Master Mix Calculation, Liquid
    Handling Export, and LIMS Inventory Tracking. Theme-aware design inheriting
    global application stylesheets.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.current_protocol: dict[str, Any] | BenchProtocol | None = None
        self.worker: ProtocolWorker | None = None
        self.progress_dialog: BioProgressDialog | None = None

        self._init_ui()
        self._load_sample_inventory()

        # Connect theme signal
        theme_manager.theme_changed.connect(self.refresh_styles)

    def refresh_styles(self) -> None:
        """Dynamically update styling on theme change."""
        view_qss = f"""
            QComboBox {{
                background: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: none;
            }}
            QComboBox::down-arrow {{
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {Colors.FG_PRIMARY};
                margin-right: 6px;
            }}
            QSplitter::handle {{
                background-color: {Colors.BORDER};
            }}
            QSplitter::handle:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
            }}
        """
        self.setStyleSheet(view_qss)
        self.update()

    def _init_ui(self) -> None:
        """Constructs the user interface layout and styling."""
        self.setObjectName("laboratory_execution_view")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header Title Banner
        header = QFrame()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)

        title_lbl = QLabel("🧬 Laboratory Execution & Build Cycle Automation")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title_lbl)

        header_layout.addStretch()

        self.status_badge = QLabel("READY")
        self.status_badge.setStyleSheet(
            "font-weight: bold; padding: 3px 10px; border-radius: 12px; font-size: 11px;"
        )
        header_layout.addWidget(self.status_badge)

        main_layout.addWidget(header)

        # Main Tab Widget
        self.tabs = QTabWidget()

        # Tab 1: Master Mix & Ratio Calculator
        tab_calculator = QWidget()
        self._init_calculator_tab(tab_calculator)
        self.tabs.addTab(tab_calculator, "🧮 Master Mix & Ratio Calculator")

        # Tab 2: Liquid Handler Export
        tab_robot = QWidget()
        self._init_robot_exporter_tab(tab_robot)
        self.tabs.addTab(tab_robot, "🤖 Liquid Handler Export (Tecan)")

        # Tab 3: Inventory & Oligo Tracker
        tab_inventory = QWidget()
        self._init_inventory_tab(tab_inventory)
        self.tabs.addTab(tab_inventory, "📦 LIMS Inventory & Oligo Tracker")

        main_layout.addWidget(self.tabs)

    # -------------------------------------------------------------------------
    # TAB 1: MASTER MIX & RATIO CALCULATOR
    # -------------------------------------------------------------------------
    def _init_calculator_tab(self, parent: QWidget) -> None:  # noqa: PLR0915
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)

        # Left Column: Inputs Box
        input_box = QGroupBox("Assembly Parameters & DNA Fragments")
        input_layout = QVBoxLayout(input_box)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Assembly Method
        self.combo_assembly_type = BioComboBox()
        self.combo_assembly_type.addItems(["Gibson Assembly", "Golden Gate Assembly"])
        form_layout.addRow("Assembly Method:", self.combo_assembly_type)

        # Num Reactions
        self.spin_num_rxns = BioSpinBox()
        self.spin_num_rxns.setRange(1, 96)
        self.spin_num_rxns.setValue(4)
        form_layout.addRow("Number of Reactions:", self.spin_num_rxns)

        # Overage %
        self.spin_overage = BioDoubleSpinBox()
        self.spin_overage.setRange(0.0, 50.0)
        self.spin_overage.setValue(10.0)
        self.spin_overage.setSuffix(" %")
        form_layout.addRow("Overage Allowance:", self.spin_overage)

        # Total Reaction Volume
        self.spin_total_vol = BioDoubleSpinBox()
        self.spin_total_vol.setRange(10.0, 100.0)
        self.spin_total_vol.setValue(20.0)
        self.spin_total_vol.setSuffix(" µL")
        form_layout.addRow("Reaction Volume:", self.spin_total_vol)

        # Target Vector Mass
        self.spin_vector_mass = BioDoubleSpinBox()
        self.spin_vector_mass.setRange(10.0, 500.0)
        self.spin_vector_mass.setValue(50.0)
        self.spin_vector_mass.setSuffix(" ng")
        form_layout.addRow("Vector Target Mass:", self.spin_vector_mass)

        # Vector Specs
        self.txt_vector_name = BioLineEdit("pET28a_Vector")
        form_layout.addRow("Vector Name:", self.txt_vector_name)

        self.spin_vector_bp = BioSpinBox()
        self.spin_vector_bp.setRange(500, 50000)
        self.spin_vector_bp.setValue(3000)
        self.spin_vector_bp.setSuffix(" bp")
        form_layout.addRow("Vector Length:", self.spin_vector_bp)

        self.spin_vector_conc = BioDoubleSpinBox()
        self.spin_vector_conc.setRange(1.0, 1000.0)
        self.spin_vector_conc.setValue(50.0)
        self.spin_vector_conc.setSuffix(" ng/µL")
        form_layout.addRow("Vector Conc:", self.spin_vector_conc)

        # Insert 1 Specs
        self.txt_insert_name = BioLineEdit("GFP_Insert")
        form_layout.addRow("Insert 1 Name:", self.txt_insert_name)

        self.spin_insert_bp = BioSpinBox()
        self.spin_insert_bp.setRange(50, 20000)
        self.spin_insert_bp.setValue(1000)
        self.spin_insert_bp.setSuffix(" bp")
        form_layout.addRow("Insert 1 Length:", self.spin_insert_bp)

        self.spin_insert_conc = BioDoubleSpinBox()
        self.spin_insert_conc.setRange(1.0, 1000.0)
        self.spin_insert_conc.setValue(30.0)
        self.spin_insert_conc.setSuffix(" ng/µL")
        form_layout.addRow("Insert 1 Conc:", self.spin_insert_conc)

        self.spin_molar_ratio = BioDoubleSpinBox()
        self.spin_molar_ratio.setRange(1.0, 10.0)
        self.spin_molar_ratio.setValue(3.0)
        self.spin_molar_ratio.setSuffix(" : 1")
        form_layout.addRow("Insert:Vector Ratio:", self.spin_molar_ratio)

        input_layout.addLayout(form_layout)

        # Calculate Button
        self.btn_generate = PrimaryButton("⚡ Generate Bench Protocol")
        self.btn_generate.clicked.connect(self._on_generate_protocol_clicked)
        input_layout.addWidget(self.btn_generate)

        layout.addWidget(input_box, stretch=1)

        # Right Column: Output Results Tables
        output_box = QGroupBox("Calculated Master Mix & Reaction Pipetting Table")
        output_layout = QVBoxLayout(output_box)

        output_splitter = BioSplitter(Qt.Orientation.Vertical)

        # Table 1: Master Mix
        mm_widget = QWidget()
        mm_layout = QVBoxLayout(mm_widget)
        mm_layout.setContentsMargins(0, 0, 0, 0)
        mm_lbl = QLabel("1. Master Mix Preparation Table")
        mm_lbl.setStyleSheet("font-weight: bold;")
        mm_layout.addWidget(mm_lbl)

        self.table_master_mix = BioTableWidget()
        self.table_master_mix.setRowCount(0)
        self.table_master_mix.setColumnCount(3)
        self.table_master_mix.setHorizontalHeaderLabels(
            ["Reagent Component", "Per Reaction (µL)", "Total Master Mix (µL)"]
        )
        if (hv := self.table_master_mix.horizontalHeader()) is not None:
            hv.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        mm_layout.addWidget(self.table_master_mix)
        output_splitter.addWidget(mm_widget)

        # Table 2: Fragment Pipetting
        pip_widget = QWidget()
        pip_layout = QVBoxLayout(pip_widget)
        pip_layout.setContentsMargins(0, 0, 0, 0)
        pip_lbl = QLabel("2. Reaction Fragment Pipetting Specifications")
        pip_lbl.setStyleSheet("font-weight: bold;")
        pip_layout.addWidget(pip_lbl)

        self.table_pipetting = BioTableWidget()
        self.table_pipetting.setRowCount(0)
        self.table_pipetting.setColumnCount(7)
        self.table_pipetting.setHorizontalHeaderLabels(
            [
                "Component",
                "Role",
                "Length (bp)",
                "Conc (ng/µL)",
                "Ratio",
                "Mass (ng)",
                "Volume (µL)",
            ]
        )
        if (hv := self.table_pipetting.horizontalHeader()) is not None:
            hv.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        pip_layout.addWidget(self.table_pipetting)
        output_splitter.addWidget(pip_widget)

        output_layout.addWidget(output_splitter)
        layout.addWidget(output_box, stretch=2)

    # -------------------------------------------------------------------------
    # TAB 2: LIQUID HANDLER EXPORT (TECAN)
    # -------------------------------------------------------------------------
    def _init_robot_exporter_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)

        # Controls Header
        ctrl_box = QGroupBox("Tecan GWL / CSV Worklist Exporter Options")
        ctrl_layout = QHBoxLayout(ctrl_box)

        ctrl_layout.addWidget(QLabel("Source Plate ID:"))
        self.txt_source_plate = BioLineEdit("REAGENT_PLATE_1")
        ctrl_layout.addWidget(self.txt_source_plate)

        ctrl_layout.addWidget(QLabel("Destination Plate ID:"))
        self.txt_dest_plate = BioLineEdit("DEST_PLATE_1")
        ctrl_layout.addWidget(self.txt_dest_plate)

        self.btn_export_csv = PrimaryButton("🤖 Export to Tecan CSV")
        self.btn_export_csv.clicked.connect(self._on_export_csv_clicked)
        ctrl_layout.addWidget(self.btn_export_csv)

        self.btn_export_opentrons = SecondaryButton("🤖 Export to Opentrons OT-2")
        self.btn_export_opentrons.clicked.connect(self._on_export_opentrons_clicked)
        ctrl_layout.addWidget(self.btn_export_opentrons)

        layout.addWidget(ctrl_box)

        # Worklist Transfer Table
        table_box = QGroupBox("Generated Robotic Pipetting Worklist (Tecan Format)")
        table_layout = QVBoxLayout(table_box)

        self.table_worklist = BioTableWidget()
        self.table_worklist.setRowCount(0)
        self.table_worklist.setColumnCount(6)
        self.table_worklist.setHorizontalHeaderLabels(
            [
                "Source_Plate",
                "Source_Well",
                "Destination_Plate",
                "Destination_Well",
                "Volume_uL",
                "Liquid_Class",
            ]
        )
        if (hv := self.table_worklist.horizontalHeader()) is not None:
            hv.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table_layout.addWidget(self.table_worklist)

        layout.addWidget(table_box)

    # -------------------------------------------------------------------------
    # TAB 3: INVENTORY & OLIGO TRACKER
    # -------------------------------------------------------------------------
    def _init_inventory_tab(self, parent: QWidget) -> None:
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)

        box = QGroupBox("Phase 2 LIMS Inventory Items & Purchase-Ready Oligos")
        box_layout = QVBoxLayout(box)

        self.table_inventory = BioTableWidget()
        self.table_inventory.setRowCount(0)
        self.table_inventory.setColumnCount(7)
        self.table_inventory.setHorizontalHeaderLabels(
            [
                "Item Barcode",
                "Type",
                "Name",
                "Concentration",
                "Volume / Scale",
                "Hierarchical Storage Location",
                "Details",
            ]
        )
        if (hv := self.table_inventory.horizontalHeader()) is not None:
            hv.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        box_layout.addWidget(self.table_inventory)

        layout.addWidget(box)

    # -------------------------------------------------------------------------
    # CONTROLLER SIGNALS & MVC SLOTS
    # -------------------------------------------------------------------------
    @Slot()
    def _on_generate_protocol_clicked(self) -> None:
        """Collects inputs from UI and launches background QThread calculation."""
        inserts = [
            {
                "name": self.txt_insert_name.text().strip(),
                "length_bp": self.spin_insert_bp.value(),
                "concentration_ng_ul": self.spin_insert_conc.value(),
                "molar_ratio": self.spin_molar_ratio.value(),
            }
        ]

        self.btn_generate.setEnabled(False)
        self.status_badge.setText("CALCULATING...")
        self.status_badge.setStyleSheet(
            f"background-color: {Colors.ACCENT_WARNING}; color: white; font-weight: bold; "
            "padding: 3px 10px; border-radius: 12px; font-size: 11px;"
        )
        self.progress_dialog = BioProgressDialog(
            "Calculating assembly protocol...", "Cancel", 0, 0, self
        )
        self.progress_dialog.show()

        # Launch QThread Worker
        self.worker = ProtocolWorker(
            num_reactions=self.spin_num_rxns.value(),
            vector_bp=self.spin_vector_bp.value(),
            vector_conc_ng_ul=self.spin_vector_conc.value(),
            inserts=inserts,
            assembly_type=self.combo_assembly_type.currentText(),
            overage_pct=self.spin_overage.value(),
            vector_mass_ng=self.spin_vector_mass.value(),
            default_molar_ratio=self.spin_molar_ratio.value(),
            reaction_volume_ul=self.spin_total_vol.value(),
            parent=self,
        )
        self.worker.finished_ok.connect(self._on_protocol_finished)
        self.worker.finished_err.connect(self._on_protocol_error)
        self.worker.start()

    @Slot(object)
    def _on_protocol_finished(self, protocol: dict[str, Any] | BenchProtocol) -> None:
        """Callback slot handling successful ProtocolEngine calculation from QThread."""
        self.current_protocol = protocol
        self.btn_generate.setEnabled(True)
        if self.progress_dialog is not None:
            self.progress_dialog.close()
            self.progress_dialog = None
        self.status_badge.setText("SUCCESS")
        self.status_badge.setStyleSheet(
            f"background-color: {Colors.ACCENT_SUCCESS}; color: white; font-weight: bold; "
            "padding: 3px 10px; border-radius: 12px; font-size: 11px;"
        )

        self._populate_results_tables(protocol)
        self._populate_worklist_table(protocol)
        show_toast("Assembly protocol generated successfully")

    @Slot(str)
    def _on_protocol_error(self, error_message: str) -> None:
        """Callback slot handling calculation errors from QThread worker."""
        self.btn_generate.setEnabled(True)
        if self.progress_dialog is not None:
            self.progress_dialog.close()
            self.progress_dialog = None
        self.status_badge.setText("ERROR")
        self.status_badge.setStyleSheet(
            f"background-color: {Colors.ACCENT_DANGER}; color: white; font-weight: bold; "
            "padding: 3px 10px; border-radius: 12px; font-size: 11px;"
        )
        show_error(
            self,
            title="Bench Protocol Error",
            message=f"Failed to calculate assembly protocol:\n\n{error_message}",
        )

    def _populate_results_tables(self, protocol: dict[str, Any] | BenchProtocol) -> None:
        """Populates Master Mix and Reaction Pipetting result tables."""
        # 1. Master Mix Table
        if isinstance(protocol, dict):
            mm_data = protocol.get("master_mix", {})
            mm_totals = mm_data.get("master_mix_volumes_total", {})
            mm_per_rxn = mm_data.get("component_volumes_per_rxn", {})
        else:
            mm_data = protocol.master_mix
            mm_totals = mm_data.master_mix_volumes_total
            mm_per_rxn = mm_data.component_volumes_per_rxn

        self.table_master_mix.setRowCount(0)
        for comp, tot_vol in mm_totals.items():
            per_rxn_vol = mm_per_rxn.get(comp, 0.0)
            row_idx = self.table_master_mix.rowCount()
            self.table_master_mix.insertRow(row_idx)
            self.table_master_mix.setItem(row_idx, 0, QTableWidgetItem(comp))
            self.table_master_mix.setItem(row_idx, 1, QTableWidgetItem(f"{per_rxn_vol:.3f}"))
            self.table_master_mix.setItem(row_idx, 2, QTableWidgetItem(f"{tot_vol:.3f}"))

        # 2. Pipetting Table
        if isinstance(protocol, dict):
            rr_data = protocol.get("reaction_ratio", {})
            v = rr_data.get("vector_spec", {})
            v_name = v.get("name", "Destination Vector")
            v_role = v.get("role", "vector")
            v_len = v.get("length_bp", 0)
            v_conc = v.get("concentration_ng_ul", 0.0)
            v_ratio = v.get("molar_ratio", 1.0)
            v_mass = v.get("target_mass_ng", 0.0)
            v_vol = v.get("volume_ul", 0.0)

            insert_specs = rr_data.get("insert_specs", [])
            water_vol = rr_data.get("water_volume_ul", 0.0)
        else:
            rr_data = protocol.reaction_ratio
            v = rr_data.vector_spec
            v_name = v.name
            v_role = v.role
            v_len = v.length_bp
            v_conc = v.concentration_ng_ul
            v_ratio = v.molar_ratio
            v_mass = v.target_mass_ng
            v_vol = v.volume_ul

            insert_specs = rr_data.insert_specs
            water_vol = rr_data.water_volume_ul

        self.table_pipetting.setRowCount(0)

        # Vector row
        self._add_pipetting_row(
            v_name,
            v_role,
            v_len,
            v_conc,
            v_ratio,
            v_mass,
            v_vol,
        )

        # Insert rows
        for ins in insert_specs:
            if isinstance(ins, dict):
                self._add_pipetting_row(
                    ins.get("name", "Insert"),
                    ins.get("role", "insert"),
                    ins.get("length_bp", 0),
                    ins.get("concentration_ng_ul", 0.0),
                    ins.get("molar_ratio", 0.0),
                    ins.get("target_mass_ng", 0.0),
                    ins.get("volume_ul", 0.0),
                )
            else:
                self._add_pipetting_row(
                    ins.name,
                    ins.role,
                    ins.length_bp,
                    ins.concentration_ng_ul,
                    ins.molar_ratio,
                    ins.target_mass_ng,
                    ins.volume_ul,
                )

        # Water row
        if water_vol > 0:
            self._add_pipetting_row(
                "Nuclease-Free Water",
                "diluent",
                0,
                0.0,
                0.0,
                0.0,
                water_vol,
            )

    def _add_pipetting_row(
        self,
        name: str,
        role: str,
        length: int,
        conc: float,
        ratio: float,
        mass: float,
        vol: float,
    ) -> None:
        row_idx = self.table_pipetting.rowCount()
        self.table_pipetting.insertRow(row_idx)
        self.table_pipetting.setItem(row_idx, 0, QTableWidgetItem(name))
        self.table_pipetting.setItem(row_idx, 1, QTableWidgetItem(role))
        self.table_pipetting.setItem(row_idx, 2, QTableWidgetItem(str(length)))
        self.table_pipetting.setItem(row_idx, 3, QTableWidgetItem(f"{conc:.1f}"))
        self.table_pipetting.setItem(row_idx, 4, QTableWidgetItem(f"{ratio:.1f}"))
        self.table_pipetting.setItem(row_idx, 5, QTableWidgetItem(f"{mass:.1f}"))
        self.table_pipetting.setItem(row_idx, 6, QTableWidgetItem(f"{vol:.3f}"))

    def _populate_worklist_table(self, protocol: dict[str, Any] | BenchProtocol) -> None:
        """Populates the Liquid Handler worklist preview table."""
        self.table_worklist.setRowCount(0)

        try:
            # Generate transfer list
            transfers = []
            if isinstance(protocol, dict):
                num_reactions = protocol.get("num_reactions", 1)
                rr = protocol.get("reaction_ratio", {})
                mm_vol = rr.get("master_mix_volume_ul", 0.0)
                water_vol = rr.get("water_volume_ul", 0.0)
                v_spec = rr.get("vector_spec", {})
                v_vol = v_spec.get("volume_ul", 0.0)
                insert_specs = rr.get("insert_specs", [])
            else:
                num_reactions = protocol.num_reactions
                rr = protocol.reaction_ratio
                mm_vol = rr.master_mix_volume_ul
                water_vol = rr.water_volume_ul
                v_spec = rr.vector_spec
                v_vol = v_spec.volume_ul
                insert_specs = rr.insert_specs

            for rxn_idx in range(num_reactions):
                dest_well = WorklistGenerator.index_to_well(rxn_idx)
                # MM
                transfers.append(
                    (
                        self.txt_source_plate.text(),
                        "A1",
                        self.txt_dest_plate.text(),
                        dest_well,
                        f"{mm_vol:.3f}",
                        "MasterMix_Viscous",
                    )
                )
                # Water
                if water_vol > 0:
                    transfers.append(
                        (
                            self.txt_source_plate.text(),
                            "B1",
                            self.txt_dest_plate.text(),
                            dest_well,
                            f"{water_vol:.3f}",
                            "Water_FreeSingle",
                        )
                    )
                # Vector
                transfers.append(
                    (
                        "VECTOR_PLATE_1",
                        "A1",
                        self.txt_dest_plate.text(),
                        dest_well,
                        f"{v_vol:.3f}",
                        "DNA_LowVolume",
                    )
                )
                # Inserts
                for ins_idx, ins in enumerate(insert_specs):
                    src_w = WorklistGenerator.index_to_well(ins_idx)
                    ins_vol = ins.get("volume_ul", 0.0) if isinstance(ins, dict) else ins.volume_ul
                    transfers.append(
                        (
                            "INSERT_PLATE_1",
                            src_w,
                            self.txt_dest_plate.text(),
                            dest_well,
                            f"{ins_vol:.3f}",
                            "DNA_LowVolume",
                        )
                    )

            for tr in transfers:
                row = self.table_worklist.rowCount()
                self.table_worklist.insertRow(row)
                for col, val in enumerate(tr):
                    self.table_worklist.setItem(row, col, QTableWidgetItem(val or ""))

        except Exception:
            pass

    @Slot()
    def _on_export_csv_clicked(self) -> None:
        """Export handler opening QFileDialog and executing WorklistGenerator export."""
        if not self.current_protocol:
            show_warning(
                self,
                title="No Protocol Available",
                message="Please generate a bench assembly protocol first before exporting to CSV.",
            )
            return

        filepath = get_save_path(
            self,
            title="Export Tecan Liquid Handler Worklist",
            start_dir="tecan_worklist.csv",
            file_filter="CSV Files (*.csv);;All Files (*)",
        )

        if filepath:
            try:
                if isinstance(self.current_protocol, dict):
                    num_reactions = self.current_protocol.get("num_reactions", 1)
                    rr = self.current_protocol.get("reaction_ratio", {})
                else:
                    num_reactions = self.current_protocol.num_reactions
                    rr = self.current_protocol.reaction_ratio

                reactions = [rr] * num_reactions
                out_file = WorklistGenerator.export_to_tecan_csv(
                    reactions_list=reactions,
                    filepath=filepath,
                    default_dest_plate=self.txt_dest_plate.text(),
                )
                show_toast("Successfully exported Tecan worklist")
                show_info(
                    self,
                    title="Export Successful",
                    message=f"Successfully exported Tecan worklist to:\n{out_file}",
                )
            except RobotExportError as e:
                show_error(
                    self,
                    title="Robot Export Error",
                    message=f"Failed to export Tecan CSV:\n{e}",
                )

    def _on_export_opentrons_clicked(self) -> None:
        """Placeholder notification for upcoming Opentrons OT-2 liquid handler export."""
        show_toast("Opentrons OT-2 export coming in v2.1")

    def _load_sample_inventory(self) -> None:
        """Populates the LIMS inventory table with Phase 2 data models."""
        self.table_inventory.setRowCount(0)

        # Sample 1: Storage Location + Reagent
        loc1 = StorageLocation("Freezer-80C", "Rack-01", "Box-A", "A01")
        reagent = Reagent(
            id="RGT-101",
            name="Gibson Assembly 2X Master Mix",
            lot_number="LOT-2026-99",
            concentration=2.0,
            concentration_unit="X",
            volume_ul=500.0,
            storage_location=loc1,
            supplier="NEB",
            catalog_number="E2611S",
        )

        # Sample 2: Oligo
        loc2 = StorageLocation("Freezer-20C", "Rack-02", "Box-B", "C03")
        oligo = Oligo(
            id="OLG-201",
            name="pET28a_FWD_Primer",
            sequence="GAATTCCGCCAGGGTTTTCCCAGTCACGAC",
            tm=63.1,
            gc_content=58.3,
            plate_id="PLATE-01",
            well_position="C03",
            scale="100nm",
            purification="HPLC",
            storage_location=loc2,
        )

        # Sample 3: Synthesized Plasmid
        loc3 = StorageLocation("Freezer-20C", "Rack-02", "Box-B", "D04")
        plasmid = PlasmidInventoryItem(
            id="PLSM-301",
            name="pET28a-GFP-Assembly",
            sequence="ATGCG...",
            vector_backbone="pET28a",
            lot_number="LOT-PL-01",
            storage_location=loc3,
            concentration_ng_ul=250.0,
        )

        items = [
            (
                reagent.barcode,
                "Reagent",
                reagent.name,
                f"{reagent.concentration} {reagent.concentration_unit}",
                f"{reagent.volume_ul:.1f} µL",
                loc1.barcode,
                f"Lot: {reagent.lot_number} | {reagent.supplier}",
            ),
            (
                oligo.barcode,
                "Oligo",
                oligo.name,
                f"Tm: {oligo.tm}°C | GC: {oligo.gc_content}%",
                f"{oligo.scale} ({oligo.purification})",
                loc2.barcode,
                f"Plate: {oligo.plate_id} Well: {oligo.well_position}",
            ),
            (
                plasmid.barcode,
                "Plasmid",
                plasmid.name,
                f"{plasmid.concentration_ng_ul} ng/µL",
                f"Backbone: {plasmid.vector_backbone}",
                loc3.barcode,
                f"Lot: {plasmid.lot_number}",
            ),
        ]

        for item in items:
            row = self.table_inventory.rowCount()
            self.table_inventory.insertRow(row)
            for col, val in enumerate(item):
                self.table_inventory.setItem(row, col, QTableWidgetItem(val or ""))

    def teardown(self) -> None:
        """Stops active background ProtocolWorker if running."""
        if hasattr(self, "progress_dialog") and self.progress_dialog is not None:
            self.progress_dialog.close()
            self.progress_dialog = None
        if self.worker is not None:
            self.worker.stop_and_wait(1000)
            self.worker = None

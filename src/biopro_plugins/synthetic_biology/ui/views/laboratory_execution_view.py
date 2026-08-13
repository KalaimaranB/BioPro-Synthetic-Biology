"""PyQt6 Graphical View & QThread Worker for Laboratory Execution & Phase 2 Build Cycle.

Provides Master Mix & Molar Ratio Calculation UI, Liquid Handler Worklist
Exporter (Tecan CSV), and LIMS Inventory & Oligo Tracker tabs. Implements
strict MVC architecture by offloading all computational engine routines to a
background QThread (ProtocolWorker).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...analysis.assembly.protocol_engine import (
    BenchProtocol,
    ProtocolEngine,
)
from ...models.inventory_models import (
    Oligo,
    PlasmidInventoryItem,
    Reagent,
    StorageLocation,
)
from ...utils.robot_exporter import RobotExportError, WorklistGenerator


class ProtocolWorker(QThread):
    """Background QThread worker executing ProtocolEngine computational routines
    off the main GUI thread.
    """

    finished = pyqtSignal(object)  # Emits BenchProtocol instance on success
    error = pyqtSignal(str)  # Emits error description string on failure

    def __init__(
        self,
        num_reactions: int,
        vector_bp: int,
        vector_conc_ng_ul: float,
        inserts: List[Dict[str, Any]],
        assembly_type: str = "Gibson",
        overage_pct: float = 10.0,
        vector_mass_ng: float = 50.0,
        default_molar_ratio: float = 3.0,
        reaction_volume_ul: float = 20.0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
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
            self.finished.emit(protocol)
        except Exception as exc:
            self.error.emit(str(exc))


try:
    from biopro.ui.theme import Colors, Fonts, theme_manager
except ImportError:
    try:
        from biopro_sdk.plugin.theme_fallback import Colors, Fonts, theme_manager
    except ImportError:

        class Colors:
            BG_DARKEST = "#0d1117"
            BG_DARK = "#161b22"
            BG_MEDIUM = "#21262d"
            FG_PRIMARY = "#e6edf3"
            FG_SECONDARY = "#8b949e"
            FG_DISABLED = "#484f58"
            BORDER = "#30363d"
            ACCENT_PRIMARY = "#00bcd4"

        class Fonts:
            SIZE_SMALL = 11

        class _DummySignal:
            def connect(self, cb):
                pass

        class _DummyThemeManager:
            theme_changed = _DummySignal()

        theme_manager = _DummyThemeManager()


class LaboratoryExecutionView(QWidget):
    """PyQt6 View for Laboratory Execution, Master Mix Calculation, Liquid
    Handling Export, and LIMS Inventory Tracking. Theme-aware design inheriting
    global application stylesheets.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.current_protocol: Optional[BenchProtocol] = None
        self.worker: Optional[ProtocolWorker] = None

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
            "font-weight: bold; padding: 3px 10px; "
            "border-radius: 12px; font-size: 11px;"
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
    def _init_calculator_tab(self, parent: QWidget) -> None:
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(10, 10, 10, 10)

        # Left Column: Inputs Box
        input_box = QGroupBox("Assembly Parameters & DNA Fragments")
        input_layout = QVBoxLayout(input_box)

        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Assembly Method
        self.combo_assembly_type = QComboBox()
        self.combo_assembly_type.addItems(["Gibson Assembly", "Golden Gate Assembly"])
        form_layout.addRow("Assembly Method:", self.combo_assembly_type)

        # Num Reactions
        self.spin_num_rxns = QSpinBox()
        self.spin_num_rxns.setRange(1, 96)
        self.spin_num_rxns.setValue(4)
        form_layout.addRow("Number of Reactions:", self.spin_num_rxns)

        # Overage %
        self.spin_overage = QDoubleSpinBox()
        self.spin_overage.setRange(0.0, 50.0)
        self.spin_overage.setValue(10.0)
        self.spin_overage.setSuffix(" %")
        form_layout.addRow("Overage Allowance:", self.spin_overage)

        # Total Reaction Volume
        self.spin_total_vol = QDoubleSpinBox()
        self.spin_total_vol.setRange(10.0, 100.0)
        self.spin_total_vol.setValue(20.0)
        self.spin_total_vol.setSuffix(" µL")
        form_layout.addRow("Reaction Volume:", self.spin_total_vol)

        # Target Vector Mass
        self.spin_vector_mass = QDoubleSpinBox()
        self.spin_vector_mass.setRange(10.0, 500.0)
        self.spin_vector_mass.setValue(50.0)
        self.spin_vector_mass.setSuffix(" ng")
        form_layout.addRow("Vector Target Mass:", self.spin_vector_mass)

        # Vector Specs
        self.txt_vector_name = QLineEdit("pET28a_Vector")
        form_layout.addRow("Vector Name:", self.txt_vector_name)

        self.spin_vector_bp = QSpinBox()
        self.spin_vector_bp.setRange(500, 50000)
        self.spin_vector_bp.setValue(3000)
        self.spin_vector_bp.setSuffix(" bp")
        form_layout.addRow("Vector Length:", self.spin_vector_bp)

        self.spin_vector_conc = QDoubleSpinBox()
        self.spin_vector_conc.setRange(1.0, 1000.0)
        self.spin_vector_conc.setValue(50.0)
        self.spin_vector_conc.setSuffix(" ng/µL")
        form_layout.addRow("Vector Conc:", self.spin_vector_conc)

        # Insert 1 Specs
        self.txt_insert_name = QLineEdit("GFP_Insert")
        form_layout.addRow("Insert 1 Name:", self.txt_insert_name)

        self.spin_insert_bp = QSpinBox()
        self.spin_insert_bp.setRange(50, 20000)
        self.spin_insert_bp.setValue(1000)
        self.spin_insert_bp.setSuffix(" bp")
        form_layout.addRow("Insert 1 Length:", self.spin_insert_bp)

        self.spin_insert_conc = QDoubleSpinBox()
        self.spin_insert_conc.setRange(1.0, 1000.0)
        self.spin_insert_conc.setValue(30.0)
        self.spin_insert_conc.setSuffix(" ng/µL")
        form_layout.addRow("Insert 1 Conc:", self.spin_insert_conc)

        self.spin_molar_ratio = QDoubleSpinBox()
        self.spin_molar_ratio.setRange(1.0, 10.0)
        self.spin_molar_ratio.setValue(3.0)
        self.spin_molar_ratio.setSuffix(" : 1")
        form_layout.addRow("Insert:Vector Ratio:", self.spin_molar_ratio)

        input_layout.addLayout(form_layout)

        # Progress Bar & Calculate Button
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setVisible(False)
        input_layout.addWidget(self.progress_bar)
        self.btn_generate = QPushButton("⚡ Generate Bench Protocol")
        self.btn_generate.setProperty("variant", "primary")
        self.btn_generate.setObjectName("PrimaryButton")
        hover_primary = getattr(Colors, "ACCENT_PRIMARY_HOVER", "#0097a7")
        self.btn_generate.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ACCENT_PRIMARY}; "
            f"color: {Colors.BG_DARKEST}; font-weight: bold; padding: 10px; "
            f"border-radius: 4px; font-size: 13px; }}\n"
            f"QPushButton:hover {{ background-color: {hover_primary}; "
            f"color: {Colors.BG_DARKEST}; }}"
        )
        self.btn_generate.clicked.connect(self._on_generate_protocol_clicked)
        input_layout.addWidget(self.btn_generate)

        layout.addWidget(input_box, stretch=1)

        # Right Column: Output Results Tables
        output_box = QGroupBox("Calculated Master Mix & Reaction Pipetting Table")
        output_layout = QVBoxLayout(output_box)

        output_splitter = QSplitter(Qt.Orientation.Vertical)

        # Table 1: Master Mix
        mm_widget = QWidget()
        mm_layout = QVBoxLayout(mm_widget)
        mm_layout.setContentsMargins(0, 0, 0, 0)
        mm_lbl = QLabel("1. Master Mix Preparation Table")
        mm_lbl.setStyleSheet("font-weight: bold;")
        mm_layout.addWidget(mm_lbl)

        self.table_master_mix = QTableWidget(0, 3)
        self.table_master_mix.setHorizontalHeaderLabels(
            ["Reagent Component", "Per Reaction (µL)", "Total Master Mix (µL)"]
        )
        self.table_master_mix.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        mm_layout.addWidget(self.table_master_mix)
        output_splitter.addWidget(mm_widget)

        # Table 2: Fragment Pipetting
        pip_widget = QWidget()
        pip_layout = QVBoxLayout(pip_widget)
        pip_layout.setContentsMargins(0, 0, 0, 0)
        pip_lbl = QLabel("2. Reaction Fragment Pipetting Specifications")
        pip_lbl.setStyleSheet("font-weight: bold;")
        pip_layout.addWidget(pip_lbl)

        self.table_pipetting = QTableWidget(0, 7)
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
        self.table_pipetting.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
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
        self.txt_source_plate = QLineEdit("REAGENT_PLATE_1")
        ctrl_layout.addWidget(self.txt_source_plate)

        ctrl_layout.addWidget(QLabel("Destination Plate ID:"))
        self.txt_dest_plate = QLineEdit("DEST_PLATE_1")
        ctrl_layout.addWidget(self.txt_dest_plate)

        self.btn_export_csv = QPushButton("🤖 Export to Tecan CSV")
        self.btn_export_csv.setProperty("variant", "primary")
        self.btn_export_csv.setObjectName("PrimaryButton")
        hover_primary = getattr(Colors, "ACCENT_PRIMARY_HOVER", "#0097a7")
        self.btn_export_csv.setStyleSheet(
            f"QPushButton {{ background-color: {Colors.ACCENT_PRIMARY}; "
            f"color: {Colors.BG_DARKEST}; font-weight: bold; padding: 8px 16px; "
            f"border-radius: 4px; }}\n"
            f"QPushButton:hover {{ background-color: {hover_primary}; "
            f"color: {Colors.BG_DARKEST}; }}"
        )
        self.btn_export_csv.clicked.connect(self._on_export_csv_clicked)
        ctrl_layout.addWidget(self.btn_export_csv)

        layout.addWidget(ctrl_box)

        # Worklist Transfer Table
        table_box = QGroupBox("Generated Robotic Pipetting Worklist (Tecan Format)")
        table_layout = QVBoxLayout(table_box)

        self.table_worklist = QTableWidget(0, 6)
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
        self.table_worklist.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
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

        self.table_inventory = QTableWidget(0, 7)
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
        self.table_inventory.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        box_layout.addWidget(self.table_inventory)

        layout.addWidget(box)

    # -------------------------------------------------------------------------
    # CONTROLLER SIGNALS & MVC SLOTS
    # -------------------------------------------------------------------------
    @pyqtSlot()
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
        self.progress_bar.setVisible(True)
        self.status_badge.setText("CALCULATING...")
        self.status_badge.setStyleSheet(
            "background-color: #D97706; color: white; font-weight: bold; "
            "padding: 3px 10px; border-radius: 12px; font-size: 11px;"
        )

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
        self.worker.finished.connect(self._on_protocol_finished)
        self.worker.error.connect(self._on_protocol_error)
        self.worker.start()

    @pyqtSlot(object)
    def _on_protocol_finished(self, protocol: BenchProtocol) -> None:
        """Callback slot handling successful ProtocolEngine calculation from QThread."""
        self.current_protocol = protocol
        self.btn_generate.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_badge.setText("SUCCESS")
        self.status_badge.setStyleSheet(
            "background-color: #059669; color: white; font-weight: bold; "
            "padding: 3px 10px; border-radius: 12px; font-size: 11px;"
        )

        self._populate_results_tables(protocol)
        self._populate_worklist_table(protocol)

    @pyqtSlot(str)
    def _on_protocol_error(self, error_message: str) -> None:
        """Callback slot handling calculation errors from QThread worker."""
        self.btn_generate.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_badge.setText("ERROR")
        self.status_badge.setStyleSheet(
            "background-color: #E11D48; color: white; font-weight: bold; "
            "padding: 3px 10px; border-radius: 12px; font-size: 11px;"
        )
        QMessageBox.critical(
            self,
            "Bench Protocol Error",
            f"Failed to calculate assembly protocol:\n\n{error_message}",
        )

    def _populate_results_tables(self, protocol: BenchProtocol) -> None:
        """Populates Master Mix and Reaction Pipetting result tables."""
        # 1. Master Mix Table
        mm_data = protocol.master_mix
        self.table_master_mix.setRowCount(0)
        for comp, tot_vol in mm_data.master_mix_volumes_total.items():
            per_rxn_vol = mm_data.component_volumes_per_rxn.get(comp, 0.0)
            row_idx = self.table_master_mix.rowCount()
            self.table_master_mix.insertRow(row_idx)
            self.table_master_mix.setItem(row_idx, 0, QTableWidgetItem(comp))
            self.table_master_mix.setItem(
                row_idx, 1, QTableWidgetItem(f"{per_rxn_vol:.3f}")
            )
            self.table_master_mix.setItem(
                row_idx, 2, QTableWidgetItem(f"{tot_vol:.3f}")
            )

        # 2. Pipetting Table
        rr_data = protocol.reaction_ratio
        self.table_pipetting.setRowCount(0)

        # Vector row
        v = rr_data.vector_spec
        self._add_pipetting_row(
            v.name,
            v.role,
            v.length_bp,
            v.concentration_ng_ul,
            v.molar_ratio,
            v.target_mass_ng,
            v.volume_ul,
        )

        # Insert rows
        for ins in rr_data.insert_specs:
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
        if rr_data.water_volume_ul > 0:
            self._add_pipetting_row(
                "Nuclease-Free Water",
                "diluent",
                0,
                0.0,
                0.0,
                0.0,
                rr_data.water_volume_ul,
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

    def _populate_worklist_table(self, protocol: BenchProtocol) -> None:
        """Populates the Liquid Handler worklist preview table."""
        self.table_worklist.setRowCount(0)

        try:
            # Generate transfer list
            transfers = []
            for rxn_idx in range(protocol.num_reactions):
                dest_well = WorklistGenerator.index_to_well(rxn_idx)
                rr = protocol.reaction_ratio
                # MM
                transfers.append((
                    self.txt_source_plate.text(), "A1",
                    self.txt_dest_plate.text(), dest_well,
                    f"{rr.master_mix_volume_ul:.3f}", "MasterMix_Viscous"
                ))
                # Water
                if rr.water_volume_ul > 0:
                    transfers.append((
                        self.txt_source_plate.text(), "B1",
                        self.txt_dest_plate.text(), dest_well,
                        f"{rr.water_volume_ul:.3f}", "Water_FreeSingle"
                    ))
                # Vector
                transfers.append((
                    "VECTOR_PLATE_1", "A1",
                    self.txt_dest_plate.text(), dest_well,
                    f"{rr.vector_spec.volume_ul:.3f}", "DNA_LowVolume"
                ))
                # Inserts
                for ins_idx, ins in enumerate(rr.insert_specs):
                    src_w = WorklistGenerator.index_to_well(ins_idx)
                    transfers.append((
                        "INSERT_PLATE_1", src_w,
                        self.txt_dest_plate.text(), dest_well,
                        f"{ins.volume_ul:.3f}", "DNA_LowVolume"
                    ))

            for tr in transfers:
                row = self.table_worklist.rowCount()
                self.table_worklist.insertRow(row)
                for col, val in enumerate(tr):
                    self.table_worklist.setItem(row, col, QTableWidgetItem(val))

        except Exception:
            pass

    @pyqtSlot()
    def _on_export_csv_clicked(self) -> None:
        """Export handler opening QFileDialog and executing WorklistGenerator export."""
        if not self.current_protocol:
            QMessageBox.warning(
                self,
                "No Protocol Available",
                "Please generate a bench assembly protocol first before "
                "exporting to CSV.",
            )
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Tecan Liquid Handler Worklist",
            "tecan_worklist.csv",
            "CSV Files (*.csv);;All Files (*)",
        )

        if filepath:
            try:
                reactions = (
                    [self.current_protocol.reaction_ratio]
                    * self.current_protocol.num_reactions
                )
                out_file = WorklistGenerator.export_to_tecan_csv(
                    reactions_list=reactions,
                    filepath=filepath,
                    default_dest_plate=self.txt_dest_plate.text(),
                )
                QMessageBox.information(
                    self,
                    "Export Successful",
                    f"Successfully exported Tecan worklist to:\n{out_file}",
                )
            except RobotExportError as e:
                QMessageBox.critical(
                    self, "Robot Export Error", f"Failed to export Tecan CSV:\n{e}"
                )

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
                self.table_inventory.setItem(row, col, QTableWidgetItem(val))

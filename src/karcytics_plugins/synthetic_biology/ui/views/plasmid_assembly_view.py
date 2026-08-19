"""Primary PyQt6 Plasmid & Vector Assembly View (Benchling-grade visual design
view).

Includes a drag-and-drop Part Palette, Assembly Canvas / Vector drop-zone,
interactive sequence feature viewer, file importer (FASTA/GenBank), and
automated primer designer. Decoupled from engines via PlasmidAssemblyController
signals & slots.
"""

from __future__ import annotations

import json
from typing import List

from karcytics_sdk.plugin.theme_fallback import Colors, theme_manager
from PyQt6.QtCore import QMimeData, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...analysis.models.domain import PlasmidVector
from ...analysis.parts.base import BiologicalPart
from ...analysis.parts.components import CDS, RBS, Promoter, Terminator
from ...analysis.state import SynBioState
from ...ui.controllers.plasmid_controller import PlasmidAssemblyController


class PartPaletteWidget(QListWidget):
    """Drag-and-drop palette containing standard biological parts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return

        part_data = item.data(Qt.ItemDataRole.UserRole)
        if not part_data:
            return

        mime_data = QMimeData()
        json_bytes = json.dumps(part_dict_serialize(part_data)).encode("utf-8")
        mime_data.setData("application/x-synbio-part", json_bytes)

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)


def part_dict_serialize(part_data: dict) -> dict:
    return part_data


class AssemblyCanvasWidget(QListWidget):
    """Drop zone for assembly order placement."""

    parts_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def dragEnterEvent(self, event):
        if (
            event.mimeData().hasFormat("application/x-synbio-part")
            or event.source() == self
        ):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-synbio-part"):
            data_bytes = event.mimeData().data("application/x-synbio-part")
            part_dict = json.loads(bytes(data_bytes).decode("utf-8"))

            item = QListWidgetItem(
                f"🧩 {part_dict['name']} [{part_dict['part_type'].upper()}]"
            )
            item.setData(Qt.ItemDataRole.UserRole, part_dict)
            self.addItem(item)
            event.acceptProposedAction()
            self.parts_changed.emit()
        else:
            super().dropEvent(event)
            self.parts_changed.emit()


class PrimerDesignDialog(QDialog):
    """Modal dialog for automated PCR & assembly primer design."""

    def __init__(
        self, target_sequence: str, controller: PlasmidAssemblyController, parent=None
    ):
        super().__init__(parent)
        self.controller = controller
        self.target_sequence = target_sequence
        self.setWindowTitle("Automated Primer Designer")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.tm_spin = QDoubleSpinBox()
        self.tm_spin.setRange(45.0, 75.0)
        self.tm_spin.setValue(60.0)
        form.addRow("Target Tm (°C):", self.tm_spin)

        self.fwd_overhang_edit = QLineEdit()
        self.fwd_overhang_edit.setPlaceholderText(
            "e.g. GAATTC (Restriction / Gibson Overhang)"
        )
        form.addRow("Forward Overhang 5':", self.fwd_overhang_edit)

        self.rev_overhang_edit = QLineEdit()
        self.rev_overhang_edit.setPlaceholderText(
            "e.g. AAGCTT (Restriction / Gibson Overhang)"
        )
        form.addRow("Reverse Overhang 5':", self.rev_overhang_edit)

        layout.addLayout(form)

        self.btn_design = QPushButton("Design Primers")
        self.btn_design.clicked.connect(self._on_design_clicked)
        layout.addWidget(self.btn_design)

        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.result_display)

    def _on_design_clicked(self):
        if not self.target_sequence:
            self.result_display.setText("Error: Target sequence is empty.")
            return

        primers = self.controller.handle_primer_design(
            sequence=self.target_sequence,
            target_tm=self.tm_spin.value(),
            fwd_overhang=self.fwd_overhang_edit.text().strip(),
            rev_overhang=self.rev_overhang_edit.text().strip(),
        )

        out = "=== AUTOMATED PCR PRIMERS DESIGNED ===\n\n"
        for p in primers:
            out += (
                f"[{p.name}]\nSequence 5'->3': {p.sequence}\n"
                f"Tm: {p.tm:.1f}°C | GC%: {p.gc_content:.1f}%\n\n"
            )
        self.result_display.setText(out)


class PlasmidAssemblyView(QWidget):
    """PyQt6 View for plasmid assembly, Drag-and-Drop part ordering, and Sequence
    viewer.
    """

    assembly_requested = pyqtSignal(str, list)
    file_parse_requested = pyqtSignal(str, str)
    primer_requested = pyqtSignal(str, float, str, str)

    def __init__(
        self, state: SynBioState, controller: PlasmidAssemblyController, parent=None
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.state = state
        self.controller = controller

        self._init_ui()
        self._connect_signals()

        # Load default library items
        self._populate_part_library()

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

    def _init_ui(self):
        self.setObjectName("plasmid_assembly_view")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: Biological Parts Palette
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl_palette = QLabel("🧬 Biological Parts Library")
        lbl_palette.setStyleSheet("font-size: 14px; font-weight: bold;")
        left_layout.addWidget(lbl_palette)

        self.part_palette = PartPaletteWidget()
        left_layout.addWidget(self.part_palette)

        splitter.addWidget(left_panel)

        # Center Panel: Visual Canvas & Sequence Assembly Drop-Zone
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        self.name_edit = QLineEdit("pBioPro_v1")
        toolbar.addWidget(QLabel("Plasmid Name:"))
        toolbar.addWidget(self.name_edit)

        self.btn_import = QPushButton("📁 Import File")
        self.btn_import.clicked.connect(self._on_import_clicked)
        toolbar.addWidget(self.btn_import)

        self.btn_assemble = QPushButton("⚡ Assemble Construct")
        self.btn_assemble.clicked.connect(self._on_assemble_clicked)
        toolbar.addWidget(self.btn_assemble)

        self.btn_primer = QPushButton("🧬 Design Primers")
        self.btn_primer.clicked.connect(self._on_primer_clicked)
        toolbar.addWidget(self.btn_primer)

        center_layout.addLayout(toolbar)

        lbl_canvas = QLabel(
            "Drop Parts Below to Assemble Genetic Construct (Drag to Reorder):"
        )
        center_layout.addWidget(lbl_canvas)

        self.assembly_canvas = AssemblyCanvasWidget()
        center_layout.addWidget(self.assembly_canvas)

        splitter.addWidget(center_panel)

        # Right Panel: Feature Map & Sequence Output
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        lbl_map = QLabel("🗺️ Feature Map & Sequence Viewer")
        lbl_map.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_layout.addWidget(lbl_map)

        self.feature_table = QTableWidget(0, 5)
        self.feature_table.setHorizontalHeaderLabels(
            ["Name", "Type", "Start", "End", "Strand"]
        )
        if (hv := self.feature_table.horizontalHeader()) is not None:

            hv.setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        right_layout.addWidget(self.feature_table)

        self.seq_display = QTextEdit()
        self.seq_display.setReadOnly(True)
        self.seq_display.setPlaceholderText(
            "Assembled sequence display (FASTA / GenBank)..."
        )
        self.seq_display.setStyleSheet("font-family: monospace;")
        right_layout.addWidget(self.seq_display)

        splitter.addWidget(right_panel)

        splitter.setSizes([200, 400, 350])
        layout.addWidget(splitter)

    def _connect_signals(self):
        # Connect View signals to Controller slots
        self.assembly_requested.connect(self.controller.handle_assemble_request)
        self.file_parse_requested.connect(self.controller.handle_file_parse_request)

        # Connect Controller signals to View slots
        self.controller.assembly_ready.connect(self.render_plasmid)
        self.controller.error_raised.connect(self._show_error)

    def _populate_part_library(self):
        sample_parts = [
            Promoter(
                id="pTac",
                name="pTac Promoter",
                sequence="TTGACAATTAATCATCGGCTCGTATAATGTGTGG",
                y_min=0.01,
                y_max=4.5,
            ),
            RBS(
                id="B0034",
                name="RBS B0034",
                sequence="AAAGAGGAGAA",
                translation_initiation_rate=1.0,
            ),
            CDS(
                id="GFP",
                name="GFP Reporter",
                sequence="ATGAGTAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTTAATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATACGGAAAACTTACCCTTAAATTTATTTGCACTACTGGAAAACTACCTGTTCCATGGCCAACACTTGTCACTACTTTCGGTTATGGTGTTCAATGCTTTGCG",
                product="GFP",
            ),
            Terminator(
                id="B0015",
                name="B0015 Terminator",
                sequence="CCAGGCATCAAATAAAACGAAAGGCTCAGTCGAAAGACTGGGCCTTTCGTTTTATCTGTTGTTTGTCGGTGAACGCTCTC",
                termination_efficiency=0.98,
            ),
        ]

        for p in sample_parts:
            item = QListWidgetItem(f"📌 {p.name} ({p.part_type.upper()})")
            item.setData(Qt.ItemDataRole.UserRole, p.to_dict())
            self.part_palette.addItem(item)

    def _on_assemble_clicked(self):
        parts: List[BiologicalPart] = []
        for i in range(self.assembly_canvas.count()):
            item = self.assembly_canvas.item(i)
            p_dict = item.data(Qt.ItemDataRole.UserRole)
            ptype = p_dict.get("part_type", "cds")

            if ptype == "promoter":
                parts.append(
                    Promoter(
                        id=p_dict["id"],
                        name=p_dict["name"],
                        sequence=p_dict.get("sequence", ""),
                    )
                )
            elif ptype == "rbs":
                parts.append(
                    RBS(
                        id=p_dict["id"],
                        name=p_dict["name"],
                        sequence=p_dict.get("sequence", ""),
                    )
                )
            elif ptype == "cds":
                parts.append(
                    CDS(
                        id=p_dict["id"],
                        name=p_dict["name"],
                        sequence=p_dict.get("sequence", ""),
                    )
                )
            elif ptype == "terminator":
                parts.append(
                    Terminator(
                        id=p_dict["id"],
                        name=p_dict["name"],
                        sequence=p_dict.get("sequence", ""),
                    )
                )

        if not parts:
            QMessageBox.warning(
                self,
                "Assembly Warning",
                "Please drag at least one part into the canvas.",
            )
            return

        vector_name = self.name_edit.text().strip() or "pBioPro_Vector"
        self.assembly_requested.emit(vector_name, parts)

    def _on_import_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Sequence File",
            "",
            "GenBank/FASTA Files (*.gb *.gbk *.genbank *.fa *.fasta)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            fmt = "fasta" if file_path.endswith((".fa", ".fasta")) else "genbank"
            self.file_parse_requested.emit(content, fmt)
        except Exception as ex:
            self._show_error(f"Failed to read file: {str(ex)}")

    def _on_primer_clicked(self):
        plasmid = self.state.get_active_plasmid()
        if not plasmid or not plasmid.sequence:
            QMessageBox.warning(
                self, "Primer Warning", "Assemble or import a plasmid vector first."
            )
            return

        dlg = PrimerDesignDialog(
            target_sequence=plasmid.sequence, controller=self.controller, parent=self
        )
        dlg.exec()

    @pyqtSlot(PlasmidVector)
    def render_plasmid(self, vector: PlasmidVector):
        """Renders assembled or imported plasmid into feature map and sequence
        display.
        """
        self.name_edit.setText(vector.name)

        # Update feature table
        self.feature_table.setRowCount(0)
        for feat in vector.features:
            row = self.feature_table.rowCount()
            self.feature_table.insertRow(row)

            self.feature_table.setItem(row, 0, QTableWidgetItem(feat.name))
            self.feature_table.setItem(
                row, 1, QTableWidgetItem(feat.feature_type.upper())
            )
            self.feature_table.setItem(row, 2, QTableWidgetItem(str(feat.start)))
            self.feature_table.setItem(row, 3, QTableWidgetItem(str(feat.end)))
            self.feature_table.setItem(
                row, 4, QTableWidgetItem("+" if feat.strand >= 0 else "-")
            )

        # Update sequence text display
        topology_str = "Circular" if vector.is_circular else "Linear"
        header = f"> {vector.name} | {vector.length} bp | {topology_str}\n"
        formatted_seq = "\n".join(
            [vector.sequence[i : i + 60] for i in range(0, len(vector.sequence), 60)]
        )
        self.seq_display.setText(header + formatted_seq)

    @pyqtSlot(str)
    def _show_error(self, message: str):
        QMessageBox.critical(self, "Assembly Error", message)

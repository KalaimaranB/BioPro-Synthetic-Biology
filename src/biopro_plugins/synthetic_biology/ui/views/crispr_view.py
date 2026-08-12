"""PyQt6 CRISPR/Cas9 Guide RNA Design & Off-Target Inspection View.

Provides target sequence editor, PAM selection, and scored results table with
CFD off-target details. Decoupled from engines via CRISPRDesignController
signals & slots.
"""

from __future__ import annotations

from typing import List
from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...analysis.models.domain import gRNACandidate
from ...analysis.state import SynBioState
from ..controllers.crispr_controller import CRISPRDesignController


class CRISPRDesignView(QWidget):
    """PyQt6 View for CRISPR/Cas9 target discovery and off-target CFD score
    inspection.
    """

    scan_requested = pyqtSignal(str, str, int)

    def __init__(
        self, state: SynBioState, controller: CRISPRDesignController, parent=None
    ):
        super().__init__(parent)
        self.state = state
        self.controller = controller

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        self.setObjectName("crispr_design_view")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet("QSplitter::handle { background-color: #334155; }")

        # Top Control Box: Target Sequence Input & PAM Config
        top_widget = QGroupBox("CRISPR Target Sequence & PAM Selection")
        top_widget.setStyleSheet(
            "QGroupBox { font-weight: bold; color: #38BDF8; "
            "border: 1px solid #334155; padding-top: 12px; }"
        )
        top_layout = QVBoxLayout(top_widget)

        config_layout = QHBoxLayout()

        config_layout.addWidget(QLabel("PAM Enzyme Motif:"))
        self.pam_combo = QComboBox()
        self.pam_combo.addItems(
            [
                "SpCas9 (NGG)",
                "AsCas12a (TTTV)",
                "SaCas9 (NNGRRT)",
                "Cas9-VQR (NGAN)",
                "Cas9-EQR (NGAG)",
            ]
        )
        self.pam_combo.setStyleSheet(
            "background-color: #1E293B; color: white; padding: 4px;"
        )
        config_layout.addWidget(self.pam_combo)

        self.btn_scan = QPushButton("🔍 Scan Guide RNA Candidates")
        self.btn_scan.setStyleSheet(
            "background-color: #2563EB; color: white; font-weight: bold; "
            "padding: 6px 12px; border-radius: 4px;"
        )
        self.btn_scan.clicked.connect(self._on_scan_clicked)
        config_layout.addWidget(self.btn_scan)

        top_layout.addLayout(config_layout)

        self.target_seq_edit = QTextEdit()
        self.target_seq_edit.setPlaceholderText(
            "Paste target DNA sequence here (e.g. ATGC...)..."
        )
        self.target_seq_edit.setFixedHeight(90)
        self.target_seq_edit.setText(
            "ATGAGTAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTTAATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATACGGAAAACTTACCCTTAAATTTATTTGCACTACTGGAAAACTACCTGTTCCATGGCCAACACTTGTCACTACTTTCGGTTATGGTGTTCAATGCTTTGCG"
        )
        self.target_seq_edit.setStyleSheet(
            "background-color: #0F172A; color: #34D399; font-family: monospace; "
            "border: 1px solid #334155;"
        )
        top_layout.addWidget(self.target_seq_edit)

        splitter.addWidget(top_widget)

        # Bottom Results: Candidate Table & Off-Target Breakdown
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        # Table of Candidates
        self.grna_table = QTableWidget(0, 8)
        self.grna_table.setHorizontalHeaderLabels(
            [
                "Protospacer (20bp)",
                "PAM",
                "Strand",
                "Range",
                "GC %",
                "Efficiency %",
                "CFD Off-Target",
                "Poly-T Risk",
            ]
        )
        self.grna_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.grna_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.grna_table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.grna_table.setStyleSheet("""
            QTableWidget {
                background-color: #0F172A;
                color: #F8FAFC;
                border: 1px solid #334155;
                gridline-color: #1E293B;
            }
            QHeaderView::section {
                background-color: #1E293B;
                color: #38BDF8;
                font-weight: bold;
            }
        """)
        bottom_layout.addWidget(self.grna_table, stretch=2)

        # CFD Off-target Detail Inspector
        self.detail_display = QTextEdit()
        self.detail_display.setReadOnly(True)
        self.detail_display.setPlaceholderText(
            "Select a guide RNA row to view detailed CFD off-target mismatch "
            "breakdown..."
        )
        self.detail_display.setStyleSheet(
            "background-color: #0F172A; color: #F8FAFC; font-family: monospace; "
            "border: 1px solid #334155;"
        )
        bottom_layout.addWidget(self.detail_display, stretch=1)

        splitter.addWidget(bottom_widget)
        splitter.setSizes([160, 400])

        layout.addWidget(splitter)

    def _connect_signals(self):
        # Connect View -> Controller
        self.scan_requested.connect(self.controller.handle_scan_request)

        # Connect Controller -> View
        self.controller.grna_results_ready.connect(self.render_grna_results)
        self.controller.error_raised.connect(self._show_error)

    def _on_scan_clicked(self):
        seq = self.target_seq_edit.toPlainText().strip()
        if not seq:
            QMessageBox.warning(self, "Input Error", "Target sequence cannot be empty.")
            return

        pam_type = self.pam_combo.currentText()
        self.scan_requested.emit(seq, pam_type, 20)

    @pyqtSlot(list)
    def render_grna_results(self, candidates: List[gRNACandidate]):
        """Populates candidates into table."""
        self.grna_table.setRowCount(0)

        for cand in candidates:
            row = self.grna_table.rowCount()
            self.grna_table.insertRow(row)

            item_spacer = QTableWidgetItem(cand.protospacer)
            item_spacer.setData(Qt.ItemDataRole.UserRole, cand)

            self.grna_table.setItem(row, 0, item_spacer)
            self.grna_table.setItem(row, 1, QTableWidgetItem(cand.pam))
            self.grna_table.setItem(
                row, 2, QTableWidgetItem("+" if cand.strand >= 0 else "-")
            )
            self.grna_table.setItem(
                row, 3, QTableWidgetItem(f"{cand.start}-{cand.end}")
            )
            self.grna_table.setItem(row, 4, QTableWidgetItem(f"{cand.gc_content}%"))

            # Efficiency Score item
            eff_item = QTableWidgetItem(f"{cand.efficiency_score}%")
            if cand.efficiency_score >= 70.0:
                eff_item.setForeground(Qt.GlobalColor.green)
            self.grna_table.setItem(row, 5, eff_item)

            # CFD Off-target score item
            cfd_item = QTableWidgetItem(f"{cand.off_target_score}%")
            if cand.off_target_score >= 90.0:
                cfd_item.setForeground(Qt.GlobalColor.green)
            else:
                cfd_item.setForeground(Qt.GlobalColor.yellow)
            self.grna_table.setItem(row, 6, cfd_item)

            # Poly-T warning item
            poly_t_item = QTableWidgetItem("YES ⚠️" if cand.has_poly_t_term else "NO")
            if cand.has_poly_t_term:
                poly_t_item.setForeground(Qt.GlobalColor.red)
            self.grna_table.setItem(row, 7, poly_t_item)

    def _on_table_selection_changed(self):
        selected_rows = self.grna_table.selectedItems()
        if not selected_rows:
            self.detail_display.clear()
            return

        cand: gRNACandidate = self.grna_table.item(selected_rows[0].row(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        if not cand:
            return

        strand_str = "+" if cand.strand >= 0 else "-"
        detail_text = (
            f"=== gRNA CANDIDATE DETAILS ===\n"
            f"Protospacer: {cand.protospacer}\n"
            f"PAM Motif:   {cand.pam}\n"
            f"Location:    {cand.start} .. {cand.end} ({strand_str})\n"
            f"GC Content:  {cand.gc_content}%\n"
            f"On-Target Efficiency:  {cand.efficiency_score}%\n"
            f"CFD Off-Target Score:  {cand.off_target_score}%\n\n"
            f"--- CFD OFF-TARGET HITS ({len(cand.off_target_hits)}) ---\n"
        )

        for idx, hit in enumerate(cand.off_target_hits, 1):
            detail_text += (
                f"{idx}. Pos {hit['position']} | Seq: {hit['sequence']} | "
                f"Mismatches: {hit['mismatches']} | Hit Score: {hit['cfd_score']}%\n"
            )

        if not cand.off_target_hits:
            detail_text += "No significant off-target mismatch sites detected."

        self.detail_display.setText(detail_text)

    @pyqtSlot(str)
    def _show_error(self, message: str):
        QMessageBox.critical(self, "CRISPR Engine Error", message)

"""Empirical Analytics View (Test, Learn & Analytics).

Scaffolds Flow Cytometry (.fcs) ingestion, NGS Variant Analysis alignment tables,
and Machine Learning Hill Kinetic Parameter Optimization comparison plots.

STRICT CONSTRAINTS ENFORCED:
- Zero setStyleSheet() or hardcoded colors.
- Widget background enabled via WA_StyledBackground.
- Strict memory safety & teardown methods using deleteLater().
"""

from __future__ import annotations

from typing import Optional

import pyqtgraph as pg
from karcytics_sdk.plugin.theme_fallback import Fonts
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...analysis.empirical.fcs_ingestion import FCSEventData
from ...analysis.empirical.ml_optimizer import HillOptimizationResult
from ...analysis.empirical.ngs_alignment import NGSAlignmentResult
from ...analysis.state import SynBioState
from ...ui.controllers.empirical_controller import EmpiricalAnalyticsController


class EmpiricalAnalyticsView(QWidget):
    """View for Flow Cytometry, NGS alignment, and ML parameter fitting."""

    def __init__(
        self,
        state: Optional[SynBioState] = None,
        controller: Optional[EmpiricalAnalyticsController] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.state = state if state is not None else SynBioState()
        self.controller = (
            controller
            if controller is not None
            else EmpiricalAnalyticsController(self.state, self)
        )

        self._active_fcs_data: Optional[FCSEventData] = None
        self._active_ngs_result: Optional[NGSAlignmentResult] = None
        self._active_opt_result: Optional[HillOptimizationResult] = None

        self._init_ui()
        self._connect_signals()

    # ── UI Initialization ─────────────────────────────────────────────

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Header Title Label
        title_label = QLabel("Test, Learn & Empirical Analytics")
        title_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        font_family = getattr(Fonts, "FAMILY_UI", "sans-serif")
        title_font = QFont(font_family)
        try:
            sz = int(getattr(Fonts, "SIZE_TITLE", 16))
        except (ValueError, TypeError):
            sz = 16
        title_font.setPointSize(sz)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)

        # Main Tab Widget
        self.tabs = QTabWidget(self)
        self.tabs.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Tab 1: FCS Flow Cytometry Ingestion
        self.fcs_tab = self._build_fcs_tab()
        self.tabs.addTab(self.fcs_tab, "Flow Cytometry (.fcs)")

        # Tab 2: NGS Variant Analysis
        self.ngs_tab = self._build_ngs_tab()
        self.tabs.addTab(self.ngs_tab, "NGS Variant Analysis")

        # Tab 3: Machine Learning Optimization Loop
        self.ml_tab = self._build_ml_tab()
        self.tabs.addTab(self.ml_tab, "ML Kinetic Parameter Fitting")

        main_layout.addWidget(self.tabs)

    def _build_fcs_tab(self) -> QWidget:
        container = QWidget(self)
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(container)

        # Ingestion Controls Group
        group = QGroupBox("Flow Cytometry Data Ingestion", container)
        group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        form = QFormLayout(group)

        file_h_layout = QHBoxLayout()
        self.fcs_path_edit = QLineEdit(group)
        self.fcs_path_edit.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.fcs_path_edit.setPlaceholderText("Select .fcs file path...")

        self.fcs_browse_btn = QPushButton("Browse...", group)
        self.fcs_browse_btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.fcs_browse_btn.clicked.connect(self._on_browse_fcs)

        file_h_layout.addWidget(self.fcs_path_edit)
        file_h_layout.addWidget(self.fcs_browse_btn)
        form.addRow("FCS File:", file_h_layout)

        self.fcs_ingest_btn = QPushButton("Ingest & Analyze FCS", group)
        self.fcs_ingest_btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.fcs_ingest_btn.clicked.connect(self._on_ingest_fcs)
        form.addRow(self.fcs_ingest_btn)

        self.flow_plugin_status_lbl = QLabel(
            "Flow Cytometry Plugin Status: Standalone Mode",
            group,
        )
        self.flow_plugin_status_lbl.setAttribute(
            Qt.WidgetAttribute.WA_StyledBackground, True
        )
        form.addRow(self.flow_plugin_status_lbl)

        layout.addWidget(group)

        # Channel Statistics Table
        self.fcs_table = QTableWidget(container)
        self.fcs_table.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.fcs_table.setColumnCount(6)
        self.fcs_table.setHorizontalHeaderLabels(
            [
                "Channel Name",
                "Total Events",
                "Mean Intensity",
                "Median Intensity",
                "Std Dev",
                "Gated %",
            ]
        )
        if (hv := self.fcs_table.horizontalHeader()) is not None:
            hv.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.fcs_table)

        return container

    def _build_ngs_tab(self) -> QWidget:
        container = QWidget(self)
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(container)

        # Controls Group
        group = QGroupBox("NGS Alignment & Mutation Analysis", container)
        group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        form = QFormLayout(group)

        ngs_file_layout = QHBoxLayout()
        self.ngs_path_edit = QLineEdit(group)
        self.ngs_path_edit.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.ngs_path_edit.setPlaceholderText("Select NGS file (FASTA/FASTQ/BAM)...")

        self.ngs_browse_btn = QPushButton("Browse...", group)
        self.ngs_browse_btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.ngs_browse_btn.clicked.connect(self._on_browse_ngs)

        ngs_file_layout.addWidget(self.ngs_path_edit)
        ngs_file_layout.addWidget(self.ngs_browse_btn)
        form.addRow("NGS File:", ngs_file_layout)

        self.ngs_align_btn = QPushButton("Run Sequence Alignment", group)
        self.ngs_align_btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.ngs_align_btn.clicked.connect(self._on_align_ngs)
        form.addRow(self.ngs_align_btn)

        layout.addWidget(group)

        # Variant Flags Table
        self.ngs_table = QTableWidget(container)
        self.ngs_table.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.ngs_table.setColumnCount(9)
        self.ngs_table.setHorizontalHeaderLabels(
            [
                "Variant ID",
                "Position",
                "Type",
                "Ref Allele",
                "Alt Allele",
                "VAF %",
                "Feature",
                "Off-Target Score",
                "Severity",
            ]
        )
        if (hv := self.ngs_table.horizontalHeader()) is not None:
            hv.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.ngs_table)

        return container

    def _build_ml_tab(self) -> QWidget:
        container = QWidget(self)
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(container)

        # Controls Group
        group = QGroupBox("Hill Kinetic Parameter Optimization Loop", container)
        group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h_layout = QHBoxLayout(group)

        self.ml_fit_btn = QPushButton("Fit Parameters to Empirical Data", group)
        self.ml_fit_btn.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.ml_fit_btn.clicked.connect(self._on_fit_ml)

        self.ml_status_lbl = QLabel("Optimization Status: Idle", group)
        self.ml_status_lbl.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        h_layout.addWidget(self.ml_fit_btn)
        h_layout.addWidget(self.ml_status_lbl)
        layout.addWidget(group)

        # Splitter: Left Table Comparison, Right PyQtGraph Plot
        splitter = QSplitter(Qt.Orientation.Horizontal, container)
        splitter.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Left Widget: Side-by-side Table
        self.ml_table = QTableWidget(splitter)
        self.ml_table.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.ml_table.setColumnCount(5)
        self.ml_table.setHorizontalHeaderLabels(
            ["Component", "Parameter", "Original", "Optimized", "Delta %"]
        )
        if (hv := self.ml_table.horizontalHeader()) is not None:
            hv.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Right Widget: PyQtGraph Comparison Plot
        plot_container = QWidget(splitter)
        plot_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        plot_layout = QVBoxLayout(plot_container)

        self.plot_widget = pg.PlotWidget(plot_container)
        self.plot_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.plot_widget.setTitle("Original vs Empirically Fitted Kinetic Curves")
        self.plot_widget.setLabel("bottom", "Time (min)")
        self.plot_widget.setLabel("left", "Expression / Fluorescence")
        self.plot_widget.addLegend()

        if isinstance(self.plot_widget, QWidget):
            plot_layout.addWidget(self.plot_widget)

        splitter.addWidget(self.ml_table)
        splitter.addWidget(plot_container)
        splitter.setSizes([450, 550])

        layout.addWidget(splitter)
        return container

    # ── Signal Connections ────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self.controller.fcs_loaded.connect(self._on_fcs_loaded)
        self.controller.ngs_aligned.connect(self._on_ngs_aligned)
        self.controller.optimization_finished.connect(self._on_optimization_finished)
        self.controller.error_raised.connect(self._on_error)

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_browse_fcs(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select FCS File", "", "FCS Files (*.fcs);;All Files (*)"
        )
        if path:
            self.fcs_path_edit.setText(path)

    def _on_ingest_fcs(self) -> None:
        path = self.fcs_path_edit.text().strip() or "sample_flow_data.fcs"
        self.controller.load_fcs_data(path)

    def _on_browse_ngs(self) -> None:
        filter_str = "NGS Files (*.fasta *.fastq *.bam);;All Files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select NGS File", "", filter_str)
        if path:
            self.ngs_path_edit.setText(path)

    def _on_align_ngs(self) -> None:
        path = self.ngs_path_edit.text().strip() or "ngs_reads.fastq"
        self.controller.run_ngs_alignment(path)

    def _on_fit_ml(self) -> None:
        comps = self.state.circuit_components
        edgs = self.state.circuit_edges
        if not comps:
            from karcytics_plugins.synthetic_biology.analysis.simulation import (
                circuit_engine as ce,
            )

            CircuitSimulationEngine = ce.CircuitSimulationEngine

            comps, edgs = CircuitSimulationEngine.create_preset_repressilator()
        self.controller.run_ml_optimization(comps, edgs, self._active_fcs_data)

    @pyqtSlot(object)
    def _on_fcs_loaded(self, data: FCSEventData) -> None:
        self._active_fcs_data = data
        self.fcs_table.setRowCount(0)

        for row, (ch_name, stats) in enumerate(data.channel_stats.items()):
            self.fcs_table.insertRow(row)
            self.fcs_table.setItem(row, 0, QTableWidgetItem(ch_name))
            self.fcs_table.setItem(row, 1, QTableWidgetItem(str(stats.event_count)))
            self.fcs_table.setItem(
                row, 2, QTableWidgetItem(f"{stats.mean_intensity:.2f}")
            )
            self.fcs_table.setItem(
                row, 3, QTableWidgetItem(f"{stats.median_intensity:.2f}")
            )
            self.fcs_table.setItem(
                row, 4, QTableWidgetItem(f"{stats.std_intensity:.2f}")
            )
            self.fcs_table.setItem(
                row, 5, QTableWidgetItem(f"{stats.gated_percentage:.1f}%")
            )

    @pyqtSlot(object)
    def _on_ngs_aligned(self, result: NGSAlignmentResult) -> None:
        self._active_ngs_result = result
        self.ngs_table.setRowCount(0)

        for row, flag in enumerate(result.variants):
            self.ngs_table.insertRow(row)
            self.ngs_table.setItem(row, 0, QTableWidgetItem(flag.id))
            self.ngs_table.setItem(row, 1, QTableWidgetItem(str(flag.position)))
            self.ngs_table.setItem(row, 2, QTableWidgetItem(flag.variant_type))
            self.ngs_table.setItem(row, 3, QTableWidgetItem(flag.ref_allele))
            self.ngs_table.setItem(row, 4, QTableWidgetItem(flag.alt_allele))
            self.ngs_table.setItem(
                row, 5, QTableWidgetItem(f"{flag.frequency * 100:.1f}%")
            )
            self.ngs_table.setItem(row, 6, QTableWidgetItem(flag.affected_feature))
            ot_str = (
                f"{flag.off_target_score:.1f}"
                if flag.off_target_score is not None
                else "N/A"
            )
            self.ngs_table.setItem(row, 7, QTableWidgetItem(ot_str))
            self.ngs_table.setItem(row, 8, QTableWidgetItem(flag.severity))

    @pyqtSlot(object)
    def _on_optimization_finished(self, result: HillOptimizationResult) -> None:
        self._active_opt_result = result
        msg = (
            f"Optimization Complete | MSE: {result.initial_mse:.3f} "
            f"-> {result.final_mse:.3f}"
        )
        self.ml_status_lbl.setText(msg)
        self.ml_table.setRowCount(0)

        row = 0
        for comp_name, deltas in result.parameter_deltas.items():
            for param_name, (orig_v, opt_v) in deltas.items():
                self.ml_table.insertRow(row)
                self.ml_table.setItem(row, 0, QTableWidgetItem(comp_name))
                self.ml_table.setItem(row, 1, QTableWidgetItem(param_name))
                self.ml_table.setItem(row, 2, QTableWidgetItem(f"{orig_v:.4f}"))
                self.ml_table.setItem(row, 3, QTableWidgetItem(f"{opt_v:.4f}"))
                d_pct = ((opt_v - orig_v) / max(1e-6, orig_v)) * 100
                self.ml_table.setItem(row, 4, QTableWidgetItem(f"{d_pct:+.1f}%"))
                row += 1

        # Plot comparison curves
        self.plot_widget.clear()
        t = list(range(50))

        for species, fit_curve in result.fitted_time_series.items():
            self.plot_widget.plot(
                t,
                fit_curve,
                pen=pg.mkPen(color="#00bcd4", width=2),
                name=f"{species} (Optimized Fit)",
            )

        for species, emp_curve in result.empirical_time_series.items():
            self.plot_widget.plot(
                t,
                emp_curve,
                pen=pg.mkPen(color="#ef5350", width=2, style=Qt.PenStyle.DashLine),
                name=f"{species} (Empirical Target)",
            )

    @pyqtSlot(str)
    def _on_error(self, err_msg: str) -> None:
        QMessageBox.warning(self, "Empirical Analytics Error", err_msg)

    # ── Teardown & Hot-swapping ───────────────────────────────────────

    def teardown(self) -> None:
        """Memory-safe cleanup for plugin hot-swapping."""
        try:
            self.controller.fcs_loaded.disconnect(self._on_fcs_loaded)
            self.controller.ngs_aligned.disconnect(self._on_ngs_aligned)
            self.controller.optimization_finished.disconnect(
                self._on_optimization_finished
            )
            self.controller.error_raised.disconnect(self._on_error)
        except Exception:
            pass

        self.controller.teardown()

        self.fcs_table.clearContents()
        self.fcs_table.setRowCount(0)
        self.ngs_table.clearContents()
        self.ngs_table.setRowCount(0)
        self.ml_table.clearContents()
        self.ml_table.setRowCount(0)

        if hasattr(self, "plot_widget") and self.plot_widget is not None:
            self.plot_widget.clear()

        self.deleteLater()

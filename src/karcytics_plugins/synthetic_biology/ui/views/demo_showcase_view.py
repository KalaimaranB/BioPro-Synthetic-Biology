"""Interactive Product Demo Showcase View for Synthetic Biology.

Integrated directly into the SynBio workspace under the 'Demo Showcase' tab.
Follows standard Karcytics SDK protocols, theme tokens, and reactive state management.
"""

from __future__ import annotations

import math
from typing import Any

from karcytics_sdk.plugin.theme_fallback import Colors, Fonts, theme_manager
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
    GeneticFeature,
    PlasmidVector,
    SimulationResult,
    gRNACandidate,
)
from ...analysis.parts.components import CDS, RBS, Promoter, Terminator
from ...analysis.state import SynBioState


class DemoShowcaseView(QWidget):
    """Product Showcase Tab View — presents a interactive demo overview of SynBio features."""

    demo_loaded = pyqtSignal()

    def __init__(
        self, state: SynBioState, main_panel: Any = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.main_panel = main_panel
        self._setup_ui()
        self._apply_theme_styles()
        theme_manager.theme_changed.connect(self._apply_theme_styles)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_card = self._build_header_card()
        layout.addWidget(header_card)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._build_left_column())
        splitter.addWidget(self._build_right_column())
        splitter.setSizes([750, 750])

        layout.addWidget(splitter, 1)

    def _build_header_card(self) -> QFrame:
        header_card = QFrame(self)
        header_card.setObjectName("HeaderCard")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 12, 16, 12)

        title_box = QVBoxLayout()
        title_lbl = QLabel("🚀 Synthetic Biology — Interactive Product Showcase")
        title_lbl.setObjectName("DemoTitle")
        subtitle_lbl = QLabel(
            "Explore pre-loaded genetic logic gates, Golden Gate plasmid maps, "
            "CRISPR gRNA target analysis, ODE kinetic oscillations, and automated Tecan liquid handler exports."
        )
        subtitle_lbl.setObjectName("DemoSubtitle")
        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.btn_load_demo = QPushButton("✨ Load Demo State into Workspace", self)
        self.btn_load_demo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_demo.clicked.connect(self._on_load_demo_clicked)
        header_layout.addWidget(self.btn_load_demo)

        return header_card

    def _build_left_column(self) -> QWidget:
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # 1. Circuit Topology Card
        topo_card = QFrame(self)
        topo_card.setObjectName("SectionCard")
        topo_layout = QVBoxLayout(topo_card)
        topo_layout.setContentsMargins(14, 12, 14, 12)

        topo_lbl = QLabel("🧬 Pre-loaded Circuit: Repressilator Oscillator")
        topo_lbl.setObjectName("SectionTitle")
        topo_layout.addWidget(topo_lbl)

        self.topo_table = QTableWidget(5, 4, self)
        self.topo_table.setHorizontalHeaderLabels(["ID", "Name", "Type", "Key Parameters"])
        topo_header = self.topo_table.horizontalHeader()
        if topo_header is not None:
            topo_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.topo_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        demo_parts = [
            ("comp_1", "pTac Promoter", "Promoter", "y_max=5.0 RPU, Kd=0.05"),
            ("comp_2", "LacI Repressor", "CDS", "Degradation=0.10, Translation=1.2"),
            ("comp_3", "pTet Promoter", "Promoter", "y_max=4.2 RPU, Kd=0.04"),
            ("comp_4", "TetR Repressor", "CDS", "Degradation=0.12, Translation=1.1"),
            ("comp_5", "b1006 Terminator", "Terminator", "Termination Efficiency=98%"),
        ]
        for row, (p_id, p_name, p_type, p_param) in enumerate(demo_parts):
            self.topo_table.setItem(row, 0, QTableWidgetItem(p_id))
            self.topo_table.setItem(row, 1, QTableWidgetItem(p_name))
            self.topo_table.setItem(row, 2, QTableWidgetItem(p_type))
            self.topo_table.setItem(row, 3, QTableWidgetItem(p_param))

        topo_layout.addWidget(self.topo_table)
        left_layout.addWidget(topo_card)

        # 2. Plasmid Construct Card
        plasmid_card = QFrame(self)
        plasmid_card.setObjectName("SectionCard")
        plasmid_layout = QVBoxLayout(plasmid_card)
        plasmid_layout.setContentsMargins(14, 12, 14, 12)

        plasmid_lbl = QLabel("🧪 Vector Assembly: pUC19-Repressilator-Gate (4,382 bp)")
        plasmid_lbl.setObjectName("SectionTitle")
        plasmid_layout.addWidget(plasmid_lbl)

        self.plasmid_table = QTableWidget(6, 4, self)
        self.plasmid_table.setHorizontalHeaderLabels(["Feature", "Type", "Coordinates", "Strand"])
        plasmid_header = self.plasmid_table.horizontalHeader()
        if plasmid_header is not None:
            plasmid_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.plasmid_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        demo_feats = [
            ("AmpR", "CDS", "120 - 980 bp", "+1 (Forward)"),
            ("pUC ori", "Origin", "1100 - 1780 bp", "+1 (Forward)"),
            ("pTac", "Promoter", "1850 - 1950 bp", "+1 (Forward)"),
            ("LacI", "CDS", "1960 - 3040 bp", "+1 (Forward)"),
            ("pTet", "Promoter", "3080 - 3180 bp", "+1 (Forward)"),
            ("TetR", "CDS", "3190 - 3820 bp", "+1 (Forward)"),
        ]
        for row, (f_name, f_type, f_coords, f_strand) in enumerate(demo_feats):
            self.plasmid_table.setItem(row, 0, QTableWidgetItem(f_name))
            self.plasmid_table.setItem(row, 1, QTableWidgetItem(f_type))
            self.plasmid_table.setItem(row, 2, QTableWidgetItem(f_coords))
            self.plasmid_table.setItem(row, 3, QTableWidgetItem(f_strand))

        plasmid_layout.addWidget(self.plasmid_table)
        left_layout.addWidget(plasmid_card)

        return left_widget

    def _build_right_column(self) -> QWidget:
        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # 3. CRISPR & Kinetic Simulation Summary Card
        crispr_card = QFrame(self)
        crispr_card.setObjectName("SectionCard")
        crispr_layout = QVBoxLayout(crispr_card)
        crispr_layout.setContentsMargins(14, 12, 14, 12)

        crispr_lbl = QLabel("✂️ CRISPR gRNA Design & Kinetic ODE Simulation")
        crispr_lbl.setObjectName("SectionTitle")
        crispr_layout.addWidget(crispr_lbl)

        self.crispr_table = QTableWidget(2, 5, self)
        self.crispr_table.setHorizontalHeaderLabels(
            ["Target Gene", "Protospacer (20bp)", "PAM", "Efficiency", "Off-Target Risk"]
        )
        crispr_header = self.crispr_table.horizontalHeader()
        if crispr_header is not None:
            crispr_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.crispr_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        demo_grna = [
            ("LacI_Repressor", "GCTAGCTAGCTAGCTAGC", "NGG", "94.0%", "Low Risk (97.0)"),
            ("TetR_Repressor", "TGACTGACTGACTGACTG", "NGG", "88.0%", "Low Risk (94.0)"),
        ]
        for row, (g_gene, g_proto, g_pam, g_eff, g_off) in enumerate(demo_grna):
            self.crispr_table.setItem(row, 0, QTableWidgetItem(g_gene))
            self.crispr_table.setItem(row, 1, QTableWidgetItem(g_proto))
            self.crispr_table.setItem(row, 2, QTableWidgetItem(g_pam))
            self.crispr_table.setItem(row, 3, QTableWidgetItem(g_eff))
            self.crispr_table.setItem(row, 4, QTableWidgetItem(g_off))

        crispr_layout.addWidget(self.crispr_table)
        right_layout.addWidget(crispr_card)

        # 4. Robot Export Preview Card
        robot_card = QFrame(self)
        robot_card.setObjectName("SectionCard")
        robot_layout = QVBoxLayout(robot_card)
        robot_layout.setContentsMargins(14, 12, 14, 12)

        robot_lbl = QLabel("🤖 Automated Tecan / Opentrons Protocol Export Preview")
        robot_lbl.setObjectName("SectionTitle")
        robot_layout.addWidget(robot_lbl)

        preview_lbl = QLabel(
            "Source,SourceWell,Destination,DestWell,Volume_uL,Reagent\n"
            "SourceRack,A01,DestRack,A01,15.0,2X Golden Gate Master Mix (BsaI + T4 Ligase)\n"
            "SourceRack,A02,DestRack,A01,2.5,pUC19 Backbone (50 ng/uL)\n"
            "SourceRack,A03,DestRack,A01,2.5,LacI Repressor Insert (20 ng/uL)\n"
            "SourceRack,A04,DestRack,A01,2.5,TetR Repressor Insert (20 ng/uL)\n"
            "SourceRack,A05,DestRack,A01,7.5,Nuclease-Free Water"
        )
        preview_lbl.setObjectName("CodePreview")
        preview_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        robot_layout.addWidget(preview_lbl)

        right_layout.addWidget(robot_card)

        return right_widget

    def _on_load_demo_clicked(self) -> None:
        """Populate the SynBioState with the Repressilator showcase dataset."""
        # 1. Biological Parts
        p_tac = Promoter(
            id="P_tac",
            name="pTac Promoter",
            sequence="TTGACAATTAATCATCGGCTCGTATAATGTGTGG",
            y_max=5.0,
        )
        rbs_strong = RBS(
            id="RBS_001",
            name="Strong Synthetic RBS",
            sequence="AAAGAGGAGAA",
            translation_initiation_rate=0.92,
        )
        cds_laci = CDS(
            id="CDS_lacI",
            name="LacI Repressor",
            sequence="ATGAAACCAGTAACGTTATACGATGTCGCAGAGTATGCCGGTGTCTCTTATCAGACCGTTTCCCGCGTGGTGAACCAGGCCAGCCACGTTTCTGCGAAAACGCGGGAAAAAGTGGAAGCGGCGATGGCGGAGCTGAATTACATTCCCAACCGCGTGGCACAACAACTGGCGGGCAAACAGTCGTTGCTGATTGGCGTTGCCACCTCCAGTCTGGCCCTGCACGCGCCGTCGCAAATTGTCGCGGCGATTAAATCTCGCGCCGATCAACTGGGTGCCAGCGTGGTGGTGTCGATGGTAGAACGAAGCGGCGTCGAAGCCTGTAAAGCGGCGGTGCACAATCTTCTCGCGCAACGCGTCAGTGGGCTGATCATTAACTATCCGCTGGATGACCAGGATGCCATTGCTGTGGAAGCTGCCTGCACTAATGTTCCGGCGTTATTTCTTGATGTCTCTGACCAGACACCCATCAACAGTATTATTTTCTCCCATGAAGACGGTACGCGACTGGGCGTGGAGCATCTGGTCGCATTGGGTCACCAGCAAATCGCGCTGTTAGCGGGCCCATTAAGTTCTGTCTCGGCGCGTCTGCGTCTGGCTGGCTGGCATAAATATCTCACTCGCAATCAAATTCAGCCGATAGCGGAACGGGAAGGCGACTGGAGTGCCATGTCCGGTTTTCAACAAACCATGCAAATGCTGAATGAGGGCATCGTTCCCACTGCGATGCTGGTTGCCAACGATCAGATGGCGCTGGGCGCAATGCGCGCCATTACCGAGTCCGGGCTGCGCGTTGGTGCGGATATCTCGGTAGTGGGATACGACGATACCGAAGACAGCTCATGTTATATCCCGCCGTTAACCACCATCAAACAGGATTTTCGCCTGCTGGGGCAAACCAGCGTGGACCGCTTGCTGCAACTCTCTCAGGGCCAGGCGGTGAAGGGCAATCAGCTGTTGCCCGTCTCACTGGTGAAAAGAAAAACCACCCTGGCGCCCAATACGCAAACCGCCTCTCCCCGCGCGTTGGCCGATTCAAAAATGAAGCTGGCATCCTTCGTTGAAGTGCCCGAGAACGAGTCATGA",
            product="LacI",
        )
        term_b1006 = Terminator(
            id="T_b1006",
            name="b1006 Terminator",
            sequence="AAAAAAACCCCGCCGAAGCGGGGGTTTTTTT",
            termination_efficiency=0.98,
        )
        p_tet = Promoter(
            id="P_tet",
            name="pTet Promoter",
            sequence="TCCCTATCAGTGATAGAGATTGACATCCCTATCAGTGATAGAGATACTGAGCAC",
            y_max=4.2,
        )
        cds_tetr = CDS(
            id="CDS_tetR",
            name="TetR Repressor",
            sequence="ATGTCCAGATTAGATAAAAGTAAAGTGATTAACAGCGCATTAGAGCTGCTTAATGAGGTCGGAATCGAAGGTTTAACAACCCGTAAACTCGCCCAGAAGCTAGGTGTAGAGCAGCCTACACTGTATTGGCACGTGAAGAACAAGCGGGCCCTGCTCGACGCCCTGGCCATCGAGATGCTGGACAGGCATCATACCCACTTCTGCCCCCTGGAAGGCGAGTCATGGCAAGACTTTCTGCGGAACAACGCCAAGAGTTTCCGCTGTGCCCTCCTCTCACACCGCGACGGGGCCAAAGTGCATCTCGGCACCCGCCCAACAGAGAAACAGTACGAAACCCTGGAAAATCAGCTCGCGTTCCTGTGTCAGCAAGGCTTCTCCCTGGAGAACGCACTGTACGCTCTGTCCGCCGTGGGCCACTTCACACTGGGCTGCGTATTGGAGGAACAGGAGCATCAAGTAGCAAAAGAGGAAAGAGACACACCTACCACCGATTCTATGCCCCCACTTCTGAGACAAGCAATTGAGCTGTTCGACCATCAGGGAGCCGAACCTGCCTTCCTTTTCGGCCTGGAACTAATCATATGTGGCCTGGAGAAACAGCTAAAGTGCGAAAGCGGCTCCGCCGACGCACTGGACGATTTCGATCTGGACATGCTCCACGCCGACGCGCTCGACTAA",
            product="TetR",
        )

        nodes = [
            CircuitComponent(
                id="comp_1",
                name="pTac Promoter",
                component_type="promoter",
                y_max=5.0,
                K_d=0.05,
                n=2.0,
            ),
            CircuitComponent(
                id="comp_2",
                name="LacI Repressor",
                component_type="cds",
                degradation_rate=0.1,
                translation_rate=1.2,
            ),
            CircuitComponent(
                id="comp_3",
                name="pTet Promoter",
                component_type="promoter",
                y_max=4.2,
                K_d=0.04,
                n=2.0,
            ),
            CircuitComponent(
                id="comp_4",
                name="TetR Repressor",
                component_type="cds",
                degradation_rate=0.12,
                translation_rate=1.1,
            ),
            CircuitComponent(id="comp_5", name="b1006 Terminator", component_type="terminator"),
        ]
        edges = [
            CircuitEdge(
                source_id="comp_1",
                target_id="comp_2",
                interaction_type="transcription",
                strength=2.5,
            ),
            CircuitEdge(
                source_id="comp_2", target_id="comp_3", interaction_type="repression", strength=1.0
            ),
            CircuitEdge(
                source_id="comp_3",
                target_id="comp_4",
                interaction_type="transcription",
                strength=2.1,
            ),
            CircuitEdge(
                source_id="comp_4", target_id="comp_1", interaction_type="repression", strength=1.0
            ),
        ]
        self.state.set_circuit_components(nodes)
        self.state.set_circuit_edges(edges)

        # 2. Plasmid
        features = [
            GeneticFeature(
                id="feat_1",
                name="AmpR",
                feature_type="cds",
                start=120,
                end=980,
                strand=1,
                color="#3B82F6",
            ),
            GeneticFeature(
                id="feat_2",
                name="ori",
                feature_type="origin",
                start=1100,
                end=1780,
                strand=1,
                color="#10B981",
            ),
            GeneticFeature(
                id="feat_3",
                name="pTac",
                feature_type="promoter",
                start=1850,
                end=1950,
                strand=1,
                color="#F59E0B",
            ),
            GeneticFeature(
                id="feat_4",
                name="LacI",
                feature_type="cds",
                start=1960,
                end=3040,
                strand=1,
                color="#EC4899",
            ),
            GeneticFeature(
                id="feat_5",
                name="pTet",
                feature_type="promoter",
                start=3080,
                end=3180,
                strand=1,
                color="#8B5CF6",
            ),
            GeneticFeature(
                id="feat_6",
                name="TetR",
                feature_type="cds",
                start=3190,
                end=3820,
                strand=1,
                color="#EF4444",
            ),
        ]
        plasmid = PlasmidVector(
            id="plasmid_001",
            name="pUC19-Repressilator-Gate",
            description="Golden Gate synthetic genetic oscillator construct",
            sequence="ATGC" * 10955,
            is_circular=True,
            features=features,
        )
        self.state.set_active_plasmid(plasmid)

        # 3. CRISPR
        grna_1 = gRNACandidate(
            id="grna_1",
            target_id="target_lacI",
            protospacer="GCTAGCTAGCTAGCTAGC",
            pam="NGG",
            strand=1,
            start=45,
            end=65,
            gc_content=55.0,
            efficiency_score=94.0,
            off_target_score=97.0,
        )
        grna_2 = gRNACandidate(
            id="grna_2",
            target_id="target_tetR",
            protospacer="TGACTGACTGACTGACTG",
            pam="NGG",
            strand=-1,
            start=112,
            end=132,
            gc_content=50.0,
            efficiency_score=88.0,
            off_target_score=94.0,
        )
        self.state.set_grna_candidates([grna_1, grna_2])

        # 4. ODE Simulation Results
        time_pts = [float(t) for t in range(0, 101, 2)]
        lacI_series = [10.0 + 8.0 * math.sin(0.15 * t) * math.exp(-0.005 * t) for t in time_pts]
        tetR_series = [
            10.0 + 8.0 * math.sin(0.15 * t + 2.09) * math.exp(-0.005 * t) for t in time_pts
        ]
        cI_series = [
            10.0 + 8.0 * math.sin(0.15 * t + 4.18) * math.exp(-0.005 * t) for t in time_pts
        ]

        sim_res = SimulationResult(
            time_points=time_pts,
            species_concentrations={"LacI": lacI_series, "TetR": tetR_series, "cI": cI_series},
            status_message="Success: Sustained Repressilator Limit Cycle (ODE LSODA)",
            success=True,
        )
        self.state.set_simulation_result(sim_res)

        # 5. Populate Main Panel Parts Cache & Canvas Render
        if self.main_panel:
            demo_parts_list = [p_tac, rbs_strong, cds_laci, term_b1006, p_tet, cds_tetr]
            self.main_panel._parts_cache = demo_parts_list

            if hasattr(self.main_panel, "_circuit_canvas"):
                self.main_panel._circuit_canvas._parts = list(demo_parts_list)
                self.main_panel._circuit_canvas.render_circuit()

            if hasattr(self.main_panel, "_properties_view"):
                self.main_panel._properties_view.set_parts(demo_parts_list)

            if hasattr(self.main_panel, "_simulate_view"):
                self.main_panel._simulate_view.set_parts(demo_parts_list)
                self.main_panel._simulate_view.plot_time_series(max_time=100, method="ode")

            if hasattr(self.main_panel, "_status_label"):
                self.main_panel._status_label.setText(
                    "✨ Demo Showcase Loaded: Repressilator Oscillator Circuit active."
                )

            # Switch main panel to Circuit Canvas (Tab 0) so the user can interact
            if hasattr(self.main_panel, "_tab_bar"):
                self.main_panel._tab_bar.setCurrentIndex(0)

        self.demo_loaded.emit()

    def _apply_theme_styles(self) -> None:
        qss = f"""
            DemoShowcaseView {{
                background: {Colors.BG_DARKEST};
                color: {Colors.FG_PRIMARY};
            }}
            QFrame#HeaderCard {{
                background: {Colors.BG_DARK};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 8px;
            }}
            QLabel#DemoTitle {{
                font-size: {Fonts.SIZE_LARGE}px;
                font-weight: bold;
                color: {Colors.FG_PRIMARY};
            }}
            QLabel#DemoSubtitle {{
                font-size: {Fonts.SIZE_SMALL}px;
                color: {Colors.FG_SECONDARY};
            }}
            QPushButton {{
                background: {Colors.ACCENT_PRIMARY};
                color: #FFFFFF;
                font-weight: bold;
                font-size: {Fonts.SIZE_NORMAL}px;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background: {Colors.ACCENT_HOVER};
            }}
            QFrame#SectionCard {{
                background: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
            }}
            QLabel#SectionTitle {{
                font-size: {Fonts.SIZE_NORMAL}px;
                font-weight: bold;
                color: {Colors.ACCENT_PRIMARY};
            }}
            QTableWidget {{
                background: {Colors.BG_DARKEST};
                color: {Colors.FG_PRIMARY};
                gridline-color: {Colors.BORDER};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
            }}
            QHeaderView::section {{
                background: {Colors.BG_MEDIUM};
                color: {Colors.FG_PRIMARY};
                font-weight: bold;
                padding: 4px;
                border: 1px solid {Colors.BORDER};
            }}
            QLabel#CodePreview {{
                font-family: monospace;
                font-size: 11px;
                background: {Colors.BG_DARKEST};
                color: {Colors.FG_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 8px;
            }}
        """
        self.setStyleSheet(qss)

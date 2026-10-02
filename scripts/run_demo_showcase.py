#!/usr/bin/env python3
"""Karcytics Synthetic Biology — Interactive Product Demo Showcase.

Designed for Product Marketing Managers, Sales Engineers, and Technical Demonstrators
to present the full end-to-end capabilities of Karcytics Synthetic Biology to potential
customers (academic labs, bio-foundries, synbio startups, and pharma R&D).

Zero Side-Effects Guarantee: Runs on isolated transient state without modifying
production configuration or local storage files.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Ensure plugin src is on sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from PyQt6.QtWidgets import (  # noqa: E402, TID251
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from karcytics_plugins.synthetic_biology import initialize  # noqa: E402
from karcytics_plugins.synthetic_biology.analysis.models.domain import (  # noqa: E402
    CircuitComponent,
    CircuitEdge,
    GeneticFeature,
    PlasmidVector,
    SimulationResult,
    gRNACandidate,
)
from karcytics_plugins.synthetic_biology.analysis.parts.components import (  # noqa: E402
    CDS,
    RBS,
    Promoter,
    Terminator,
)
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState  # noqa: E402


def create_demo_state() -> SynBioState:
    """Build a rich, realistic demonstration state featuring a Repressilator circuit."""
    state = SynBioState()

    # 1. Biological Parts & Circuit Topology (Repressilator: LacI, TetR, cI loop)
    _p_tac = Promoter(
        id="P_tac", name="pTac Promoter", sequence="TTGACAATTAATCATCGGCTCGTATAATGTGTGG", y_max=1.0
    )
    _rbs_strong = RBS(
        id="RBS_001",
        name="Strong Synthetic RBS",
        sequence="AAAGAGGAGAA",
        translation_initiation_rate=0.92,
    )
    _cds_laci = CDS(
        id="CDS_lacI",
        name="LacI Repressor",
        sequence="ATGAAACCAGTAACGTTATACGATGTCGCAGAGTATGCCGGTGTCTCTTATCAGACCGTTTCCCGCGTGGTGAACCAGGCCAGCCACGTTTCTGCGAAAACGCGGGAAAAAGTGGAAGCGGCGATGGCGGAGCTGAATTACATTCCCAACCGCGTGGCACAACAACTGGCGGGCAAACAGTCGTTGCTGATTGGCGTTGCCACCTCCAGTCTGGCCCTGCACGCGCCGTCGCAAATTGTCGCGGCGATTAAATCTCGCGCCGATCAACTGGGTGCCAGCGTGGTGGTGTCGATGGTAGAACGAAGCGGCGTCGAAGCCTGTAAAGCGGCGGTGCACAATCTTCTCGCGCAACGCGTCAGTGGGCTGATCATTAACTATCCGCTGGATGACCAGGATGCCATTGCTGTGGAAGCTGCCTGCACTAATGTTCCGGCGTTATTTCTTGATGTCTCTGACCAGACACCCATCAACAGTATTATTTTCTCCCATGAAGACGGTACGCGACTGGGCGTGGAGCATCTGGTCGCATTGGGTCACCAGCAAATCGCGCTGTTAGCGGGCCCATTAAGTTCTGTCTCGGCGCGTCTGCGTCTGGCTGGCTGGCATAAATATCTCACTCGCAATCAAATTCAGCCGATAGCGGAACGGGAAGGCGACTGGAGTGCCATGTCCGGTTTTCAACAAACCATGCAAATGCTGAATGAGGGCATCGTTCCCACTGCGATGCTGGTTGCCAACGATCAGATGGCGCTGGGCGCAATGCGCGCCATTACCGAGTCCGGGCTGCGCGTTGGTGCGGATATCTCGGTAGTGGGATACGACGATACCGAAGACAGCTCATGTTATATCCCGCCGTTAACCACCATCAAACAGGATTTTCGCCTGCTGGGGCAAACCAGCGTGGACCGCTTGCTGCAACTCTCTCAGGGCCAGGCGGTGAAGGGCAATCAGCTGTTGCCCGTCTCACTGGTGAAAAGAAAAACCACCCTGGCGCCCAATACGCAAACCGCCTCTCCCCGCGCGTTGGCCGATTCAAAAATGAAGCTGGCATCCTTCGTTGAAGTGCCCGAGAACGAGTCATGA",
        product="LacI",
    )
    _term_b1006 = Terminator(
        id="T_b1006",
        name="b1006 Terminator",
        sequence="AAAAAAACCCCGCCGAAGCGGGGGTTTTTTT",
        termination_efficiency=0.98,
    )

    _p_tet = Promoter(
        id="P_tet",
        name="pTet Promoter",
        sequence="TCCCTATCAGTGATAGAGATTGACATCCCTATCAGTGATAGAGATACTGAGCAC",
        y_max=0.85,
    )
    _cds_tetr = CDS(
        id="CDS_tetR",
        name="TetR Repressor",
        sequence="ATGTCCAGATTAGATAAAAGTAAAGTGATTAACAGCGCATTAGAGCTGCTTAATGAGGTCGGAATCGAAGGTTTAACAACCCGTAAACTCGCCCAGAAGCTAGGTGTAGAGCAGCCTACACTGTATTGGCACGTGAAGAACAAGCGGGCCCTGCTCGACGCCCTGGCCATCGAGATGCTGGACAGGCATCATACCCACTTCTGCCCCCTGGAAGGCGAGTCATGGCAAGACTTTCTGCGGAACAACGCCAAGAGTTTCCGCTGTGCCCTCCTCTCACACCGCGACGGGGCCAAAGTGCATCTCGGCACCCGCCCAACAGAGAAACAGTACGAAACCCTGGAAAATCAGCTCGCGTTCCTGTGTCAGCAAGGCTTCTCCCTGGAGAACGCACTGTACGCTCTGTCCGCCGTGGGCCACTTCACACTGGGCTGCGTATTGGAGGAACAGGAGCATCAAGTAGCAAAAGAGGAAAGAGACACACCTACCACCGATTCTATGCCCCCACTTCTGAGACAAGCAATTGAGCTGTTCGACCATCAGGGAGCCGAACCTGCCTTCCTTTTCGGCCTGGAACTAATCATATGTGGCCTGGAGAAACAGCTAAAGTGCGAAAGCGGCTCCGCCGACGCACTGGACGATTTCGATCTGGACATGCTCCACGCCGACGCGCTCGACTAA",
        product="TetR",
    )

    # Domain Components
    nodes = [
        CircuitComponent(
            id="comp_1", name="pTac Promoter", component_type="promoter", y_max=5.0, K_d=0.05, n=2.0
        ),
        CircuitComponent(
            id="comp_2",
            name="LacI Repressor",
            component_type="cds",
            degradation_rate=0.1,
            translation_rate=1.2,
        ),
        CircuitComponent(
            id="comp_3", name="pTet Promoter", component_type="promoter", y_max=4.2, K_d=0.04, n=2.0
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
            source_id="comp_1", target_id="comp_2", interaction_type="transcription", strength=2.5
        ),
        CircuitEdge(
            source_id="comp_2", target_id="comp_3", interaction_type="repression", strength=1.0
        ),
        CircuitEdge(
            source_id="comp_3", target_id="comp_4", interaction_type="transcription", strength=2.1
        ),
        CircuitEdge(
            source_id="comp_4", target_id="comp_1", interaction_type="repression", strength=1.0
        ),
    ]

    state.set_circuit_components(nodes)
    state.set_circuit_edges(edges)

    # 2. Plasmid Construct (pUC19 Golden Gate Assembly)
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
    state.set_active_plasmid(plasmid)

    # 3. CRISPR Guide Targets
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
    state.set_grna_candidates([grna_1, grna_2])

    # 4. Pre-calculated Kinetic Simulation Results
    time_pts = [float(t) for t in range(0, 101, 2)]
    # Damped/Sustained Oscillation curves for 3 repressors
    laci_series = [10.0 + 8.0 * math.sin(0.15 * t) * math.exp(-0.005 * t) for t in time_pts]
    tetr_series = [10.0 + 8.0 * math.sin(0.15 * t + 2.09) * math.exp(-0.005 * t) for t in time_pts]
    ci_series = [10.0 + 8.0 * math.sin(0.15 * t + 4.18) * math.exp(-0.005 * t) for t in time_pts]

    sim_res = SimulationResult(
        time_points=time_pts,
        species_concentrations={"LacI": laci_series, "TetR": tetr_series, "cI": ci_series},
        status_message="Success: Sustained Repressilator Limit Cycle (ODE LSODA)",
        success=True,
    )
    state.set_simulation_result(sim_res)

    return state


class DemoShowcaseWindow(QMainWindow):
    """Marketing Showcase Window wrapper around SynBioPanel."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Karcytics Synthetic Biology — Customer Presentation & Demo Showcase")
        self.resize(1500, 950)

        # Central container
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top Marketing Banner & Feature Navigation Bar
        banner = QWidget(self)
        banner.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #0F172A, stop:0.5 #1E1B4B, stop:1 #0F172A); "
            "border-bottom: 2px solid #6366F1; padding: 6px 16px;"
        )
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(12, 6, 12, 6)

        title_label = QLabel(
            "🚀 <b>KARCYTICS SYNTHETIC BIOLOGY</b> <font color='#A5B4FC'>| Executive Product Showcase</font>"
        )
        title_label.setStyleSheet("color: #F8FAFC; font-size: 15px; font-weight: bold;")
        banner_layout.addWidget(title_label)

        banner_layout.addStretch()

        # Direct navigation jump buttons for live presentation
        btn_style = (
            "QPushButton { background: #312E81; color: #E0E7FF; font-weight: bold; "
            "font-size: 12px; border: 1px solid #6366F1; border-radius: 4px; padding: 6px 12px; } "
            "QPushButton:hover { background: #4338CA; color: #FFFFFF; border-color: #818CF8; } "
            "QPushButton:pressed { background: #3730A3; }"
        )

        self.btn_design = QPushButton("🧬 1. Circuit Canvas", self)
        self.btn_plasmid = QPushButton("🧪 2. Plasmid Assembly", self)
        self.btn_crispr = QPushButton("✂️ 3. CRISPR Engineering", self)
        self.btn_sim = QPushButton("📈 4. ODE Kinetic Simulation", self)
        self.btn_robot = QPushButton("🤖 5. Tecan Automation", self)
        self.btn_cat = QPushButton("📊 6. SBOL Catalogue", self)

        for btn in (
            self.btn_design,
            self.btn_plasmid,
            self.btn_crispr,
            self.btn_sim,
            self.btn_robot,
            self.btn_cat,
        ):
            btn.setStyleSheet(btn_style)
            banner_layout.addWidget(btn)

        main_layout.addWidget(banner)

        # Build SynBioPanel instance
        plugin_instance = initialize(context=None)
        self.synbio_panel = plugin_instance.create_panel(parent=self)

        # Inject Demo State
        demo_state = create_demo_state()
        self.synbio_panel.set_state(demo_state)

        main_layout.addWidget(self.synbio_panel, 1)

        # Connect Navigation Buttons to Tab Changes
        self.btn_design.clicked.connect(lambda: self._switch_tab(0))
        self.btn_plasmid.clicked.connect(lambda: self._switch_tab(2))
        self.btn_crispr.clicked.connect(lambda: self._switch_tab(3))
        self.btn_sim.clicked.connect(lambda: self._switch_tab(7))
        self.btn_robot.clicked.connect(lambda: self._switch_tab(6))
        self.btn_cat.clicked.connect(lambda: self._switch_tab(9))

    def _switch_tab(self, tab_index: int) -> None:
        if hasattr(self.synbio_panel, "_tab_bar"):
            self.synbio_panel._tab_bar.setCurrentIndex(tab_index)


def main() -> int:
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = DemoShowcaseWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

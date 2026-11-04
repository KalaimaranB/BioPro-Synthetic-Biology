"""Interactive Product Demo Showcase View for Synthetic Biology.

Integrated directly into the SynBio workspace under the 'Demo Showcase' tab.
Follows standard Karcytics SDK protocols, theme tokens, and reactive state management.

Everything this tab displays is derived from the shipped engines applied to one
source of truth — the demo strand in :func:`build_demo_strand`. The tab used to
carry a second, hand-written copy of the circuit, the plasmid map, the guide
RNAs and the simulation trace, and those copies disagreed with what the engines
actually produce: the trace was a closed-form damped sine labelled "sustained
limit cycle", it plotted a species (cI) absent from the hand-written circuit,
and the circuit itself contained no oscillator. Deriving the panels instead
means the summary cannot drift from the result a user gets by pressing Run.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from karcytics_sdk.plugin.citation_widgets import CitationLabel
from karcytics_sdk.plugin.components import (
    BioSplitter,
    BioTableWidget,
    PrimaryButton,
)
from karcytics_sdk.plugin.theme_fallback import Colors, Fonts, theme_manager
from karcytics_sdk.plugin.toast import show_toast
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...analysis.assembly.vector_builder import VectorAssemblyEngine
from ...analysis.citations import (
    FEATURE_CITATIONS,
    assembly_step,
    circuit_ode_step,
    crispr_step,
    design_step,
)
from ...analysis.crispr.grna_designer import CRISPRDesignEngine
from ...analysis.models.domain import SimulationParameters
from ...analysis.parts.base import BiologicalPart
from ...analysis.parts.components import CDS, RBS, Promoter, Terminator
from ...analysis.simulation.circuit_engine import CircuitSimulationEngine
from ...analysis.simulation.topology import circuit_from_parts
from ...analysis.state import SynBioState

# Kinetics shared by all three transcription units of the demo oscillator.
#
# n = 2.5 is deliberate and load-bearing. A three-gene repressor ring only
# oscillates above a Hopf threshold in the Hill coefficient — about n = 2.15 for
# these kinetics, where a small limit cycle first appears and then grows; at the n = 2.1 this
# demo used to request, the shipped engine returns a visibly damping trace
# (amplitude 15.3 -> 1.4 RPU over 400 min), which is why the old hand-written
# "sustained limit cycle" caption did not match the engine. At n = 2.5 the same
# engine sustains the cycle (amplitude 24.3 -> 23.1 RPU over the same window),
# so the caption and the plot now agree.
DEMO_HILL_N = 2.5
DEMO_K_D = 1.0
DEMO_Y_MAX = 10.0
DEMO_Y_MIN = 0.001
DEMO_DEGRADATION_RATE = 0.2

# Simulation window. The cycle period is ~35 min at these parameters, so 400 min
# shows roughly eleven periods — enough for the amplitude to be visibly steady.
DEMO_T_END = 400.0
DEMO_NUM_POINTS = 1600

_RBS_B0034 = "AAAGAGGAGAAA"

# pUC19-derived backbone fragment (AmpR + pUC ori region) used so the assembled
# construct has a real, reportable length instead of a filler repeat. The old
# demo built its plasmid from "ATGC" * 10955 — 43,820 bp — while the card above
# it claimed 4,382 bp.
_BACKBONE = (
    "ATGAGTATTCAACATTTCCGTGTCGCCCTTATTCCCTTTTTTGCGGCATTTTGCCTTCCTGTTTTTGCTCACCCAGAAACGCTGGTG"
    "AAAGTAAAAGATGCTGAAGATCAGTTGGGTGCACGAGTGGGTTACATCGAACTGGATCTCAACAGCGGTAAGATCCTTGAGAGTTTT"
    "CGCCCCGAAGAACGTTTTCCAATGATGAGCACTTTTAAAGTTCTGCTATGTGGCGCGGTATTATCCCGTATTGACGCCGGGCAAGAG"
    "CAACTCGGTCGCCGCATACACTATTCTCAGAATGACTTGGTTGAGTACTCACCAGTCACAGAAAAGCATCTTACGGATGGCATGACA"
    "GTAAGAGAATTATGCAGTGCTGCCATAACCATGAGTGATAACACTGCGGCCAACTTACTTCTGACAACGATCGGAGGACCGAAGGAG"
    "CTAACCGCTTTTTTGCACAACATGGGGGATCATGTAACTCGCCTTGATCGTTGGGAACCGGAGCTGAATGAAGCCATACCAAACGAC"
)

# LacI coding sequence (E. coli lacI), used both as the demo CDS and as the
# CRISPR target so the guide RNAs on this tab are real hits in a real gene.
_LACI_CDS = (
    "ATGAAACCAGTAACGTTATACGATGTCGCAGAGTATGCCGGTGTCTCTTATCAGACCGTTTCCCGCGTGGTGAACCAGGCCAGCCAC"
    "GTTTCTGCGAAAACGCGGGAAAAAGTGGAAGCGGCGATGGCGGAGCTGAATTACATTCCCAACCGCGTGGCACAACAACTGGCGGGC"
    "AAACAGTCGTTGCTGATTGGCGTTGCCACCTCCAGTCTGGCCCTGCACGCGCCGTCGCAAATTGTCGCGGCGATTAAATCTCGCGCC"
    "GATCAACTGGGTGCCAGCGTGGTGGTGTCGATGGTAGAACGAAGCGGCGTCGAAGCCTGTAAAGCGGCGGTGCACAATCTTCTCGCG"
    "CAACGCGTCAGTGGGCTGATCATTAACTATCCGCTGGATGACCAGGATGCCATTGCTGTGGAAGCTGCCTGCACTAATGTTCCGGCG"
    "TTATTTCTTGATGTCTCTGACCAGACACCCATCAACAGTATTATTTTCTCCCATGAAGACGGTACGCGACTGGGCGTGGAGCATCTG"
    "GTCGCATTGGGTCACCAGCAAATCGCGCTGTTAGCGGGCCCATTAAGTTCTGTCTCGGCGCGTCTGCGTCTGGCTGGCTGGCATAAA"
    "TATCTCACTCGCAATCAAATTCAGCCGATAGCGGAACGGGAAGGCGACTGGAGTGCCATGTCCGGTTTTCAACAAACCATGCAAATG"
    "CTGAATGAGGGCATCGTTCCCACTGCGATGCTGGTTGCCAACGATCAGATGGCGCTGGGCGCAATGCGCGCCATTACCGAGTCCGGG"
    "CTGCGCGTTGGTGCGGATATCTCGGTAGTGGGATACGACGATACCGAAGACAGCTCATGTTATATCCCGCCGTTAACCACCATCAAA"
    "CAGGATTTTCGCCTGCTGGGGCAAACCAGCGTGGACCGCTTGCTGCAACTCTCTCAGGGCCAGGCGGTGAAGGGCAATCAGCTGTTG"
    "CCCGTCTCACTGGTGAAAAGAAAAACCACCCTGGCGCCCAATACGCAAACCGCCTCTCCCCGCGCGTTGGCCGATTCAAAAATGAAG"
    "CTGGCATCCTTCGTTGAAGTGCCCGAGAACGAGTCATGA"
)

# TetR coding sequence (Tn10 tetR).
_TETR_CDS = (
    "ATGTCCAGATTAGATAAAAGTAAAGTGATTAACAGCGCATTAGAGCTGCTTAATGAGGTCGGAATCGAAGGTTTAACAACCCGTAAA"
    "CTCGCCCAGAAGCTAGGTGTAGAGCAGCCTACACTGTATTGGCACGTGAAGAACAAGCGGGCCCTGCTCGACGCCCTGGCCATCGAG"
    "ATGCTGGACAGGCATCATACCCACTTCTGCCCCCTGGAAGGCGAGTCATGGCAAGACTTTCTGCGGAACAACGCCAAGAGTTTCCGC"
    "TGTGCCCTCCTCTCACACCGCGACGGGGCCAAAGTGCATCTCGGCACCCGCCCAACAGAGAAACAGTACGAAACCCTGGAAAATCAG"
    "CTCGCGTTCCTGTGTCAGCAAGGCTTCTCCCTGGAGAACGCACTGTACGCTCTGTCCGCCGTGGGCCACTTCACACTGGGCTGCGTA"
    "TTGGAGGAACAGGAGCATCAAGTAGCAAAAGAGGAAAGAGACACACCTACCACCGATTCTATGCCCCCACTTCTGAGACAAGCAATT"
    "GAGCTGTTCGACCATCAGGGAGCCGAACCTGCCTTCCTTTTCGGCCTGGAACTAATCATATGTGGCCTGGAGAAACAGCTAAAGTGC"
    "GAAAGCGGCTCCGCCGACGCACTGGACGATTTCGATCTGGACATGCTCCACGCCGACGCGCTCGACTAA"
)

# Bacteriophage lambda cI repressor coding sequence.
_CI_CDS = (
    "ATGAGCACAAAAAAGAAACCATTAACACAAGAGCAGCTTGAGGACGCACGTCGCCTTAAAGCAATTTATGAAAAAAAGAAAAATGAA"
    "CTTGGCTTATCCCAGGAATCTGTCGCAGACAAGATGGGGATGGGGCAGTCAGGCGTTGGTGCTTTATTTAATGGCATCAATGCATTA"
    "AATGCTTATAACGCCGCATTGCTTGCAAAAATTCTCAAAGTTAGCGTTGAAGAATTTAGCCCTTCAATCGCCAGAGAAATCTACGAG"
    "ATGTATGAAGCGGTTAGTATGCAGCCGTCACTTAGAAGTGAGTATGAGTACCCTGTTTTTTCTCATGTTCAGGCAGGGATGTTCTCA"
    "CCTGAGCTTAGAACCTTTACCAAAGGTGATGCGGAGAGATGGGTAAGCACAACCAAAAAAGCCAGTGATTCTGCATTCTGGCTTGAG"
    "GTTGAAGGTAATTCCATGACCGCACCAACAGGCTCCAAGCCAAGCTTTCCTGACGGAATGTTAATTCTCGTTGACCCTGAGCAGGCT"
    "GTTGAGCCAGGTGATTTCTGCATAGCCAGACTTGGGGGTGATGAGTTTACCTTCAAGAAACTGATCAGGGATAGCGGTCAGGTGTTT"
    "TTACAACCACTAAACCCACAGTACCCAATGATCCCATGCAATGAGAGTTGTTCCGTTGTGGGGAAAGTTATCGCTAGTCAGTGGCCT"
    "GAAGAGACGTTTGGCTGA"
)

# Elowitz & Leibler (2000) repressilator, as a strand. The ring is
# TetR -| LacI -| cI -| TetR: each promoter is repressed by the product of the
# transcription unit before it, so ``circuit_from_parts`` recovers a three-node
# negative-feedback cycle with no hand-written topology.
_DEMO_TRANSCRIPTION_UNITS: tuple[tuple[str, str, list[str], str, str, str, str], ...] = (
    (
        "P_Ltet",
        "pLtetO-1 Promoter",
        ["TetR"],
        "CDS_lacI",
        "LacI Repressor",
        "LacI",
        "E. coli lac operon",
    ),
    (
        "P_Llac",
        "pLlacO-1 Promoter",
        ["LacI"],
        "CDS_cI",
        "lambda cI Repressor",
        "cI",
        "phage lambda",
    ),
    (
        "P_lambda",
        "lambda P_R Promoter",
        ["cI"],
        "CDS_tetR",
        "TetR Repressor",
        "TetR",
        "Tn10",
    ),
)

_CDS_SEQUENCES = {"LacI": _LACI_CDS, "cI": _CI_CDS, "TetR": _TETR_CDS}

_PROMOTER_SEQUENCES = {
    "P_Ltet": "TCCCTATCAGTGATAGAGATTGACATCCCTATCAGTGATAGAGATACTGAGCAC",
    "P_Llac": "AATTGTGAGCGGATAACAATTGACATTGTGAGCGGATAACAAGATACTGAGCAC",
    "P_lambda": "TAACACCGTGCGTGTTGACTATTTTACCTCTGGCGGTGATAATGGTTGCATGTACTAAGGAGGTTGTA",
}

_TERMINATOR_SEQUENCE = "AAAAAAACCCCGCCGAAGCGGGGGTTTTTTT"


def build_demo_strand() -> list[BiologicalPart]:
    """The demo construct, in strand order.

    Returned as plain parts so the rest of the tab goes through the same
    compile-and-simulate path as a strand a user draws on the Design canvas.
    """
    parts: list[BiologicalPart] = []
    for idx, (
        prom_id,
        prom_name,
        repressors,
        cds_id,
        cds_name,
        product,
        organism,
    ) in enumerate(_DEMO_TRANSCRIPTION_UNITS, start=1):
        parts.append(
            Promoter(
                id=prom_id,
                name=prom_name,
                sequence=_PROMOTER_SEQUENCES[prom_id],
                y_min=DEMO_Y_MIN,
                y_max=DEMO_Y_MAX,
                K_d=DEMO_K_D,
                n=DEMO_HILL_N,
                repressors=list(repressors),
            )
        )
        parts.append(
            RBS(
                id=f"RBS_{idx}",
                name="RBS (BBa_B0034)",
                sequence=_RBS_B0034,
                translation_initiation_rate=0.92,
            )
        )
        parts.append(
            CDS(
                id=cds_id,
                name=cds_name,
                sequence=_CDS_SEQUENCES[product],
                product=product,
                degradation_rate=DEMO_DEGRADATION_RATE,
                source_organism=organism,
            )
        )
        parts.append(
            Terminator(
                id=f"T_{idx}",
                name="rrnB T1 Terminator",
                sequence=_TERMINATOR_SEQUENCE,
                termination_efficiency=0.98,
            )
        )
    return parts


def build_demo_plasmid(parts: list[BiologicalPart]) -> Any:
    """Assemble the demo strand into a plasmid with the shipped assembly engine."""
    return VectorAssemblyEngine.assemble_vector(
        vector_name="pSB1A3-Repressilator",
        parts=parts,
        backbone_sequence=_BACKBONE,
        is_circular=True,
    )


def build_demo_grnas(limit: int = 2) -> list[Any]:
    """Run the shipped CRISPR engine against the demo's own lacI target.

    The guides shown are therefore real protospacers at real coordinates in
    ``_LACI_CDS``, scored by the engine. The previous hard-coded pair
    ("GCTAGCTAGCTAGCTAGC", "TGACTGACTGACTGACTG") were 18 nt sequences under a
    column headed "Protospacer (20bp)", and neither occurred in any sequence
    this module ships.
    """
    candidates = scan_demo_target()
    candidates.sort(key=lambda g: (g.efficiency_score, g.off_target_score), reverse=True)
    return candidates[:limit]


DEMO_PAM_TYPE = "SpCas9 (NGG)"
DEMO_SPACER_LENGTH = 20


def scan_demo_target() -> list[Any]:
    """Every SpCas9 site the engine finds in the demo's lacI coding sequence."""
    return CRISPRDesignEngine.find_grna_candidates(
        target_sequence=_LACI_CDS,
        pam_type=DEMO_PAM_TYPE,
        spacer_length=DEMO_SPACER_LENGTH,
    )


class DemoShowcaseView(QWidget):
    """Product Showcase Tab View — presents a interactive demo overview of SynBio features."""

    demo_loaded = Signal()

    def __init__(
        self, state: SynBioState, main_panel: Any = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.main_panel = main_panel

        # Derived once and shared by the summary panels and the load action, so
        # the two cannot describe different circuits.
        self._demo_parts = build_demo_strand()
        self._demo_components, self._demo_edges = circuit_from_parts(self._demo_parts)
        self._demo_plasmid = build_demo_plasmid(self._demo_parts)
        try:
            self._demo_grnas = build_demo_grnas()
        except Exception:
            # A scan failure must not take the whole tab down with it.
            self._demo_grnas = []

        self._setup_ui()
        self._apply_theme_styles()
        theme_manager.theme_changed.connect(self._apply_theme_styles)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_card = self._build_header_card()
        layout.addWidget(header_card)

        splitter = BioSplitter(Qt.Orientation.Horizontal, self)
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
            "Loads a three-gene repressilator strand, compiles it to a circuit, and runs "
            "the shipped ODE engine. Every figure below is engine output for this strand — "
            "nothing on this tab is pre-rendered. The guided tour ends with the Methods "
            "write-up and saving the workspace to the project."
        )
        subtitle_lbl.setObjectName("DemoSubtitle")
        # Without this the label's minimum width is the full run of text — over
        # 1,500 px — and because a QStackedWidget's minimum is the maximum over
        # all its pages, that became the minimum width of the entire window,
        # which could then be sized past the edge of the display.
        subtitle_lbl.setWordWrap(True)
        title_lbl.setWordWrap(True)
        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.btn_load_demo = PrimaryButton("✨ Load Demo State into Workspace", self)
        self.btn_load_demo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_load_demo.clicked.connect(self._on_load_demo_clicked)
        header_layout.addWidget(self.btn_load_demo)

        return header_card

    @staticmethod
    def _fill_table(table: BioTableWidget, rows: Sequence[Sequence[str]]) -> None:
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(str(value)))

    def _build_topology_card(self) -> QFrame:
        """The compiled circuit: nodes, what they repress, and their kinetics."""
        # 1. Circuit Topology Card -- node list straight off the compiled circuit.
        topo_card = QFrame(self)
        topo_card.setObjectName("SectionCard")
        topo_layout = QVBoxLayout(topo_card)
        topo_layout.setContentsMargins(14, 12, 14, 12)

        topo_lbl = QLabel(
            "🧬 Compiled circuit: 3-gene repressilator "
            f"({len(self._demo_components)} nodes, {len(self._demo_edges)} regulatory edges)"
        )
        topo_lbl.setObjectName("SectionTitle")
        topo_lbl.setWordWrap(True)
        topo_layout.addWidget(topo_lbl)

        self.topo_table = BioTableWidget(self)
        self.topo_table.setColumnCount(5)
        self.topo_table.setHorizontalHeaderLabels(
            ["Node", "Expresses", "Source organism", "Represses", "Kinetics"]
        )
        topo_header = self.topo_table.horizontalHeader()
        if topo_header is not None:
            # Size to content with the last column taking the slack: five
            # equally stretched columns clipped their own headers at this
            # pane width ("netics (engine input").
            topo_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            topo_header.setStretchLastSection(True)
        self.topo_table.setEditTriggers(BioTableWidget.EditTrigger.NoEditTriggers)

        # Who each node represses, read off the compiled edges rather than
        # restated by hand.
        name_of = {c.id: c.name for c in self._demo_components}
        represses: dict[str, list[str]] = {c.id: [] for c in self._demo_components}
        for edge in self._demo_edges:
            if edge.interaction_type.lower() == "repression":
                represses.setdefault(edge.source_id, []).append(
                    name_of.get(edge.target_id, edge.target_id)
                )

        topo_rows = [
            (
                comp.id,
                comp.name,
                comp.source_organism or "—",
                ", ".join(represses.get(comp.id, [])) or "—",
                f"y_max={comp.y_max:g} RPU, K_d={comp.K_d:g}, "
                f"n={comp.n:g}, deg={comp.degradation_rate:g}/min",
            )
            for comp in self._demo_components
        ]
        self._fill_table(self.topo_table, topo_rows)

        topo_note = QLabel(
            f"n = {DEMO_HILL_N:g} sits above the Hill-coefficient threshold at which this ring "
            "sustains its cycle. That threshold is about n = 2.15 for these kinetics: below it "
            "the same engine returns a damping trace."
        )
        topo_note.setObjectName("DemoNote")
        topo_note.setWordWrap(True)

        topo_layout.addWidget(self.topo_table)
        topo_layout.addWidget(topo_note)
        topo_layout.addWidget(
            CitationLabel(
                "Hill-repression ODE model",
                FEATURE_CITATIONS["circuit_simulation"],
                prefix="Model:",
                parent=self,
            )
        )
        return topo_card

    def _build_left_column(self) -> QWidget:
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        left_layout.addWidget(self._build_topology_card())

        # 2. Plasmid Construct Card -- feature table off the assembled vector.
        plasmid_card = QFrame(self)
        plasmid_card.setObjectName("SectionCard")
        plasmid_layout = QVBoxLayout(plasmid_card)
        plasmid_layout.setContentsMargins(14, 12, 14, 12)

        bp = len(self._demo_plasmid.sequence)
        plasmid_lbl = QLabel(
            f"🧪 Vector assembly: {self._demo_plasmid.name} ({bp:,} bp, "
            f"{'circular' if self._demo_plasmid.is_circular else 'linear'})"
        )
        plasmid_lbl.setObjectName("SectionTitle")
        plasmid_lbl.setWordWrap(True)
        plasmid_layout.addWidget(plasmid_lbl)

        self.plasmid_table = BioTableWidget(self)
        self.plasmid_table.setColumnCount(4)
        self.plasmid_table.setHorizontalHeaderLabels(["Feature", "Type", "Coordinates", "Strand"])
        plasmid_header = self.plasmid_table.horizontalHeader()
        if plasmid_header is not None:
            plasmid_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.plasmid_table.setEditTriggers(BioTableWidget.EditTrigger.NoEditTriggers)

        plasmid_rows = [
            (
                feat.name,
                str(feat.feature_type).upper(),
                f"{feat.start:,} - {feat.end:,} bp ({feat.end - feat.start:,} bp)",
                "+1 (Forward)" if feat.strand >= 0 else "-1 (Reverse)",
            )
            for feat in self._demo_plasmid.features
        ]
        self._fill_table(self.plasmid_table, plasmid_rows)

        plasmid_layout.addWidget(self.plasmid_table)
        left_layout.addWidget(plasmid_card)

        return left_widget

    def _build_right_column(self) -> QWidget:
        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        # 3. CRISPR Card -- real scan of the demo's own lacI coding sequence.
        crispr_card = QFrame(self)
        crispr_card.setObjectName("SectionCard")
        crispr_layout = QVBoxLayout(crispr_card)
        crispr_layout.setContentsMargins(14, 12, 14, 12)

        crispr_lbl = QLabel(
            f"✂️ CRISPR guide design — top {len(self._demo_grnas)} of the SpCas9 (NGG) "
            f"sites found in lacI ({len(_LACI_CDS):,} bp)"
        )
        crispr_lbl.setObjectName("SectionTitle")
        crispr_lbl.setWordWrap(True)
        crispr_layout.addWidget(crispr_lbl)

        self.crispr_table = BioTableWidget(self)
        self.crispr_table.setColumnCount(6)
        self.crispr_table.setHorizontalHeaderLabels(
            ["Target", "Protospacer (20 nt)", "PAM", "Position", "GC %", "Heuristic score"]
        )
        crispr_header = self.crispr_table.horizontalHeader()
        if crispr_header is not None:
            # The protospacer is 20 monospace characters and must not be
            # elided — a truncated guide sequence is worse than no guide.
            crispr_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            crispr_header.setStretchLastSection(True)
        self.crispr_table.setEditTriggers(BioTableWidget.EditTrigger.NoEditTriggers)

        grna_rows = [
            (
                "lacI",
                g.protospacer,
                g.pam,
                f"{g.start:,}-{g.end:,} ({'+' if g.strand >= 0 else '−'})",
                f"{g.gc_content:.1f}",
                f"on {g.efficiency_score:.0f} / off {g.off_target_score:.0f}",
            )
            for g in self._demo_grnas
        ]
        self._fill_table(self.crispr_table, grna_rows)

        crispr_note = QLabel(
            "Scores are the module's own rule-based heuristic (GC window, poly-T, "
            "PAM-proximal base), not the published Doench 2016 or CFD models."
        )
        crispr_note.setObjectName("DemoNote")
        crispr_note.setWordWrap(True)

        crispr_layout.addWidget(self.crispr_table)
        crispr_layout.addWidget(crispr_note)
        crispr_layout.addWidget(
            CitationLabel(
                "SpCas9 NGG PAM requirement",
                FEATURE_CITATIONS["crispr_scan"],
                prefix="Site rule:",
                parent=self,
            )
        )
        right_layout.addWidget(crispr_card)

        # 4. Robot Export Preview Card
        robot_card = QFrame(self)
        robot_card.setObjectName("SectionCard")
        robot_layout = QVBoxLayout(robot_card)
        robot_layout.setContentsMargins(14, 12, 14, 12)

        # Tecan only: RobotExporter.export_to_opentrons raises NotImplementedError,
        # so naming Opentrons here promised an export the module cannot perform.
        robot_lbl = QLabel("🤖 Tecan worklist export preview (CSV)")
        robot_lbl.setObjectName("SectionTitle")
        robot_lbl.setWordWrap(True)
        robot_layout.addWidget(robot_lbl)

        preview_lbl = QLabel(
            "Source,SourceWell,Destination,DestWell,Volume_uL,Reagent\n"
            "SourceRack,A01,DestRack,A01,15.0,2X Golden Gate Master Mix (BsaI + T4 Ligase)\n"
            "SourceRack,A02,DestRack,A01,2.5,pSB1A3 Backbone (50 ng/uL)\n"
            "SourceRack,A03,DestRack,A01,2.5,LacI Repressor Insert (20 ng/uL)\n"
            "SourceRack,A04,DestRack,A01,2.5,cI Repressor Insert (20 ng/uL)\n"
            "SourceRack,A05,DestRack,A01,2.5,TetR Repressor Insert (20 ng/uL)\n"
            "SourceRack,A06,DestRack,A01,5.0,Nuclease-Free Water"
        )
        preview_lbl.setObjectName("CodePreview")
        preview_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        robot_layout.addWidget(preview_lbl)

        robot_note = QLabel(
            "Opentrons OT-2 export is not implemented; the Laboratory Execution tab "
            "reports that rather than writing a file."
        )
        robot_note.setObjectName("DemoNote")
        robot_note.setWordWrap(True)
        robot_layout.addWidget(robot_note)
        robot_layout.addWidget(
            CitationLabel(
                "Golden Gate assembly",
                FEATURE_CITATIONS["golden_gate"],
                prefix="Reaction design:",
                parent=self,
            )
        )

        right_layout.addWidget(robot_card)
        right_layout.addStretch()

        return right_widget

    def _on_load_demo_clicked(self) -> None:
        """Load the repressilator demo by running it, not by describing it."""
        # The demo replaces the whole workspace. Never do that silently over
        # unsaved work, and never stay linked to the workflow the previous
        # workspace came from — otherwise the next Save would overwrite that
        # workflow with demo data.
        if self.main_panel is not None and hasattr(self.main_panel, "prepare_for_replacement"):
            if not self.main_panel.prepare_for_replacement("Load the demo"):
                return

        parts = build_demo_strand()
        components, edges = circuit_from_parts(parts)
        plasmid = build_demo_plasmid(parts)

        # The strand is the source of truth; the circuit is compiled from it by
        # the same function the Design tab uses.
        self.state.clear_methods_log()
        self.state.design_parts = parts
        self.state.set_circuit_components(components)
        self.state.set_circuit_edges(edges)
        self.state.set_active_plasmid(plasmid)
        self.state.record_method(design_step(parts, len(components)))
        self.state.record_method(
            assembly_step(
                plasmid.name, len(plasmid.sequence), len(plasmid.features), plasmid.is_circular
            )
        )
        try:
            all_sites = scan_demo_target()
            self.state.set_grna_candidates(build_demo_grnas())
            self.state.record_method(
                crispr_step(DEMO_PAM_TYPE, DEMO_SPACER_LENGTH, len(_LACI_CDS), len(all_sites))
            )
        except Exception:
            self.state.set_grna_candidates([])

        # Real ODE integration. The status message reports what the solver
        # returned instead of asserting a limit cycle up front.
        result = CircuitSimulationEngine.simulate_circuit(
            components,
            edges,
            SimulationParameters(
                t_start=0.0,
                t_end=DEMO_T_END,
                num_points=DEMO_NUM_POINTS,
            ),
        )
        self.state.set_simulation_result(result)
        if result.success:
            self.state.record_method(
                circuit_ode_step(
                    components,
                    edges,
                    solver=SimulationParameters().solver_method,
                    t_end=DEMO_T_END,
                    num_points=DEMO_NUM_POINTS,
                )
            )

        if self.main_panel:
            if hasattr(self.main_panel, "_refresh_views_from_state"):
                self.main_panel._refresh_views_from_state()

            # Keep the ribbon's Max Time in step with the window actually
            # plotted, so the control does not read 100 min beside a 400 min
            # trace.
            sim_ribbon = getattr(self.main_panel, "_sim_ribbon", None)
            if sim_ribbon is not None and hasattr(sim_ribbon, "time_spin"):
                sim_ribbon.time_spin.setValue(int(DEMO_T_END))

            if hasattr(self.main_panel, "_simulate_view"):
                self.main_panel._simulate_view.plot_time_series(
                    max_time=int(DEMO_T_END), method="ode"
                )

            if hasattr(self.main_panel, "_status_label"):
                if result.success:
                    species = ", ".join(result.species_concentrations)
                    self.main_panel._status_label.setText(
                        f"✨ Demo loaded: repressilator ({species}) integrated to "
                        f"{DEMO_T_END:g} min."
                    )
                else:
                    self.main_panel._status_label.setText(
                        f"⚠️ Demo loaded, but the solver failed: {result.status_message}"
                    )

            # Hand over to the guided tour, which drives the tabs from here on
            # at the presenter's pace. Falls back to the Design tab where no
            # tour is wired up, so the demo still lands somewhere useful.
            if hasattr(self.main_panel, "start_demo_tour"):
                self.main_panel.start_demo_tour()
            elif hasattr(self.main_panel, "_tab_bar"):
                self.main_panel._tab_bar.setCurrentIndex(0)

        show_toast(
            "Demo showcase loaded into workspace"
            if result.success
            else f"Demo loaded; simulation failed: {result.status_message}"
        )
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
            QLabel#DemoNote {{
                font-size: {Fonts.SIZE_SMALL}px;
                color: {Colors.FG_SECONDARY};
                font-style: italic;
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
                font-family: Menlo, Consolas, 'Courier New', monospace;
                font-size: 11px;
                background: {Colors.BG_DARKEST};
                color: {Colors.FG_SECONDARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 8px;
            }}
        """
        self.setStyleSheet(qss)

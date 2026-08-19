import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
except ImportError:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from karcytics_sdk.plugin.theme_fallback import Colors

from ...analysis.parts.base import BiologicalPart
from ...analysis.parts.components import CDS, RBS, Promoter, Terminator


class WTGraphDialog(QDialog):
    """Modal popup dialog presenting comparative matplotlib transfer curve
    (WT vs Mutation).
    """

    def __init__(self, figure, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comparative Biophysical Transfer Curve (WT vs Mutation)")
        self.resize(720, 520)
        self._setup_ui(figure)

    def _setup_ui(self, figure):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.canvas = FigureCanvasQTAgg(figure)
        layout.addWidget(self.canvas, 1)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DARKEST}; "
            f"font-weight: bold; padding: 6px 20px; border-radius: 4px;"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)


class ModelDetailsDialog(QDialog):
    """Modal popup dialog showing academic, mathematical, and biophysical model
    breakdowns.
    """

    def __init__(self, model_key: str, parent=None):
        super().__init__(parent)
        self.model_key = model_key.lower()
        self.setWindowTitle("Biophysical & Mathematical Model Mechanics")
        self.resize(650, 480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setStyleSheet(
            f"background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; "
            f"border: 1px solid {Colors.BORDER}; font-size: 13px; padding: 12px;"
        )
        self.browser.setHtml(self._generate_html_content())
        layout.addWidget(self.browser)

        close_btn = QPushButton("Close")
        close_btn.setStyleSheet(
            f"background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DARKEST}; "
            f"font-weight: bold; padding: 6px 20px; border-radius: 4px;"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignRight)

    def _generate_html_content(self) -> str:
        if "thermodynamic pwm" in self.model_key or "promoter" in self.model_key:
            return (
                f"<h2 style='color: {Colors.ACCENT_PRIMARY}; margin-top: 0;'>⚙️ "
                "Promoter Thermodynamic PWM Model</h2>"
                "<p><b>Overview:</b> Evaluates RNA Polymerase (RNAP &sigma;<sup>70"
                "</sup> holoenzyme) binding kinetics and open-complex formation using "
                "Position Weight Matrices (PWM) and steric spacer strain "
                "functions.</p>"
                "<h3 style='color: #4caf50;'>1. Hexamer Motif Recognition (-35 & "
                "-10 Boxes)</h3>"
                "<p>The sliding window algorithm scans the query DNA string to locate "
                "the window matching the two canonical hexamers:</p>"
                "<ul>"
                "<li><b>-35 Box:</b> Consensus <code>TTGACA</code> (positions -35 to "
                "-30 relative to TSS)</li>"
                "<li><b>-10 Box (Pribnow Box):</b> Consensus <code>TATAAT</code> "
                "(positions -12 to -7 relative to TSS)</li>"
                "</ul>"
                "<p>Position-specific thermodynamic mismatch energy penalties "
                "(&Delta;&Delta;G in k<sub>B</sub>T) are accumulated for nucleotide "
                "deviations based on empirical binding preference matrices.</p>"
                "<h3 style='color: #4caf50;'>2. Spacer Length Steric Strain</h3>"
                "<p>The optimal spacer between the -35 and -10 hexamers is "
                "<b>17 bp</b>. Deviations (15&ndash;19 bp) introduce torsional "
                "strain on the &sigma;<sub>4</sub> and &sigma;<sub>2</sub> "
                "subdomains:</p>"
                "<ul>"
                "<li>Spacer = 17 bp: &Delta;G<sub>spacer</sub> = 0.0 "
                "k<sub>B</sub>T</li>"
                "<li>Spacer = 16 or 18 bp (&plusmn;1 bp): &Delta;G<sub>spacer</sub> = "
                "1.8 k<sub>B</sub>T</li>"
                "<li>Spacer = 15 or 19 bp (&plusmn;2 bp): &Delta;G<sub>spacer</sub> = "
                "4.5 k<sub>B</sub>T</li>"
                "</ul>"
                "<h3 style='color: #4caf50;'>3. Mathematical Parameter Mapping</h3>"
                "<p>The total binding penalty score (&Delta;G<sub>penalty</sub> = "
                "P<sub>-35</sub> + P<sub>-10</sub> + P<sub>spacer</sub>) is mapped to "
                "transfer curve parameters:</p>"
                "<p><b>Maximum Promoter Expression (y<sub>max</sub>):</b></p>"
                f"<div style='background: {Colors.BG_MEDIUM}; padding: 8px; "
                "border-radius: 4px; font-family: monospace;'>"
                "y<sub>max</sub> = y<sub>min_max</sub> + (y<sub>max_ref</sub> - "
                "y<sub>min_max</sub>) &middot; exp(-0.35 &middot; &Delta;G<sub>penalty"
                "</sub>)"
                "</div>"
                "<p><b>Repression Threshold / Dissociation Constant (K<sub>d</sub>"
                "):</b></p>"
                f"<div style='background: {Colors.BG_MEDIUM}; padding: 8px; "
                "border-radius: 4px; font-family: monospace;'>"
                "K<sub>d</sub> = min(100.0, K<sub>d_base</sub> &middot; "
                "exp(0.40 &middot; &Delta;G<sub>penalty</sub>))"
                "</div>"
            )
        elif (
            "cai" in self.model_key
            or "blosum62" in self.model_key
            or "cds" in self.model_key
        ):
            return (
                f"<h2 style='color: {Colors.ACCENT_PRIMARY}; margin-top: 0;'>🧱 CDS "
                "CAI & BLOSUM62 Stability Model</h2>"
                "<p><b>Overview:</b> Evaluates protein expression kinetics using a "
                "dual-engine architecture: <i>E. coli</i> Codon Adaptation Index (CAI) "
                "for translation speed and BLOSUM62 substitution scoring for 3D "
                "folding stability.</p>"
                "<h3 style='color: #4caf50;'>1. Ribosomal Translation Speed (CAI "
                "Model)</h3>"
                "<p>Scans the 3-bp codon sequence against host tRNA abundance "
                "profiles (w<sub>i</sub> relative adaptiveness values):</p>"
                f"<div style='background: {Colors.BG_MEDIUM}; padding: 8px; "
                "border-radius: 4px; font-family: monospace;'>"
                "CAI = exp( (1 / N<sub>sense</sub>) &sum; ln(w<sub>i</sub>) )"
                "</div>"
                "<p>Codon bias directly determines translation elongation rate "
                "<code>translation_rate</code> (0.005 to 1.0 min<sup>-1</sup>). Rare "
                "codons cause ribosomal stalling and mRNA degradation.</p>"
                "<h3 style='color: #4caf50;'>2. Thermodynamic Folding Stability "
                "(BLOSUM62 Model)</h3>"
                "<p>Translates DNA to protein and aligns against characterized CDS "
                "reference sequences. Substitutions are scored via the BLOSUM62 "
                "matrix:</p>"
                "<ul>"
                "<li><b>Conservative Mutations (e.g., L &harr; I, K &harr; R):</b> "
                "Positive matrix scores (&Delta;S<sub>i</sub> &approx; 0&ndash;2); "
                "minimal folding impact; normal degradation rate (&approx; 0.01 min"
                "<sup>-1</sup>).</li>"
                "<li><b>Non-Conservative Mutations (e.g., G &harr; W, D &harr; F):</b> "
                "Negative matrix scores (&Delta;S<sub>i</sub> &approx; 10&ndash;13); "
                "severe structural disruption triggering intracellular proteolysis "
                "by host Lon/ClpXP proteases (up to 0.5 min<sup>-1</sup>).</li>"
                "</ul>"
            )
        else:
            return (
                f"<h2 style='color: {Colors.ACCENT_PRIMARY}; margin-top: 0;'>🔍 "
                "k-Nearest Neighbors (k-NN) Fallback Model</h2>"
                "<p><b>Overview:</b> Legacy alignment fallback utilizing Levenshtein "
                "edit distance and inverse-distance weighting across characterized "
                "parts in the catalogue.</p>"
                "<h3 style='color: #4caf50;'>1. Sequence Alignment & Distance "
                "Metric</h3>"
                "<p>Computes string edit distance (substitutions, insertions, "
                "deletions) between the query sequence and characterized repository "
                "parts.</p>"
                "<h3 style='color: #4caf50;'>2. Inverse-Distance Weighting</h3>"
                f"<div style='background: {Colors.BG_MEDIUM}; padding: 8px; "
                "border-radius: 4px; font-family: monospace;'>"
                "w<sub>i</sub> = 1 / distance<sub>i</sub>"
                "</div>"
                "<p>Averages top-<i>k</i> nearest neighbors weighted by sequence "
                "proximity to predict continuous parameters.</p>"
            )


class PartInspector(QWidget):
    """Details pane for viewing and editing a biological part."""

    part_saved = pyqtSignal(BiologicalPart)
    part_deleted = pyqtSignal(str)

    def __init__(self, parent=None, catalogue_service=None):
        super().__init__(parent)
        self.current_part = None
        self.catalogue_service = catalogue_service
        self._setup_ui()
        self.setMinimumWidth(320)
        self.setMaximumWidth(450)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.header_lbl = QLabel("Part Inspector")
        self.header_lbl.setStyleSheet(
            f"font-size: 24px; font-weight: bold; color: {Colors.FG_PRIMARY};"
        )
        self.layout.addWidget(self.header_lbl)

        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # Properties Tab
        self.props_tab = QWidget()
        self.props_layout = QFormLayout(self.props_tab)

        self.id_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Promoter", "CDS", "Terminator", "RBS"])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        self.props_layout.addRow("ID:", self.id_edit)
        self.props_layout.addRow("Name:", self.name_edit)
        self.props_layout.addRow("Type:", self.type_combo)

        # Promoter
        self.kd_lbl = QLabel("K_d:")
        self.kd_edit = QLineEdit()
        self.ymax_lbl = QLabel("y_max:")
        self.ymax_edit = QLineEdit()
        self.ymin_lbl = QLabel("y_min:")
        self.ymin_edit = QLineEdit()
        self.n_lbl = QLabel("n:")
        self.n_edit = QLineEdit()

        self.props_layout.addRow(self.kd_lbl, self.kd_edit)
        self.props_layout.addRow(self.ymax_lbl, self.ymax_edit)
        self.props_layout.addRow(self.ymin_lbl, self.ymin_edit)
        self.props_layout.addRow(self.n_lbl, self.n_edit)

        # CDS
        self.trans_rate_lbl = QLabel("Translation Rate:")
        self.trans_rate_edit = QLineEdit()
        self.deg_rate_lbl = QLabel("Degradation Rate:")
        self.deg_rate_edit = QLineEdit()
        self.product_lbl = QLabel("Product:")
        self.product_edit = QLineEdit()

        self.props_layout.addRow(self.trans_rate_lbl, self.trans_rate_edit)
        self.props_layout.addRow(self.deg_rate_lbl, self.deg_rate_edit)
        self.props_layout.addRow(self.product_lbl, self.product_edit)

        # Terminator
        self.term_eff_lbl = QLabel("Termination Eff.:")
        self.term_eff_edit = QLineEdit()
        self.props_layout.addRow(self.term_eff_lbl, self.term_eff_edit)

        # RBS
        self.rbs_init_rate_lbl = QLabel("Translation Init Rate:")
        self.rbs_init_rate_edit = QLineEdit()
        self.props_layout.addRow(self.rbs_init_rate_lbl, self.rbs_init_rate_edit)

        self.desc_lbl = QLabel()
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.desc_lbl.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-style: italic; margin-top: 10px;"
        )
        self.props_layout.addRow(self.desc_lbl)

        # Prediction Status Indicator Badge
        self.prediction_status_lbl = QLabel()
        self.prediction_status_lbl.setWordWrap(True)
        self.prediction_status_lbl.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.prediction_status_lbl.setStyleSheet(
            f"color: {Colors.ACCENT_PRIMARY}; font-weight: bold; padding: 4px; "
            f"border: 1px solid {Colors.ACCENT_PRIMARY}; border-radius: 4px; "
            "margin-top: 6px;"
        )
        self.prediction_status_lbl.setVisible(False)
        self.props_layout.addRow(self.prediction_status_lbl)

        # "Learn More" Educational Info Card
        self.prediction_info_card = QLabel()
        self.prediction_info_card.setWordWrap(True)
        self.prediction_info_card.setOpenExternalLinks(False)
        self.prediction_info_card.linkActivated.connect(self._open_model_details_dialog)
        self.prediction_info_card.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.prediction_info_card.setStyleSheet(
            f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; "
            f"color: {Colors.FG_SECONDARY}; border-radius: 6px; padding: 8px; "
            "font-size: 11px; margin-top: 4px;"
        )
        self.prediction_info_card.setVisible(False)
        self.props_layout.addRow(self.prediction_info_card)

        # "Graph WT vs Mutation" Button in Inspector Panel below Prediction Badge
        self.graph_wt_btn = QPushButton("Graph WT vs Mutation")
        self.graph_wt_btn.setProperty("variant", "primary")
        self.graph_wt_btn.setObjectName("PrimaryButton")
        self.graph_wt_btn.clicked.connect(self._on_graph_wt_vs_mutation)
        self.props_layout.addRow(self.graph_wt_btn)

        self.tabs.addTab(self.props_tab, "Properties")

        # Sequence Tab
        self.seq_tab = QWidget()
        self.seq_layout = QVBoxLayout(self.seq_tab)

        self.seq_edit = QTextEdit()
        self.seq_edit.setPlaceholderText(
            "Paste or type DNA sequence here (A, C, G, T)..."
        )
        self.seq_edit.textChanged.connect(self._on_sequence_changed)
        self.seq_layout.addWidget(self.seq_edit)

        self.predict_btn = QPushButton("⚡ Predict Parameters (k-NN)")
        self.predict_btn.setProperty("variant", "secondary")
        self.predict_btn.setObjectName("SecondaryButton")
        self.predict_btn.clicked.connect(self._run_prediction)
        self.seq_layout.addWidget(self.predict_btn)

        self.seq_graph_btn = QPushButton("📊 Graph WT vs Mutation")
        self.seq_graph_btn.setProperty("variant", "primary")
        self.seq_graph_btn.setObjectName("PrimaryButton")
        self.seq_graph_btn.clicked.connect(self._on_graph_wt_vs_mutation)
        self.seq_layout.addWidget(self.seq_graph_btn)

        self.tabs.addTab(self.seq_tab, "Sequence")

        # Structure Tab
        self.struct_tab = QWidget()
        self.struct_layout = QVBoxLayout(self.struct_tab)
        self.struct_lbl = QLabel()
        self.struct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.struct_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.struct_layout.addWidget(self.struct_lbl)
        self.tabs.addTab(self.struct_tab, "Structure")

        # Action Buttons Layout (Save & Delete)
        self.btn_layout = QHBoxLayout()

        self.save_btn = QPushButton("Save / Update Part")
        self.save_btn.setProperty("variant", "primary")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.clicked.connect(self._on_save)
        self.btn_layout.addWidget(self.save_btn)

        self.delete_btn = QPushButton("Delete Part")
        self.delete_btn.setProperty("variant", "danger")
        self.delete_btn.setObjectName("DangerButton")
        self.delete_btn.clicked.connect(self._on_delete)
        self.btn_layout.addWidget(self.delete_btn)

        self.layout.addLayout(self.btn_layout)

        self.refresh_styles()
        self.clear()
        self._on_type_changed(self.type_combo.currentText())

    def refresh_styles(self) -> None:
        """Apply theme-based styles dynamically without hardcoded colors."""
        hover_primary = getattr(Colors, "ACCENT_PRIMARY_HOVER", "#0097a7")
        danger_color = getattr(
            Colors, "ACCENT_NEGATIVE", getattr(Colors, "ACCENT_DANGER", "#ef5350")
        )
        sec_hover_bg = getattr(
            Colors, "BG_LIGHT", getattr(Colors, "BG_DARK", "#161b22")
        )
        bg_darkest = getattr(Colors, "BG_DARKEST", "#0d1117")
        bg_medium = getattr(Colors, "BG_MEDIUM", "#21262d")
        fg_primary = getattr(Colors, "FG_PRIMARY", "#e6edf3")
        border = getattr(Colors, "BORDER", "#30363d")
        accent_primary = getattr(Colors, "ACCENT_PRIMARY", "#00bcd4")

        btn_qss = f"""
            QPushButton#PrimaryButton, QPushButton[variant="primary"] {{
                background-color: {accent_primary};
                color: {bg_darkest};
                border: 1px solid {accent_primary};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton#PrimaryButton:hover, QPushButton[variant="primary"]:hover {{
                background-color: {hover_primary};
                border-color: {hover_primary};
                color: {bg_darkest};
            }}
            QPushButton#SecondaryButton, QPushButton[variant="secondary"] {{
                background-color: {bg_medium};
                color: {fg_primary};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton#SecondaryButton:hover, QPushButton[variant="secondary"]:hover {{
                background-color: {sec_hover_bg};
                border-color: {accent_primary};
            }}
            QPushButton#DangerButton, QPushButton[variant="danger"] {{
                background-color: {danger_color};
                color: white;
                border: 1px solid {danger_color};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }}
            QPushButton#DangerButton:hover, QPushButton[variant="danger"]:hover {{
                background-color: #d32f2f;
                border-color: #d32f2f;
            }}
        """
        self.setStyleSheet(btn_qss)

    def _on_type_changed(self, text):
        part_type = text.lower()

        is_promoter = part_type == "promoter"
        self.kd_lbl.setVisible(is_promoter)
        self.kd_edit.setVisible(is_promoter)
        self.ymax_lbl.setVisible(is_promoter)
        self.ymax_edit.setVisible(is_promoter)
        self.ymin_lbl.setVisible(is_promoter)
        self.ymin_edit.setVisible(is_promoter)
        self.n_lbl.setVisible(is_promoter)
        self.n_edit.setVisible(is_promoter)

        is_cds = part_type == "cds"
        self.trans_rate_lbl.setVisible(is_cds)
        self.trans_rate_edit.setVisible(is_cds)
        self.deg_rate_lbl.setVisible(is_cds)
        self.deg_rate_edit.setVisible(is_cds)
        self.product_lbl.setVisible(is_cds)
        self.product_edit.setVisible(is_cds)

        is_term = part_type == "terminator"
        self.term_eff_lbl.setVisible(is_term)
        self.term_eff_edit.setVisible(is_term)

        is_rbs = part_type == "rbs"
        self.rbs_init_rate_lbl.setVisible(is_rbs)
        self.rbs_init_rate_edit.setVisible(is_rbs)

    def set_part(self, part: BiologicalPart | None = None):
        """Populate the inspector. If None, clear for new part."""
        self.current_part = part

        is_editable = part.is_custom if part else True

        self.name_edit.setReadOnly(not is_editable)
        self.type_combo.setEnabled(is_editable)
        self.seq_edit.setReadOnly(not is_editable)

        self.kd_edit.setReadOnly(not is_editable)
        self.ymax_edit.setReadOnly(not is_editable)
        self.ymin_edit.setReadOnly(not is_editable)
        self.n_edit.setReadOnly(not is_editable)

        self.trans_rate_edit.setReadOnly(not is_editable)
        self.deg_rate_edit.setReadOnly(not is_editable)
        self.product_edit.setReadOnly(not is_editable)

        self.term_eff_edit.setReadOnly(not is_editable)
        self.rbs_init_rate_edit.setReadOnly(not is_editable)

        self.save_btn.setVisible(is_editable)
        self.delete_btn.setVisible(part is not None and is_editable)

        if part is None:
            self.header_lbl.setText("New Theoretical Part")
            self.id_edit.setText("")
            self.id_edit.setReadOnly(False)
            self.name_edit.setText("")
            self.type_combo.setCurrentIndex(0)
            self.seq_edit.setText("")

            self.kd_edit.setText("")
            self.ymax_edit.setText("")
            self.ymin_edit.setText("")
            self.n_edit.setText("")

            self.trans_rate_edit.setText("")
            self.deg_rate_edit.setText("")
            self.product_edit.setText("")

            self.term_eff_edit.setText("")
            self.rbs_init_rate_edit.setText("")

            self.desc_lbl.setText("")
            self.prediction_status_lbl.setVisible(False)
            self.prediction_info_card.setVisible(False)
            self.struct_lbl.setText("No structure generated for this part.")
            self.struct_lbl.setStyleSheet(
                f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; "
                f"color: {Colors.FG_SECONDARY};"
            )
        else:
            self.header_lbl.setText(f"{part.name} ({part.id})")
            self.id_edit.setText(part.id)
            self.id_edit.setReadOnly(True)
            self.name_edit.setText(part.name)

            for i in range(self.type_combo.count()):
                if self.type_combo.itemText(i).lower() == part.part_type.lower():
                    self.type_combo.setCurrentIndex(i)
                    break

            self.seq_edit.setText(part.sequence)
            self.desc_lbl.setText(
                part.description if part.description else "No description available."
            )

            self.kd_edit.setText("")
            self.ymax_edit.setText("")
            self.ymin_edit.setText("")
            self.n_edit.setText("")

            self.trans_rate_edit.setText("")
            self.deg_rate_edit.setText("")
            self.product_edit.setText("")

            self.term_eff_edit.setText("")
            self.rbs_init_rate_edit.setText("")

            if isinstance(part, Promoter):
                self.kd_edit.setText(str(part.K_d) if part.K_d is not None else "")
                self.ymax_edit.setText(
                    str(part.y_max) if part.y_max is not None else ""
                )
                self.ymin_edit.setText(
                    str(part.y_min) if part.y_min is not None else ""
                )
                self.n_edit.setText(str(part.n) if part.n is not None else "")
            elif isinstance(part, CDS):
                self.trans_rate_edit.setText(
                    str(part.translation_rate)
                    if part.translation_rate is not None
                    else ""
                )
                self.deg_rate_edit.setText(
                    str(part.degradation_rate)
                    if part.degradation_rate is not None
                    else ""
                )
                self.product_edit.setText(str(part.product) if part.product else "")
            elif isinstance(part, Terminator):
                self.term_eff_edit.setText(
                    str(part.termination_efficiency)
                    if part.termination_efficiency is not None
                    else ""
                )
            elif isinstance(part, RBS):
                self.rbs_init_rate_edit.setText(
                    str(part.translation_initiation_rate)
                    if part.translation_initiation_rate is not None
                    else ""
                )

            self._render_static_structure(part)

    def clear(self):
        self.set_part(None)

    def _render_static_structure(self, part: BiologicalPart):
        """Show a static 2D image or a generic placeholder."""
        image_rel_path = part.properties.get("image_path")

        if image_rel_path:
            # Resolve relative path to absolute
            import karcytics_plugins.synthetic_biology.analysis.catalogue.service as svc

            base_dir = os.path.dirname(os.path.abspath(svc.__file__))
            abs_path = os.path.join(
                base_dir,
                os.path.basename(image_rel_path)
                if not image_rel_path.startswith("images")
                else image_rel_path,
            )

            if os.path.exists(abs_path):
                pixmap = QPixmap(abs_path)
                self.struct_lbl.setStyleSheet("")
                self.struct_lbl.setPixmap(
                    pixmap.scaled(
                        self.struct_tab.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return

        self.struct_lbl.setStyleSheet(
            f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; "
            f"color: {Colors.FG_SECONDARY};"
        )
        self.struct_lbl.setText("No structure available.\\n(Generic Placeholder)")

    def _on_save(self):
        if self.current_part and not self.current_part.is_custom:
            return  # Safety check

        part_id = self.id_edit.text().strip()
        if not part_id:
            return

        name = self.name_edit.text().strip()
        seq = self.seq_edit.toPlainText().strip()
        part_type = self.type_combo.currentText().lower()

        def _parse_float(txt):
            try:
                return float(txt)
            except ValueError:
                return None

        part = self.current_part
        if not part:
            if part_type == "promoter":
                part = Promoter(id=part_id, name=name, sequence=seq)
            elif part_type == "terminator":
                part = Terminator(id=part_id, name=name, sequence=seq)
            elif part_type == "rbs":
                part = RBS(id=part_id, name=name, sequence=seq)
            else:
                part = CDS(id=part_id, name=name, sequence=seq)
        else:
            part.name = name
            part.sequence = seq

        if isinstance(part, Promoter):
            part.K_d = _parse_float(self.kd_edit.text())
            part.y_max = _parse_float(self.ymax_edit.text())
            part.y_min = _parse_float(self.ymin_edit.text())
            part.n = _parse_float(self.n_edit.text())
        elif isinstance(part, CDS):
            part.translation_rate = _parse_float(self.trans_rate_edit.text())
            part.degradation_rate = _parse_float(self.deg_rate_edit.text())
            part.product = self.product_edit.text()
        elif isinstance(part, Terminator):
            part.termination_efficiency = _parse_float(self.term_eff_edit.text())
        elif isinstance(part, RBS):
            part.translation_initiation_rate = _parse_float(
                self.rbs_init_rate_edit.text()
            )

        self.part_saved.emit(part)

    def _on_sequence_changed(self):
        """Auto-trigger parameter prediction if in New Theoretical Part mode
        with a sequence.
        """
        if self.current_part is None or getattr(self.current_part, "is_custom", True):
            seq = self.seq_edit.toPlainText().strip()
            if len(seq) >= 10:
                self._run_prediction()

    def _run_prediction(self):
        """Run k-NN parameter prediction based on the sequence input."""
        seq = self.seq_edit.toPlainText().strip()
        if not seq:
            self.prediction_status_lbl.setVisible(False)
            return

        part_type = self.type_combo.currentText().lower()

        if self.catalogue_service:
            result = self.catalogue_service.predict_part_parameters(
                seq, part_type=part_type, k=3
            )
            # Fallback directly to SequencePredictor using default repo candidates
            from karcytics_plugins.synthetic_biology.analysis.prediction \
                import sequence_predictor as sp
            from karcytics_plugins.synthetic_biology.analysis.api.kinetics import (
                CelloKineticsDatabase,
            )

            SequencePredictor = sp.SequencePredictor

            CelloKineticsDatabase.get_parameters("AmtR")

            # Load candidate parts
            candidate_parts = []
            classic_params = CelloKineticsDatabase._classic_params
            for pid, params in classic_params.items():
                if "y_max" in params:
                    candidate_parts.append(
                        Promoter(
                            id=pid,
                            name=pid,
                            sequence=params.get("sequence", ""),
                            y_max=params.get("y_max"),
                            y_min=params.get("y_min"),
                            K_d=params.get("K_d"),
                            n=params.get("n"),
                        )
                    )
            result = SequencePredictor.predict(
                seq, candidate_parts, part_type=part_type, k=3
            )

        if not result.get("is_predicted"):
            self.prediction_status_lbl.setText(
                "Prediction unavailable for this sequence."
            )
            self.prediction_status_lbl.setVisible(True)
            return

        params = result.get("parameters", {})
        if part_type == "promoter":
            if params.get("K_d") is not None:
                self.kd_edit.setText(str(params["K_d"]))
            if params.get("y_max") is not None:
                self.ymax_edit.setText(str(params["y_max"]))
            if params.get("y_min") is not None:
                self.ymin_edit.setText(str(params["y_min"]))
            if params.get("n") is not None:
                self.n_edit.setText(str(params["n"]))
        elif part_type == "cds":
            if params.get("translation_rate") is not None:
                self.trans_rate_edit.setText(str(params["translation_rate"]))
            if params.get("degradation_rate") is not None:
                self.deg_rate_edit.setText(str(params["degradation_rate"]))

        top_id = result.get("top_match_id", "N/A")
        top_dist = result.get("top_match_distance", "N/A")
        k_used = result.get("k_neighbors_used", 3)
        status_msg = result.get("status_message")
        model_type = str(result.get("model_type", "")).lower()

        if status_msg:
            self.prediction_status_lbl.setText(status_msg)
        else:
            self.prediction_status_lbl.setText(
                f"⚡ [Predicted via {k_used}-NN] Top match: {top_id} "
                f"(distance: {top_dist})"
            )
        self.prediction_status_lbl.setVisible(True)

        # Inject Educational Copy based on prediction model used
        self._active_model_type = model_type
        learn_more_link = (
            "<br><a href='learn_more' style='color: #00bcd4; font-weight: bold; "
            "text-decoration: underline;'>Click here to learn more.</a>"
        )

        if "thermodynamic pwm" in model_type:
            info_text = (
                "⚙️ <b>How this works (The Physics Engine):</b> Imagine this DNA is an "
                "'ON' switch for a factory, and a microscopic worker needs to grab two "
                "specific handles to turn it on. This model physically measures those "
                f"handles.{learn_more_link}"
            )
        elif "cai" in model_type or "blosum62" in model_type:
            info_text = (
                "🧱 <b>How this works (The 3D Lego Model):</b> This DNA is an "
                "instruction manual to build a 3D protein structure. This model "
                "checks translation speed and structural folding stability."
                f"{learn_more_link}"
            )
        else:
            info_text = (
                "🔍 <b>How this works (The Spellchecker):</b> This model acts like a "
                "smart spellchecker. It compares your sequence to a library of known "
                f"parts using string edit distance.{learn_more_link}"
            )

        self.prediction_info_card.setText(info_text)
        self.prediction_info_card.setVisible(True)

    def _on_delete(self):
        """Handle part deletion with UI confirmation popup."""
        if not self.current_part:
            return

        part_id = self.current_part.id
        part_name = getattr(self.current_part, "name", "") or part_id

        confirm = QMessageBox.question(
            self,
            "Confirm Part Deletion",
            f"Are you sure you want to delete the part '{part_name}'? "
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm == QMessageBox.StandardButton.Yes:
            if self.catalogue_service:
                self.catalogue_service.delete_part(part_id)
            self.part_deleted.emit(part_id)

    def _open_model_details_dialog(self, link_str: str = ""):
        """Open the detailed mathematical & biological model breakdown popup dialog."""
        model_key = getattr(self, "_active_model_type", "knn")
        dialog = ModelDetailsDialog(model_key=model_key, parent=self)
        dialog.exec()

    def _on_graph_wt_vs_mutation(self):
        """Trigger wild type lookup, dual parameter extraction, and comparative
        graphing.
        """
        seq = self.seq_edit.toPlainText().strip()
        if not seq:
            QMessageBox.warning(
                self,
                "Missing Sequence",
                "Please enter a DNA sequence before generating the comparative graph.",
            )
            return

        part_type = self.type_combo.currentText().lower()

        # Load candidate parts database
        candidate_parts = []
        if self.catalogue_service:
            candidate_parts = self.catalogue_service.get_all_parts()
        else:
            from karcytics_plugins.synthetic_biology.analysis.api.kinetics import (
                CelloKineticsDatabase,
            )

            CelloKineticsDatabase.get_parameters("AmtR")
            classic_params = CelloKineticsDatabase._classic_params
            for pid, params in classic_params.items():
                if "y_max" in params:
                    candidate_parts.append(
                        Promoter(
                            id=pid,
                            name=pid,
                            sequence=params.get("sequence", ""),
                            y_max=params.get("y_max"),
                            y_min=params.get("y_min"),
                            K_d=params.get("K_d"),
                            n=params.get("n"),
                        )
                    )
                elif "translation_rate" in params:
                    candidate_parts.append(
                        CDS(
                            id=pid,
                            name=pid,
                            sequence=params.get("sequence", ""),
                            translation_rate=params.get("translation_rate"),
                            degradation_rate=params.get("degradation_rate"),
                        )
                    )

        try:
            from karcytics_plugins.synthetic_biology.analysis.prediction \
                import graphing_utils as gu

            generate_transfer_curve = gu.generate_transfer_curve
            from karcytics_plugins.synthetic_biology.analysis.prediction \
                import sequence_predictor as sp  # noqa: E501

            compare_kinetics = sp.compare_kinetics

            comparison = compare_kinetics(seq, candidate_parts, part_type=part_type)

            wt_info = comparison["wildtype_info"]
            wt_params = comparison["wt_params"]
            mut_params = comparison["mut_params"]
            effective_type = comparison["part_type"]

            wt_id = wt_info.get("id", "WT Baseline")
            dist = wt_info.get("distance", "N/A")
            plot_title = (
                f"WT Baseline: {wt_id} (Levenshtein Dist: {dist}) vs Mutated Sequence"
            )

            fig = generate_transfer_curve(
                wt_params=wt_params,
                mut_params=mut_params,
                part_type=effective_type,
                title=plot_title,
            )

            dialog = WTGraphDialog(fig, parent=self)
            dialog.exec()

        except Exception as e:
            QMessageBox.warning(
                self,
                "Wild Type Reverse Lookup Error",
                f"Failed to generate comparative graph:\n{str(e)}",
            )

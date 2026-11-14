"""Primary PySide6 Plasmid & Vector Assembly View (Benchling-grade visual design
view).

Includes a drag-and-drop Part Palette, Assembly Canvas / Vector drop-zone,
interactive sequence feature viewer, file importer (FASTA/GenBank), and
automated primer designer. Decoupled from engines via PlasmidAssemblyController
signals & slots.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from karcytics_sdk.plugin.citation_widgets import CitationLabel
from karcytics_sdk.plugin.components import (
    BioCaptionLabel,
    BioComboBox,
    BioDoubleSpinBox,
    BioLineEdit,
    BioListWidget,
    BioSpinBox,
    BioSplitter,
    BioStatusLabel,
    BioTableWidget,
    BioToggleButton,
    PrimaryButton,
    SecondaryButton,
    WorkspaceSaveButton,
)
from karcytics_sdk.plugin.dialogs import get_save_path, show_error, show_warning
from karcytics_sdk.plugin.theme_fallback import Colors, theme_manager
from karcytics_sdk.plugin.toast import show_toast
from PySide6.QtCore import QMimeData, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QBrush, QColor, QDrag
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidgetItem,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...analysis import citations
from ...analysis.assembly import gel as gel_engine
from ...analysis.assembly import primer_export
from ...analysis.assembly import restriction as rst
from ...analysis.assembly.primer_rubric import PrimerRubric
from ...analysis.citations import FEATURE_CITATIONS
from ...analysis.models.domain import PlasmidVector
from ...analysis.parts.base import BiologicalPart
from ...analysis.parts.components import CDS, RBS, Promoter, Terminator, part_from_dict
from ...analysis.sequence_input import (
    SequenceRejectedError,
    clean_sequence,
    validate_region,
)
from ...analysis.state import SynBioState
from ...ui.controllers.plasmid_controller import PlasmidAssemblyController
from ..widgets.amplification_track import AmplificationTrack
from ..widgets.bio_tab_widget import BioTabWidget
from ..widgets.flow_layout import FlowLayout
from ..widgets.gel_view import GelView
from ..widgets.rubric_panel import RubricPanel
from ..workers import AmplificationWorker, InternalSiteWorker, PrimerCandidateWorker

logger = logging.getLogger(__name__)

#: How long to wait after the last keystroke before resolving a tail to an
#: enzyme. Typing 'GAATTC' used to spawn a worker per resolving keystroke.
_TAIL_DEBOUNCE_MS = 250

#: Shown on the Amplification and Gel tabs until a candidate is chosen.
#: The coverage switch states, written so the label always says which is live.
_COVERAGE_OFF = "Trimming allowed \u2014 click to keep the whole target"
_COVERAGE_ON = "\u2713 Keeping the whole target (no trimming)"

_SELECT_HINT = (
    "Design primers, then select a candidate in the Candidates tab to see "
    "its amplification and predicted gel."
)


class PartPaletteWidget(BioListWidget):
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


class AssemblyCanvasWidget(BioListWidget):
    """Drop zone for assembly order placement."""

    parts_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-synbio-part") or event.source() == self:
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-synbio-part"):
            data_bytes = event.mimeData().data("application/x-synbio-part")
            part_dict = json.loads(bytes(data_bytes).decode("utf-8"))

            item = QListWidgetItem(f"🧩 {part_dict['name']} [{part_dict['part_type'].upper()}]")
            item.setData(Qt.ItemDataRole.UserRole, part_dict)
            self.addItem(item)
            event.acceptProposedAction()
            self.parts_changed.emit()
        else:
            super().dropEvent(event)
            self.parts_changed.emit()


class PrimerDesignDialog(QDialog):
    """Primer design, amplification and the gel that follows, for one target.

    This dialog orchestrates; it does not calculate. Candidate ranking, rubric
    verdicts, binding sites, digests and band positions all come from
    ``analysis/``, and every long step runs on a worker. The three panels below
    render what those engines return.
    """

    def __init__(self, target_sequence: str, controller: PlasmidAssemblyController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.target_sequence = target_sequence or ""
        self.setWindowTitle("Primer Design & Amplification")
        self.setMinimumSize(1040, 760)

        self._candidates: list[dict] = []
        # Held as attributes so Qt does not collect a thread mid-run.
        self._worker: PrimerCandidateWorker | None = None
        self._amp_worker: AmplificationWorker | None = None
        self._site_worker: InternalSiteWorker | None = None
        self._methods_dialog: Any = None
        self._last_rubric = PrimerRubric()
        # Monotonic request ids. A worker's result is discarded unless it is
        # still the newest request of its kind: typing a tail or arrow-keying
        # the candidate table used to let a slow earlier result land after a
        # newer one and overwrite it.
        self._site_request = 0
        self._design_request = 0
        self._amp_request = 0
        self._tail_debounce = QTimer(self)
        self._tail_debounce.setSingleShot(True)
        self._tail_debounce.setInterval(_TAIL_DEBOUNCE_MS)
        self._tail_debounce.timeout.connect(self._refresh_tail_enzymes)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_inputs())

        self.tabs = BioTabWidget()
        self.tabs.addTab(self._build_candidates_tab(), "Candidates")
        self.tabs.addTab(self._build_amplification_tab(), "Amplification")
        self.tabs.addTab(self._build_gel_tab(), "Gel")
        # The results take every pixel the inputs do not need. Without this
        # the fixed-height input form absorbed the slack and the tables and
        # the gel were squeezed into ~95 px, which put 16 ladder labels on
        # top of each other.
        layout.addWidget(self.tabs, stretch=1)

        layout.addWidget(self._build_footer())

        self.status = BioStatusLabel("")
        layout.addWidget(self.status)

        self._refresh_tail_enzymes()

    def _build_footer(self) -> QWidget:
        """Save / Methods & References / Export, which this dialog had none of.

        The main panel carries these once globally, but a modal dialog is
        where the primer work actually happens, so a student had no way to
        save a design or see what produced its numbers without closing it.
        """
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)

        self.btn_methods = SecondaryButton("Methods && References")
        self.btn_methods.clicked.connect(self._open_methods)
        row.addWidget(self.btn_methods)

        self.btn_export = SecondaryButton("Export primers\u2026")
        self.btn_export.clicked.connect(self._export)
        self.btn_export.setEnabled(False)
        row.addWidget(self.btn_export)

        self.btn_copy = SecondaryButton("Copy forward primer")
        self.btn_copy.clicked.connect(self._copy_selected)
        self.btn_copy.setEnabled(False)
        row.addWidget(self.btn_copy)

        row.addStretch()

        self.save_button = WorkspaceSaveButton(bar)
        self.save_button.clicked.connect(self._save_workspace)
        row.addWidget(self.save_button)
        return bar

    def _selected_candidate(self) -> dict | None:
        row = self.candidate_table.currentRow()
        return self._candidates[row] if 0 <= row < len(self._candidates) else None

    def _export(self) -> None:
        """Write the submission: primers, rubric checks and the methods text."""
        candidate = self._selected_candidate()
        if candidate is None:
            show_warning(
                self,
                title="Nothing to export",
                message="Select a candidate in the Candidates tab first.",
            )
            return

        path = get_save_path(
            self,
            title="Export primer design",
            file_filter="CSV (*.csv);;FASTA (*.fasta)",
        )
        if not path:
            return

        state = getattr(self.controller, "state", None)
        methods = (
            citations.methods_text(state.data.methods_log)
            if state is not None and state.data.methods_log
            else ""
        )
        fwd_enz, rev_enz = self._tail_enzymes()
        # One enzyme name per primer, in forward/reverse order, blank if the
        # tail does not resolve to one.
        enzyme_names = [fwd_enz[0] if fwd_enz else "", rev_enz[0] if rev_enz else ""]
        try:
            if str(path).lower().endswith((".fasta", ".fa")):
                payload = primer_export.to_fasta(candidate)
            else:
                payload = primer_export.to_csv(
                    candidate,
                    methods=methods,
                    tail_enzymes=enzyme_names,
                    rubric_name=getattr(self._last_rubric, "name", ""),
                )
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(payload)
        except OSError as exc:
            logger.warning("Primer export failed: %s", exc)
            show_warning(self, title="Export failed", message=str(exc))
            return
        show_toast(f"Exported to {path}")

    def _copy_selected(self) -> None:
        """Put the forward primer on the clipboard, ready for an order form."""
        candidate = self._selected_candidate()
        if candidate is None:
            return
        text = primer_export.clipboard_text(candidate["forward"])
        QApplication.clipboard().setText(text)
        show_toast("Forward primer copied.")

    def _open_methods(self) -> None:
        """Show the same Methods & References dialog the main panel uses."""
        from ..wizards.methods_dialog import MethodsReferencesDialog

        state = getattr(self.controller, "state", None)
        if state is None:
            show_warning(
                self,
                title="Methods unavailable",
                message="This dialog is not attached to a workspace.",
            )
            return
        if self._methods_dialog is None:
            self._methods_dialog = MethodsReferencesDialog(state, self)
        self._methods_dialog.refresh()
        self._methods_dialog.show()
        self._methods_dialog.raise_()

    def _save_workspace(self) -> None:
        panel = self.parent()
        saver = getattr(panel, "save_workflow", None) or getattr(panel, "_on_save", None)
        if callable(saver):
            saver()
            show_toast("Design saved to the workspace.")
        else:
            show_warning(
                self,
                title="Save unavailable",
                message="This dialog is not attached to a workspace that can be saved.",
            )

    # ── Inputs ─────────────────────────────────────────────────────────

    def _build_inputs(self) -> QWidget:
        box = QWidget()
        column = QVBoxLayout(box)
        form = QFormLayout()

        self.feature_combo = BioComboBox()
        self.feature_combo.addItem("Whole target sequence", userData=None)
        for name, begin, finish in self._annotated_features():
            self.feature_combo.addItem(f"{name} ({begin}-{finish})", userData=(begin, finish))
        self.feature_combo.currentIndexChanged.connect(self._on_region_changed)
        form.addRow("Amplify:", self.feature_combo)

        coords = QWidget()
        coord_row = QHBoxLayout(coords)
        coord_row.setContentsMargins(0, 0, 0, 0)
        self.start_spin = BioSpinBox()
        self.start_spin.setRange(0, max(len(self.target_sequence), 1))
        self.end_spin = BioSpinBox()
        self.end_spin.setRange(0, max(len(self.target_sequence), 1))
        self.end_spin.setValue(len(self.target_sequence))
        for widget in (self.start_spin, self.end_spin):
            widget.valueChanged.connect(self._on_coords_changed)
        coord_row.addWidget(QLabel("from"))
        coord_row.addWidget(self.start_spin)
        coord_row.addWidget(QLabel("to"))
        coord_row.addWidget(self.end_spin)
        coord_row.addStretch()
        form.addRow("Coordinates:", coords)

        self.tm_spin = BioDoubleSpinBox()
        self.tm_spin.setRange(45.0, 75.0)
        self.tm_spin.setValue(60.0)
        form.addRow("Target Tm (\u00b0C):", self.tm_spin)

        self.fwd_overhang_edit, self.fwd_enzyme_label, fwd_row = self._build_tail_row("GAATTC")
        form.addRow("Forward 5' tail:", fwd_row)

        self.rev_overhang_edit, self.rev_enzyme_label, rev_row = self._build_tail_row("AAGCTT")
        form.addRow("Reverse 5' tail:", rev_row)

        self.full_target_toggle = BioToggleButton(_COVERAGE_OFF)
        self.full_target_toggle.setCheckable(True)
        # The label used to read "Keep the whole target (no trimming)" whether
        # the toggle was on or off, so it looked like a statement of current
        # behaviour. It is an OFF switch by default, and a user who read it as
        # fact got a trimmed product and no warning.
        self.full_target_toggle.toggled.connect(self._on_coverage_toggled)
        form.addRow("Coverage:", self.full_target_toggle)

        column.addLayout(form)

        self.input_note = self._add_caption(column)
        self.input_problem = self._add_caption(column, colour=Colors.ACCENT_DANGER)
        self.internal_site_warning = self._add_caption(column, colour=Colors.ACCENT_DANGER)

        column.addWidget(self._build_run_row())
        return box

    def _on_coverage_toggled(self, checked: bool) -> None:
        """Say which way the switch is set, and drop results from the other way."""
        self.full_target_toggle.setText(_COVERAGE_ON if checked else _COVERAGE_OFF)
        if self._candidates:
            self._invalidate_candidates(
                "Coverage changed. Press Design Primers to rank candidates again."
            )

    def _build_run_row(self) -> QWidget:
        """The Design button and the cancel that long runs need."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_design = PrimaryButton("Design Primers")
        self.btn_design.clicked.connect(self._on_design_clicked)
        layout.addWidget(self.btn_design)

        self.btn_cancel = SecondaryButton("Cancel")
        self.btn_cancel.clicked.connect(self._on_cancel)
        self.btn_cancel.setVisible(False)
        layout.addWidget(self.btn_cancel)
        return row

    @staticmethod
    def _add_caption(column: Any, colour: str = "") -> Any:
        """A wrapped caption row that stays hidden until it has something to say."""
        label = BioCaptionLabel("")
        label.setWordWrap(True)
        label.setVisible(False)
        if colour:
            label.setStyleSheet(f"color: {colour};")
        column.addWidget(label)
        return label

    @staticmethod
    def _set_caption(label: Any, text: str) -> None:
        """Set a caption and hide it when empty.

        An empty label still reserves a row, and three of them stacked above
        the Design button cost ~70 px of blank space that the results needed.
        """
        label.setText(text)
        label.setVisible(bool(text))

    def _build_tail_row(self, example: str) -> tuple:
        """A tail entry box plus the enzyme name the digest engine resolves it to."""
        edit = BioLineEdit()
        edit.setPlaceholderText(f"e.g. {example}")
        edit.textChanged.connect(self._on_tail_edited)

        name = BioCaptionLabel("")
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit)
        layout.addWidget(name)
        return edit, name, row

    def _annotated_features(self) -> list:
        """Features offered for selection, read off the construct's vector."""
        vector = getattr(getattr(self.controller, "state", None), "active_vector", None)
        features = []
        for feature in getattr(vector, "features", ()) or ():
            name = getattr(feature, "name", "") or getattr(feature, "label", "")
            begin = getattr(feature, "start", None)
            finish = getattr(feature, "end", None)
            if name and isinstance(begin, int) and isinstance(finish, int):
                features.append((name, begin, finish))
        return features

    def _region(self) -> tuple[int, int]:
        """The selected span, or (0, len) when nothing narrower is valid.

        Validity is decided by the analysis layer, not here — see
        :func:`analysis.sequence_input.validate_region`.
        """
        selection = self._validated_region()
        if not selection.ok:
            return 0, len(self.target_sequence)
        return selection.start, selection.end

    def _validated_region(self):
        """Run the engine's coordinate check over the current spin values."""
        return validate_region(
            self.start_spin.value(), self.end_spin.value(), len(self.target_sequence)
        )

    def _selected_sequence(self) -> str:
        begin, finish = self._region()
        return self.target_sequence[begin:finish]

    def _on_region_changed(self) -> None:
        span = self.feature_combo.currentData()
        if span:
            self.start_spin.setValue(span[0])
            self.end_spin.setValue(span[1])
        else:
            # "Whole target sequence" must mean it. Re-selecting it used to
            # leave whatever coordinates the previous feature had set.
            self.start_spin.setValue(0)
            self.end_spin.setValue(len(self.target_sequence))

    def _on_coords_changed(self) -> None:
        self._refresh_tail_enzymes()

    # ── Tails and the internal-site warning ────────────────────────────

    def _resolve_tail(self, text: str, label: str) -> tuple[tuple[str, ...], str]:
        """Enzymes a tail resolves to, and why it cannot be used if it cannot.

        Never raises, and that is the whole point. The digest engine validates
        its input and raises ``SequenceRejectedError`` on anything that is not
        ACGT, while this runs from a keystroke-debounce slot. An exception
        escaping here unwinds into PySide6 with no Python frame left to catch
        it, the daemon's excepthook calls ``sys.exit(1)``, and the entire
        plugin process dies with its traceback on stderr where no log file
        sees it. Typing a single ``q`` into a tail box killed the application
        that way, about 250 ms after the keystroke.
        """
        if not text:
            return (), ""
        cleaned = clean_sequence(text, label=label)
        if not cleaned.ok:
            return (), cleaned.summary()
        try:
            return rst.enzymes_for_tail(cleaned.sequence), ""
        except SequenceRejectedError as exc:
            # Belt and braces: the engine owns the rules, so a tail it refuses
            # for a reason ``clean_sequence`` does not model is still reported
            # rather than raised.
            logger.debug("Tail %r refused by the digest engine: %s", text, exc)
            return (), str(exc)

    def _tail_enzymes(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Enzyme names for each tail, named by the digest engine."""
        fwd, _ = self._resolve_tail(self.fwd_overhang_edit.text().strip(), "Forward 5' tail")
        rev, _ = self._resolve_tail(self.rev_overhang_edit.text().strip(), "Reverse 5' tail")
        return fwd, rev

    def _tail_problems(self) -> tuple[str, str]:
        """Why each tail cannot be used; an empty string when it can."""
        _, fwd = self._resolve_tail(self.fwd_overhang_edit.text().strip(), "Forward 5' tail")
        _, rev = self._resolve_tail(self.rev_overhang_edit.text().strip(), "Reverse 5' tail")
        return fwd, rev

    def _on_tail_edited(self) -> None:
        """Coalesce keystrokes, and never leave results from an older tail up.

        Designing with GAATTC and then typing AAGCTT used to leave the old
        primers in the table while the enzyme used for site annotation had
        already changed, so the two disagreed on screen.
        """
        self._tail_debounce.start()
        if self._candidates:
            self._invalidate_candidates(
                "Tails changed. Press Design Primers to rank candidates for the new tails."
            )

    def _invalidate_candidates(self, reason: str) -> None:
        """Drop results computed against inputs that are no longer on screen."""
        self._candidates = []
        self._design_request += 1
        self._amp_request += 1
        self.candidate_table.setRowCount(0)
        self.btn_export.setEnabled(False)
        self.btn_copy.setEnabled(False)
        self.rubric_panel.clear()
        self.amplification_track.clear()
        self.gel_view.clear()
        self.amplification_hint.setVisible(True)
        self.gel_hint.setVisible(True)
        self.status.setText(reason)

    def _refresh_tail_enzymes(self) -> None:
        fwd, rev = self._tail_enzymes()
        fwd_problem, rev_problem = self._tail_problems()

        # The refusal takes the enzyme name's place: the student needs to see
        # why the tail they typed resolved to nothing, next to the box they
        # typed it in.
        self._set_caption(self.fwd_enzyme_label, fwd_problem or (f"\u2192 {fwd[0]}" if fwd else ""))
        self._set_caption(self.rev_enzyme_label, rev_problem or (f"\u2192 {rev[0]}" if rev else ""))

        chosen = tuple(dict.fromkeys([n for n in (fwd[:1] + rev[:1]) if n]))
        if not chosen or not self._selected_sequence():
            self._set_caption(self.internal_site_warning, "")
            return

        self._site_request += 1
        request = self._site_request
        self._site_worker = InternalSiteWorker(
            sequence=self._selected_sequence(), enzymes=chosen, parent=self
        )
        self._site_worker.sites_ready.connect(
            lambda payload, r=request: self._on_internal_sites(payload, r)
        )
        self._site_worker.error_occurred.connect(self._on_worker_error)
        self._site_worker.start()

    def _on_internal_sites(self, payload: dict, request: int = 0) -> None:
        if request and request != self._site_request:
            return  # superseded by a newer tail
        sites = payload.get("sites", ())
        if not sites:
            self._set_caption(self.internal_site_warning, "")
            return
        cutters = sorted({site.enzyme for site in sites})
        self._set_caption(
            self.internal_site_warning,
            f"{', '.join(cutters)} also cuts inside the region you are amplifying "
            f"({len(sites)} site(s)). Digesting the product with it would destroy "
            "the insert \u2014 choose a different tail enzyme.",
        )

    # ── Tabs ───────────────────────────────────────────────────────────

    def _build_candidates_tab(self) -> QWidget:
        page = QWidget()
        column = QVBoxLayout(page)

        self.candidate_table = BioTableWidget()
        headers = (
            "#",
            "Score",
            "Forward",
            "Fwd Tm",
            "Fwd GC%",
            "Reverse",
            "Rev Tm",
            "Rev GC%",
            "Product",
            "Verdict",
        )
        self.candidate_table.setColumnCount(len(headers))
        self.candidate_table.setHorizontalHeaderLabels(list(headers))
        self.candidate_table.setEditTriggers(BioTableWidget.EditTrigger.NoEditTriggers)
        self.candidate_table.setSelectionBehavior(BioTableWidget.SelectionBehavior.SelectRows)
        self.candidate_table.itemSelectionChanged.connect(self._on_candidate_selected)
        column.addWidget(self.candidate_table, stretch=3)

        column.addWidget(
            BioCaptionLabel(
                "Tm and GC are for the annealing region only; a 5' tail does not anneal "
                "on the first cycle but is carried into the product."
            )
        )

        self.rubric_panel = RubricPanel()
        column.addWidget(self.rubric_panel, stretch=4)
        column.addWidget(
            CitationLabel("Screening", FEATURE_CITATIONS["primer_screen"], prefix="Based on")
        )
        return page

    def _build_amplification_tab(self) -> QWidget:
        page = QWidget()
        column = QVBoxLayout(page)
        self.amplification_hint = BioCaptionLabel(_SELECT_HINT)
        self.amplification_hint.setWordWrap(True)
        column.addWidget(self.amplification_hint)

        self.amplification_track = AmplificationTrack()
        column.addWidget(self.amplification_track, stretch=1)
        column.addWidget(
            CitationLabel("Amplification", FEATURE_CITATIONS["amplification"], prefix="Based on")
        )
        return page

    def _build_gel_tab(self) -> QWidget:
        page = QWidget()
        column = QVBoxLayout(page)
        self.gel_hint = BioCaptionLabel(_SELECT_HINT)
        self.gel_hint.setWordWrap(True)
        column.addWidget(self.gel_hint)

        controls = QWidget()
        control_row = QHBoxLayout(controls)
        control_row.setContentsMargins(0, 0, 0, 0)

        control_row.addWidget(QLabel("Ladder:"))
        self.ladder_combo = BioComboBox()
        for key, ladder in gel_engine.LADDERS.items():
            self.ladder_combo.addItem(ladder.name, userData=key)
        self.ladder_combo.setCurrentIndex(max(list(gel_engine.LADDERS).index("1kb_plus"), 0))
        self.ladder_combo.currentIndexChanged.connect(self._rerun_amplification)
        control_row.addWidget(self.ladder_combo)

        control_row.addWidget(QLabel("Agarose:"))
        self.agarose_combo = BioComboBox()
        for percentage in gel_engine.AGAROSE_WINDOWS:
            self.agarose_combo.addItem(percentage, userData=percentage)
        self.agarose_combo.setCurrentText(gel_engine.DEFAULT_AGAROSE)
        self.agarose_combo.currentIndexChanged.connect(self._rerun_amplification)
        control_row.addWidget(self.agarose_combo)
        control_row.addStretch()
        column.addWidget(controls)

        self.gel_view = GelView()
        column.addWidget(self.gel_view, stretch=1)
        return page

    def _rerun_amplification(self) -> None:
        """Re-run with the current gel settings, if a candidate is selected."""
        candidate = self._selected_candidate()
        if candidate is not None:
            self._run_amplification(candidate)

    # ── Running ────────────────────────────────────────────────────────

    def _on_design_clicked(self) -> None:
        # An inverted or empty range used to fall through to the whole
        # template, so a mistyped coordinate silently amplified everything.
        selection = self._validated_region()
        if not selection.ok:
            self._show_problem(selection.summary())
            return

        cleaned = clean_sequence(self._selected_sequence(), label="Target sequence")
        if not cleaned.ok:
            self._show_problem(cleaned.summary())
            return

        # A tail the engine cannot read stops the run. Designing without it
        # would hand back primers that lack the tail the student typed, and a
        # silently dropped restriction site is exactly the confidently-wrong
        # answer this workflow exists to prevent.
        tail_problems = [problem for problem in self._tail_problems() if problem]
        if tail_problems:
            self._show_problem(" ".join(tail_problems))
            return
        # Say what was changed rather than changing it behind their back, and
        # keep saying it: the status line is overwritten the moment the run
        # finishes, so the note gets a label of its own.
        self._set_caption(self.input_note, " ".join(cleaned.transformations))

        sequence = cleaned.sequence

        self._set_caption(self.input_problem, "")
        self._set_running(True)
        self._design_request += 1
        request = self._design_request
        self.status.setText("Ranking candidates\u2026")
        fwd, rev = self._tail_enzymes()

        self._worker = PrimerCandidateWorker(
            target_sequence=sequence,
            target_tm=self.tm_spin.value(),
            fwd_overhang=self.fwd_overhang_edit.text().strip(),
            rev_overhang=self.rev_overhang_edit.text().strip(),
            require_full_target=self.full_target_toggle.isChecked(),
            parent=self,
        )
        self._worker.candidates_ready.connect(
            lambda found, r=request: self._on_candidates(found, r)
        )
        self._worker.error_occurred.connect(self._on_worker_error)
        self._worker.start()

    def _show_problem(self, message: str) -> None:
        """Report a refusal from the analysis layer, in its own words."""
        self._set_caption(self.input_note, "")
        self.status.setText(message)
        self._set_caption(self.input_problem, message)
        show_warning(self, title="Cannot design primers", message=message)

    def _set_running(self, running: bool) -> None:
        """Show that work is in flight, and offer a way out of it."""
        self.btn_design.setEnabled(not running)
        self.btn_design.setText("Ranking\u2026" if running else "Design Primers")
        self.btn_cancel.setVisible(running)

    def _on_cancel(self) -> None:
        """Abandon the in-flight run: bump the generation so its result is dropped."""
        self._design_request += 1
        self._amp_request += 1
        self._set_running(False)
        self.status.setText("Cancelled.")

    def _on_worker_error(self, message: str) -> None:
        self._set_running(False)
        self.status.setText(message)
        show_warning(self, title="Primer design failed", message=message)

    def _on_candidates(self, candidates: list, request: int = 0) -> None:
        if request and request != self._design_request:
            return  # a newer design run has already started
        self._set_running(False)
        self._candidates = list(candidates or [])
        self._last_rubric = PrimerRubric()
        self._fill_candidate_table()
        if not self._candidates:
            self.status.setText("No candidate primers could be generated for this region.")
            self.rubric_panel.clear()
            return
        self.status.setText(f"{len(self._candidates)} candidates ranked.")
        self.candidate_table.selectRow(0)

    def _fill_candidate_table(self) -> None:
        self.candidate_table.setRowCount(len(self._candidates))
        for row, candidate in enumerate(self._candidates):
            fwd, rev = candidate["forward"], candidate["reverse"]
            verdict = candidate["summary"]["verdict"]
            cells = (
                str(row + 1),
                f"{candidate['score']:.0f}",
                fwd.sequence,
                f"{fwd.calculated_tm:.1f}",
                f"{fwd.gc_content:.1f}",
                rev.sequence,
                f"{rev.calculated_tm:.1f}",
                f"{rev.gc_content:.1f}",
                f"{candidate['product_bp']} bp",
                verdict.upper(),
            )
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if column == len(cells) - 1:
                    item.setForeground(
                        QBrush(QColor(_VERDICT_COLOUR.get(verdict, Colors.FG_PRIMARY)))
                    )
                self.candidate_table.setItem(row, column, item)
        self.candidate_table.resizeColumnsToContents()

    def _on_candidate_selected(self) -> None:
        row = self.candidate_table.currentRow()
        if not (0 <= row < len(self._candidates)):
            return
        candidate = self._candidates[row]
        # The engine says when the best pair could not sit on the target ends.
        self._set_caption(self.input_problem, candidate.get("coverage_note", ""))
        self.btn_export.setEnabled(True)
        self.btn_copy.setEnabled(True)
        self.rubric_panel.show_candidate(candidate["checks"], candidate["summary"])
        # Record the design and screening that produced the pair now on screen.
        self._record(
            lambda: self.controller.record_primer_design(
                candidate, self._last_rubric, len(self._candidates)
            )
        )
        self._run_amplification(candidate)

    def _run_amplification(self, candidate: dict) -> None:
        fwd, rev = candidate["forward"], candidate["reverse"]
        fwd_enz, rev_enz = self._tail_enzymes()
        enzymes = tuple(dict.fromkeys([n for n in (fwd_enz[:1] + rev_enz[:1]) if n]))

        self._amp_worker = AmplificationWorker(
            template=self.target_sequence,
            forward_primer=fwd.sequence,
            reverse_primer=rev.sequence,
            forward_tail=fwd.overhang or "",
            reverse_tail=rev.overhang or "",
            enzymes=enzymes,
            ladder=self.ladder_combo.currentData() or "1kb_plus",
            agarose=self.agarose_combo.currentData() or gel_engine.DEFAULT_AGAROSE,
            parent=self,
        )
        self._amp_request += 1
        request = self._amp_request
        self._amp_worker.amplification_ready.connect(
            lambda payload, r=request: self._on_amplification(payload, r)
        )
        self._amp_worker.error_occurred.connect(self._on_worker_error)
        self._amp_worker.start()

    def _on_amplification(self, payload: dict, request: int = 0) -> None:
        if request and request != self._amp_request:
            return  # a different candidate is selected now
        self.amplification_hint.setVisible(False)
        self.gel_hint.setVisible(False)
        self.amplification_track.show_result(payload["result"], payload["template_bp"])
        self._record(lambda: self.controller.record_amplification(payload["result"]))

        digest = payload.get("digest")
        if digest is not None:
            self._record(lambda: self.controller.record_digest(digest))

        gel = payload.get("gel")
        if gel is not None:
            self.gel_view.show_gel(gel)
            self._record(lambda: self.controller.record_gel(gel))
        else:
            self.gel_view.clear()

    def _record(self, write: Any) -> None:
        """Write one methods entry, tolerating a controller that cannot.

        Tests and the demo pass stand-in controllers without a state object.
        A missing recorder must not take the results off the screen, but it
        must not pass silently either.
        """
        try:
            write()
        except AttributeError as exc:
            logger.warning("Could not record a methods entry: %s", exc)


#: Engine verdict -> theme token. The engine decides the verdict.
_VERDICT_COLOUR = {
    "pass": Colors.ACCENT_SUCCESS,
    "fail": Colors.ACCENT_DANGER,
    "incomplete": Colors.ACCENT_WARNING,
}


class PlasmidAssemblyView(QWidget):
    """PySide6 View for plasmid assembly, Drag-and-Drop part ordering, and Sequence
    viewer.
    """

    assembly_requested = Signal(str, list)
    file_parse_requested = Signal(str, str)

    def __init__(
        self,
        state: SynBioState,
        controller: PlasmidAssemblyController,
        parent=None,
        catalogue=None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.state = state
        self.controller = controller
        self.catalogue = catalogue

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

    def _init_ui(self):  # noqa: PLR0915
        self.setObjectName("plasmid_assembly_view")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        splitter = BioSplitter(Qt.Orientation.Horizontal)

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

        # Toolbar. A FlowLayout, not a QHBoxLayout: a single row's minimum width
        # is the sum of every control in it, and this panel sits in a three-way
        # splitter, so that sum became a floor under the whole plugin window —
        # one it could not be resized below, on a narrow display. Flowing wraps
        # the controls onto another row instead, leaving the minimum at the
        # widest single control. Button text is identical either way.
        toolbar = FlowLayout(margin=0, hSpacing=6, vSpacing=6)
        self.name_edit = BioLineEdit("pKarcytics_v1")
        # Without this the edit asks for a comfortable default width and puts
        # most of the row's minimum back.
        self.name_edit.setMinimumWidth(110)
        toolbar.addWidget(QLabel("Plasmid Name:"))
        toolbar.addWidget(self.name_edit)

        self.btn_import = SecondaryButton("📁 Import File")
        self.btn_import.clicked.connect(self._on_import_clicked)
        toolbar.addWidget(self.btn_import)

        self.btn_assemble = PrimaryButton("⚡ Assemble Construct")
        self.btn_assemble.clicked.connect(self._on_assemble_clicked)
        toolbar.addWidget(self.btn_assemble)

        self.btn_primer = SecondaryButton("🧬 Design Primers")
        self.btn_primer.clicked.connect(self._on_primer_clicked)
        toolbar.addWidget(self.btn_primer)

        center_layout.addLayout(toolbar)
        center_layout.addWidget(
            CitationLabel(
                "nearest-neighbour Tm with Mg2+ salt correction",
                FEATURE_CITATIONS["primer_design"],
                prefix="Primer design:",
                parent=self,
            )
        )

        lbl_canvas = QLabel("Drop Parts Below to Assemble Genetic Construct (Drag to Reorder):")
        lbl_canvas.setWordWrap(True)
        center_layout.addWidget(lbl_canvas)

        self.assembly_canvas = AssemblyCanvasWidget()
        center_layout.addWidget(self.assembly_canvas)

        splitter.addWidget(center_panel)

        # Right Panel: Feature Map & Sequence Output
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        lbl_map = QLabel("🗺️ Feature Map & Sequence Viewer")
        lbl_map.setWordWrap(True)
        lbl_map.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_layout.addWidget(lbl_map)

        self.feature_table = BioTableWidget()
        self.feature_table.setColumnCount(5)
        self.feature_table.setRowCount(0)
        self.feature_table.setHorizontalHeaderLabels(["Name", "Type", "Start", "End", "Strand"])
        if (hv := self.feature_table.horizontalHeader()) is not None:
            hv.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        right_layout.addWidget(self.feature_table)

        self.seq_display = QTextEdit()
        self.seq_display.setReadOnly(True)
        self.seq_display.setPlaceholderText("Assembled sequence display (FASTA / GenBank)...")
        self.seq_display.setStyleSheet("font-family: Menlo, Consolas, 'Courier New', monospace;")
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

    def reload_from_state(self) -> None:
        """Re-read the design parts and catalogue into the palette, and redraw the
        workspace's plasmid.

        The feature map used to be drawn only when an assembly finished in this
        session, so a plasmid that arrived through the shared state — from the
        demo, or from reopening a saved workflow — sat in the state while this
        tab showed an empty map.
        """
        self._populate_part_library()
        plasmid = self.state.get_active_plasmid() if self.state is not None else None
        if plasmid is not None and plasmid.sequence:
            self.render_plasmid(plasmid, announce=False)
        else:
            self.feature_table.setRowCount(0)
            self.seq_display.clear()

    def _populate_part_library(self):
        """Fill the palette from the design strand and the parts catalogue.

        Parts the user placed on the Design canvas come first, then everything
        in the catalogue. The hardcoded samples below are only a last resort
        for a session with no state and no catalogue.
        """
        self.part_palette.clear()

        library: list[BiologicalPart] = []
        seen: set[str] = set()

        for source in (
            self.state.design_parts if self.state is not None else [],
            self.catalogue.get_all_parts()
            if self.catalogue is not None and hasattr(self.catalogue, "get_all_parts")
            else [],
        ):
            for part in source:
                if part is None or part.id in seen:
                    continue
                seen.add(part.id)
                library.append(part)

        if library:
            for p in library:
                self._add_palette_item(p)
            return

        self._populate_sample_parts()

    def _add_palette_item(self, part: BiologicalPart) -> None:
        """Add one part to the palette, carrying its full serialized form.

        The whole ``to_dict`` goes on the item so assembly keeps the kinetic
        parameters instead of rebuilding a bare id/name/sequence part.
        """
        label = f"📌 {part.name} ({part.part_type.upper()})"
        if not part.sequence:
            label = f"⚠️ {part.name} ({part.part_type.upper()}) — no sequence"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, part.to_dict())
        if not part.sequence:
            item.setToolTip("This part has no DNA sequence and cannot be assembled.")
        self.part_palette.addItem(item)

    def _populate_sample_parts(self):
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
            self._add_palette_item(p)

    def _on_assemble_clicked(self):
        # Rebuild from the full serialized dict so kinetic parameters
        # (y_min/y_max/K_d/n/product/repressors) survive into the construct.
        parts: list[BiologicalPart] = []
        for i in range(self.assembly_canvas.count()):
            item = self.assembly_canvas.item(i)
            part = part_from_dict(item.data(Qt.ItemDataRole.UserRole))
            if part is not None:
                parts.append(part)

        missing = [p.name for p in parts if not p.sequence]
        if missing:
            show_warning(
                self,
                title="Missing Sequence",
                message=(
                    "These parts have no DNA sequence and cannot be assembled:\n"
                    + "\n".join(f"• {name}" for name in missing)
                ),
            )
            return

        if not parts:
            show_warning(
                self,
                title="Assembly Warning",
                message="Please drag at least one part into the canvas.",
            )
            return

        vector_name = self.name_edit.text().strip() or "pKarcytics_Vector"
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
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            fmt = "fasta" if file_path.endswith((".fa", ".fasta")) else "genbank"
            self.file_parse_requested.emit(content, fmt)
        except Exception as ex:
            self._show_error(f"Failed to read file: {str(ex)}")

    def _on_primer_clicked(self):
        plasmid = self.state.get_active_plasmid()
        if not plasmid or not plasmid.sequence:
            show_warning(
                self,
                title="Primer Warning",
                message="Assemble or import a plasmid vector first.",
            )
            return

        dlg = PrimerDesignDialog(
            target_sequence=plasmid.sequence, controller=self.controller, parent=self
        )
        dlg.exec()

    @Slot(PlasmidVector)
    def render_plasmid(self, vector: PlasmidVector, announce: bool = True):
        """Renders assembled or imported plasmid into feature map and sequence
        display.

        ``announce=False`` redraws without the "assembled" toast, for a plasmid
        restored from state rather than assembled just now.
        """
        self.name_edit.setText(vector.name)

        # Update feature table
        self.feature_table.setRowCount(0)
        for feat in vector.features:
            row = self.feature_table.rowCount()
            self.feature_table.insertRow(row)

            self.feature_table.setItem(row, 0, QTableWidgetItem(feat.name))
            self.feature_table.setItem(row, 1, QTableWidgetItem(feat.feature_type.upper()))
            self.feature_table.setItem(row, 2, QTableWidgetItem(str(feat.start)))
            self.feature_table.setItem(row, 3, QTableWidgetItem(str(feat.end)))
            self.feature_table.setItem(row, 4, QTableWidgetItem("+" if feat.strand >= 0 else "-"))

        # Update sequence text display
        topology_str = "Circular" if vector.is_circular else "Linear"
        header = f"> {vector.name} | {vector.length} bp | {topology_str}\n"
        formatted_seq = "\n".join(
            [vector.sequence[i : i + 60] for i in range(0, len(vector.sequence), 60)]
        )
        self.seq_display.setText(header + formatted_seq)
        if announce:
            show_toast("Plasmid construct assembled successfully")

    @Slot(str)
    def _show_error(self, message: str):
        show_error(self, title="Assembly Error", message=message)

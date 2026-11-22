"""Getting a sequence into the module, by every route a student actually has.

Before this, there was exactly one: the Import File button, which offered
``.gb``/``.gbk``/``.genbank``/``.fa``/``.fasta`` and decided the format from
the extension alone. Three things followed, all of them invisible rather than
loud:

* ``seq_display`` is read-only and ``clean_sequence`` was wired only into the
  primer dialog, so a construct held in an email or a lab manual could not be
  pasted at all.
* ``dragEnterEvent`` accepted only ``application/x-synbio-part``, so a file
  dragged from Finder was refused with no message of any kind.
* ``fmt = "fasta" if file_path.endswith((".fa", ".fasta")) else "genbank"``
  meant FASTA saved as ``.txt`` could not even be selected, and anything else
  was handed to the GenBank parser whatever it held.

All three now converge on one router, so the tests below assert the same two
properties of each route: the construct loads, and anything that happened to
it on the way in is visible afterwards.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from karcytics_plugins.synthetic_biology.analysis import sequence_format as sf
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
    PlasmidAssemblyController,
)
from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
    PlasmidAssemblyView,
    SequencePasteDialog,
)

from .sequence_fixtures import SYNTHETIC_ORF

# ── Fixtures ───────────────────────────────────────────────────────────

GENBANK_RECORD = """LOCUS       pKARC_TEST               120 bp    DNA     circular SYN 22-NOV-2026
DEFINITION  origin-wrap fixture.
ACCESSION   pKARC
VERSION     pKARC
KEYWORDS    .
SOURCE      synthetic construct
FEATURES             Location/Qualifiers
     CDS             11..40
                     /label="gfp_fragment"
ORIGIN
        1 acgtacgtac gtacgtacgt acgtacgtac gtacgtacgt acgtacgtac gtacgtacgt
       61 acgtacgtac gtacgtacgt acgtacgtac gtacgtacgt acgtacgtac gtacgtacgt
//
"""

FASTA_RECORD = f">pGFP-S12 green fluorescent protein\n{SYNTHETIC_ORF}\n"

#: Lower case, wrapped, with an RNA base — three things clean_sequence must
#: report rather than apply silently.
MESSY_RAW = "augagu aaagga\ngaagaacuu\n"


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app, qtbot=None):
    state = SynBioState()
    controller = PlasmidAssemblyController(state)
    widget = PlasmidAssemblyView(state, controller)
    yield widget
    controller.teardown()
    widget.deleteLater()


@pytest.fixture
def emitted(view, monkeypatch):
    """Capture what the view hands the controller, without running a worker."""
    calls: list[tuple[str, str]] = []
    view.file_parse_requested.connect(lambda text, fmt: calls.append((text, fmt)))
    return calls


@pytest.fixture
def errors(view, monkeypatch):
    shown: list[str] = []
    monkeypatch.setattr(view, "_show_error", shown.append)
    return shown


# ── Defect 3: the format comes from the content ────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "filename", "expected"),
    [
        (FASTA_RECORD, "pgfp.txt", sf.FASTA),
        (FASTA_RECORD, "pgfp.seq", sf.FASTA),
        (FASTA_RECORD, "", sf.FASTA),
        (GENBANK_RECORD, "pkarc.fasta", sf.GENBANK),
        (GENBANK_RECORD, "pkarc", sf.GENBANK),
        (SYNTHETIC_ORF, "orf.txt", sf.RAW),
        (SYNTHETIC_ORF, "", sf.RAW),
    ],
)
def test_the_content_decides_the_format_not_the_name(text, filename, expected):
    assert sf.sniff_format(text, filename=filename).fmt == expected


@pytest.mark.unit
def test_a_disagreement_between_content_and_name_is_recorded_not_resolved_by_name():
    verdict = sf.sniff_format(GENBANK_RECORD, filename="pkarc.fasta")

    assert verdict.fmt == sf.GENBANK, "content wins"
    assert verdict.hint == sf.FASTA
    assert verdict.disagrees_with_name is True


@pytest.mark.unit
def test_a_name_that_agrees_is_not_reported_as_a_disagreement():
    assert sf.sniff_format(FASTA_RECORD, filename="x.fasta").disagrees_with_name is False
    assert sf.sniff_format(SYNTHETIC_ORF, filename="x.txt").disagrees_with_name is False


@pytest.mark.unit
@pytest.mark.parametrize(
    ("text", "must_mention"),
    [
        ("%PDF-1.7\nbinary junk here", "PDF"),
        ("Dear students, the sequence is attached.", "Dear students"),
        ("", "nothing to read"),
        ("\x00\x01\x02binary", "binary"),
    ],
)
def test_content_matching_no_format_is_refused_by_name(text, must_mention):
    verdict = sf.sniff_format(text)

    assert verdict.fmt == sf.UNKNOWN
    assert must_mention.lower() in verdict.reason.lower(), verdict.reason


@pytest.mark.unit
def test_the_dialog_filter_offers_the_wider_set_and_keeps_all_files():
    for ext in ("*.txt", "*.seq", "*.fa", "*.fasta", "*.gb", "*.gbk"):
        assert ext in sf.FILE_DIALOG_FILTER
    assert "All files (*)" in sf.FILE_DIALOG_FILTER, (
        "a file with no extension must still be selectable"
    )


# ── Defect 1: pasting ──────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("pasted", "expected_fmt"),
    [(SYNTHETIC_ORF, "fasta"), (FASTA_RECORD, sf.FASTA), (GENBANK_RECORD, sf.GENBANK)],
)
def test_each_pasted_form_loads_a_construct(view, emitted, pasted, expected_fmt):
    """Raw residues, FASTA and GenBank all reach the parse worker."""
    view._load_sequence_text(pasted, source="pasted sequence")

    assert len(emitted) == 1
    _, fmt = emitted[0]
    assert fmt == expected_fmt


@pytest.mark.unit
def test_bare_residues_are_wrapped_so_the_existing_importer_can_read_them(view, emitted):
    view.name_edit.setText("pGFP-S12")
    view._load_sequence_text(SYNTHETIC_ORF, source="pasted sequence")

    payload, fmt = emitted[0]
    assert fmt == "fasta"
    assert payload.startswith(">pGFP-S12\n")
    assert SYNTHETIC_ORF in payload


@pytest.mark.unit
def test_every_transformation_is_surfaced_not_swallowed(view, emitted):
    """Lower case, line breaks and RNA all reported, in the panel, after loading."""
    view._load_sequence_text(MESSY_RAW, source="pasted sequence")

    assert emitted, "a transformed sequence must still load"
    assert view.import_notice.isVisible() or not view.import_notice.isHidden()
    shown = view.import_notice.text()
    assert "upper case" in shown.lower()
    assert "whitespace" in shown.lower()
    assert "rna" in shown.lower(), shown


@pytest.mark.unit
def test_a_clean_paste_leaves_no_notice(view, emitted):
    """The notice means something changed; it must not cry wolf."""
    view._load_sequence_text(SYNTHETIC_ORF, source="pasted sequence")

    assert emitted
    assert view.import_notice.text() == ""


@pytest.mark.unit
def test_an_unusable_paste_is_refused_with_its_reason(view, emitted, errors):
    view._load_sequence_text("ACGTNNNNACGT", source="pasted sequence")

    assert not emitted, "nothing may load"
    assert errors and "ambiguity" in errors[0].lower(), errors


# ── The paste dialog itself ────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize("text", [SYNTHETIC_ORF, FASTA_RECORD, GENBANK_RECORD])
def test_the_paste_dialog_enables_loading_for_every_supported_form(app, text):
    dlg = SequencePasteDialog()
    try:
        dlg.editor.setPlainText(text)
        ok = dlg.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok.isEnabled(), dlg.status.text()
        assert dlg.verdict is not None and dlg.verdict.ok
    finally:
        dlg.deleteLater()


@pytest.mark.unit
def test_the_paste_dialog_reports_transformations_before_loading(app):
    dlg = SequencePasteDialog()
    try:
        dlg.editor.setPlainText(MESSY_RAW)
        assert dlg.transformations, "clean_sequence reported changes; the dialog must hold them"
        assert "rna" in " ".join(dlg.transformations).lower()
    finally:
        dlg.deleteLater()


@pytest.mark.unit
def test_the_paste_dialog_refuses_what_cannot_be_loaded(app):
    dlg = SequencePasteDialog()
    try:
        dlg.editor.setPlainText("Dear students, please see attached.")
        ok = dlg.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert not ok.isEnabled()
        assert "neither a FASTA" in dlg.status.text()
    finally:
        dlg.deleteLater()


@pytest.mark.unit
def test_the_paste_dialog_writes_no_parser_of_its_own(app):
    """It must hand text on untouched; parsing belongs to the existing path."""
    dlg = SequencePasteDialog()
    try:
        dlg.editor.setPlainText(GENBANK_RECORD)
        assert dlg.sequence_text() == GENBANK_RECORD
    finally:
        dlg.deleteLater()


# ── Defect 2: dropped files ────────────────────────────────────────────


def _drop(paths: list[Path]) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    return mime


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "content", "expected_fmt"),
    [
        ("pkarc.gb", GENBANK_RECORD, sf.GENBANK),
        ("pgfp.fasta", FASTA_RECORD, sf.FASTA),
        ("pgfp.txt", FASTA_RECORD, sf.FASTA),
        ("pkarc.fasta", GENBANK_RECORD, sf.GENBANK),
    ],
)
def test_a_dropped_sequence_file_loads(view, emitted, tmp_path, name, content, expected_fmt):
    path = tmp_path / name
    path.write_text(content)

    view.load_dropped_files([str(path)])

    assert len(emitted) == 1, "the drop must reach the parse worker"
    assert emitted[0][1] == expected_fmt


@pytest.mark.unit
def test_a_dropped_unsupported_file_says_so(view, emitted, errors, tmp_path):
    """The whole defect was that this was silent. Assert the message exists."""
    pdf = tmp_path / "lab_manual.pdf"
    pdf.write_bytes(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\nnot a sequence")

    view.load_dropped_files([str(pdf)])

    assert not emitted
    assert errors, "a refused drop must not be silent"
    assert "pdf" in errors[0].lower() or "not a text file" in errors[0].lower(), errors


@pytest.mark.unit
def test_a_dropped_text_file_that_is_not_a_sequence_names_what_was_found(
    view, emitted, errors, tmp_path
):
    note = tmp_path / "instructions.txt"
    note.write_text("Hand in your primer design by Friday.")

    view.load_dropped_files([str(note)])

    assert not emitted
    assert errors and "Hand in your primer" in errors[0], errors


@pytest.mark.unit
def test_the_canvas_accepts_a_file_drag_it_used_to_refuse(view, tmp_path):
    """DragEnterEvent accepted only the internal part MIME type."""
    path = tmp_path / "pgfp.fasta"
    path.write_text(FASTA_RECORD)
    mime = _drop([path])

    from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
        dropped_file_paths,
    )

    # Compared as paths, not strings: QUrl.toLocalFile() returns forward
    # slashes on Windows, where the same file is also spelt with backslashes.
    assert [Path(p) for p in dropped_file_paths(mime)] == [path]
    assert dropped_file_paths(QMimeData()) == [], "a drag with no urls carries no files"


@pytest.mark.unit
def test_dropping_several_files_loads_one_and_says_which(view, emitted, tmp_path, monkeypatch):
    warned: list[str] = []
    monkeypatch.setattr(
        "karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view.show_warning",
        lambda *a, **k: warned.append(k.get("message", "")),
    )
    first = tmp_path / "a.fasta"
    second = tmp_path / "b.fasta"
    first.write_text(FASTA_RECORD)
    second.write_text(FASTA_RECORD)

    view.load_dropped_files([str(first), str(second)])

    assert len(emitted) == 1
    assert warned and "a.fasta" in warned[0], warned


# ── The property the brief singles out ─────────────────────────────────


@pytest.mark.unit
def test_a_pasted_construct_is_not_written_up_as_an_in_silico_assembly(view):
    """It takes the imported-file path, whose handler records no method step.

    ``_on_assembly_finished`` records ``assembly_step``; ``_on_parse_finished``
    deliberately does not, because a construct that arrived from outside was
    not assembled here. A paste must land on the second.
    """
    from karcytics_plugins.synthetic_biology.analysis.models.domain import PlasmidVector

    controller = view.controller
    vector = PlasmidVector(
        id="x", name="pasted", description="", sequence=SYNTHETIC_ORF, is_circular=True
    )

    controller._on_parse_finished(vector)

    # State round-trips the vector through a dict, so compare by value.
    loaded = controller.state.get_active_plasmid()
    assert loaded is not None and loaded.sequence == vector.sequence, "it must still load"
    assert controller.state.methods_log == [], (
        "an imported or pasted construct must not appear as an in-silico assembly"
    )

    controller._on_assembly_finished(vector)
    assert controller.state.methods_log, "an actual assembly still records one"


@pytest.mark.unit
def test_every_entry_route_emits_on_the_same_signal(view, emitted, tmp_path):
    """One router, so the methods-log property above cannot be true of only one."""
    path = tmp_path / "pgfp.fasta"
    path.write_text(FASTA_RECORD)

    view._load_sequence_text(SYNTHETIC_ORF, source="pasted sequence")
    view.load_dropped_files([str(path)])
    view._load_sequence_text(GENBANK_RECORD, source="pasted sequence")

    assert len(emitted) == 3, "paste, drop and GenBank paste all take the one path"

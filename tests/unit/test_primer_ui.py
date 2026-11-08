"""The primer UI: wiring, worker use, and that it decides nothing itself.

These are headless. What they pin is that every value on screen came from an
engine — the panels render ``RubricCheck``, ``AmplificationResult`` and ``Gel``
objects and never re-derive a verdict, a binding site or a band position.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis.assembly import amplification as amp
from karcytics_plugins.synthetic_biology.analysis.assembly import gel as gel_engine
from karcytics_plugins.synthetic_biology.analysis.assembly import primer_screen as ps
from karcytics_plugins.synthetic_biology.analysis.assembly import restriction as rst
from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
    VectorAssemblyEngine,
)
from karcytics_plugins.synthetic_biology.ui.widgets.amplification_track import AmplificationTrack
from karcytics_plugins.synthetic_biology.ui.widgets.gel_view import GelView
from karcytics_plugins.synthetic_biology.ui.widgets.provenance_badge import ProvenanceBadge
from karcytics_plugins.synthetic_biology.ui.widgets.rubric_panel import RubricPanel
from karcytics_plugins.synthetic_biology.ui.workers import (
    AmplificationWorker,
    InternalSiteWorker,
    PrimerCandidateWorker,
)

from .sequence_fixtures import (
    ECORI_TAIL,
    HINDIII_TAIL,
    SYNTHETIC_ORF,
    SYNTHETIC_TEMPLATE,
    primers_for,
    repeated_site_template,
)

FWD, REV = primers_for(SYNTHETIC_ORF)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


# ── Workers ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_candidate_generation_runs_on_a_worker(app):
    """Ranking screens a grid of lengths at every offset; not on the GUI thread."""
    worker = PrimerCandidateWorker(target_sequence=SYNTHETIC_ORF, limit=5)
    received = []
    worker.candidates_ready.connect(received.append)

    worker._execute()

    assert len(received) == 1
    assert 0 < len(received[0]) <= 5
    assert "checks" in received[0][0]
    assert "summary" in received[0][0]


@pytest.mark.unit
def test_the_amplification_worker_drives_all_three_engines(app):
    """The view must not have to orchestrate PCR, then digest, then gel."""
    worker = AmplificationWorker(
        template=SYNTHETIC_TEMPLATE,
        forward_primer=ECORI_TAIL + FWD,
        reverse_primer=HINDIII_TAIL + REV,
        forward_tail=ECORI_TAIL,
        reverse_tail=HINDIII_TAIL,
        enzymes=("EcoRI", "HindIII"),
    )
    received = []
    worker.amplification_ready.connect(received.append)

    worker._execute()

    payload = received[0]
    assert payload["result"].outcome == amp.PRODUCT
    assert payload["digest"] is not None
    assert payload["gel"] is not None
    assert payload["template_bp"] == len(SYNTHETIC_TEMPLATE)
    # Ladder plus product plus digest.
    assert [lane.kind for lane in payload["gel"].lanes] == ["ladder", "pcr_product", "digest"]


@pytest.mark.unit
def test_multiple_products_each_get_a_lane(app):
    """A student seeing two bands has learned the primers are not unique."""
    worker = AmplificationWorker(
        template=repeated_site_template(), forward_primer=FWD, reverse_primer=REV
    )
    received = []
    worker.amplification_ready.connect(received.append)
    worker._execute()

    payload = received[0]
    assert payload["result"].outcome == amp.MULTIPLE_PRODUCTS
    product_lanes = [lane for lane in payload["gel"].lanes if lane.kind == "pcr_product"]
    assert len(product_lanes) == 2


@pytest.mark.unit
def test_the_internal_site_worker_reports_sites_in_the_region(app):
    worker = InternalSiteWorker(sequence="AAAGAATTCAAA", enzymes=("EcoRI",))
    received = []
    worker.sites_ready.connect(received.append)
    worker._execute()
    assert len(received[0]["sites"]) == 1


@pytest.mark.unit
def test_the_internal_site_worker_handles_no_enzymes(app):
    worker = InternalSiteWorker(sequence=SYNTHETIC_ORF, enzymes=())
    received = []
    worker.sites_ready.connect(received.append)
    worker._execute()
    assert received[0]["sites"] == ()


# ── The rubric panel renders, it does not judge ────────────────────────


@pytest.mark.unit
def test_the_rubric_panel_shows_one_row_per_check(app, destroy_after):
    panel = destroy_after(RubricPanel())
    checks = ps.screen_primer(FWD, "", None)

    panel.show_candidate(checks, ps.summarise(checks))

    assert panel.table.rowCount() == len(checks)


@pytest.mark.unit
def test_a_check_that_could_not_run_shows_as_not_run(app, destroy_after):
    """Never a silent gap: a skipped check that looks like a pass is the danger."""
    panel = destroy_after(RubricPanel())
    skipped = ps.check_template_uniqueness(None, FWD, REV)
    assert skipped.passed is None

    panel.show_candidate([skipped], ps.summarise([skipped]))

    cell = panel.table.item(0, 3)
    assert cell is not None
    assert cell.text() == "not run"


@pytest.mark.unit
def test_the_verdict_says_when_checks_were_skipped(app, destroy_after):
    panel = destroy_after(RubricPanel())
    checks = [ps.check_template_uniqueness(None, FWD, REV)]
    panel.show_candidate(checks, ps.summarise(checks))
    assert "not run" in panel.verdict_label.text()


@pytest.mark.unit
def test_a_failing_check_shows_the_engines_remediation(app, destroy_after):
    """A bare FAIL teaches nothing, and the advice is the engine's, not the view's."""
    panel = destroy_after(RubricPanel())
    at_rich = "ATATATATATATATATAT"
    checks = ps.screen_primer(at_rich, "", None)
    failing = [c for c in checks if c.passed is False]
    assert failing, "fixture should fail at least one check"

    panel.show_candidate(checks, ps.summarise(checks))

    assert panel.advice_header.isVisible() or panel.advice_header.isVisibleTo(panel)
    rendered = " ".join(
        panel._advice_layout.itemAt(i).widget().text()
        for i in range(panel._advice_layout.count())
        if panel._advice_layout.itemAt(i).widget() is not None
    )
    for check in failing:
        assert check.remediation, f"{check.name} has no remediation in the engine"
        assert check.remediation[:40] in rendered


@pytest.mark.unit
def test_the_panel_accepts_checks_reloaded_from_a_saved_workspace(app, destroy_after):
    """A saved workspace restores checks as dicts, not dataclasses."""
    panel = destroy_after(RubricPanel())
    checks = [c.to_dict() for c in ps.screen_primer(FWD, "", None)]
    panel.show_candidate(checks, {"verdict": "pass", "passed": 5, "total": 5, "skipped": 0})
    assert panel.table.rowCount() == len(checks)


# ── The three-way provenance distinction reaches the screen ────────────


@pytest.mark.unit
def test_each_check_row_carries_a_provenance_badge(app, destroy_after):
    panel = destroy_after(RubricPanel())
    checks = ps.screen_primer(FWD, "", None)
    panel.show_candidate(checks, ps.summarise(checks))

    for row in range(panel.table.rowCount()):
        assert isinstance(panel.table.cellWidget(row, 4), ProvenanceBadge)


@pytest.mark.unit
def test_a_convention_is_labelled_as_one_at_the_point_of_display(app, destroy_after):
    """Not only in the exported methods text."""
    panel = destroy_after(RubricPanel())
    checks = ps.screen_primer(FWD, "", None)
    gc = next(c for c in checks if c.name == ps.GC_CONTENT)
    assert gc.provenance_label == "our convention"

    panel.show_candidate(checks, ps.summarise(checks))
    badge = panel.table.cellWidget(0, 4)
    assert "convention" in _text_of(badge)


@pytest.mark.unit
def test_a_published_mechanism_is_shown_as_distinct_from_a_convention(app, destroy_after):
    """The whole point of stage 1: three states, not two, visible on screen."""
    panel = destroy_after(RubricPanel())
    checks = ps.screen_primer(FWD, "", None)
    hairpin = next(c for c in checks if c.name == ps.HAIRPIN)
    assert hairpin.provenance_label == "our threshold, published mechanism"
    assert hairpin.mechanism

    panel.show_candidate(checks, ps.summarise(checks))
    row = [c.name for c in checks].index(ps.HAIRPIN)
    rendered = _text_of(panel.table.cellWidget(row, 4))
    assert "published mechanism" in rendered
    assert "Mechanism" in rendered, "the citation keys must be shown inline"


def _text_of(widget) -> str:
    from PySide6.QtWidgets import QLabel

    return " ".join(child.text() for child in widget.findChildren(QLabel))


# ── Amplification track ────────────────────────────────────────────────


@pytest.mark.unit
def test_the_track_renders_a_product_without_recomputing_it(app, destroy_after):
    track = destroy_after(AmplificationTrack())
    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV)

    track.show_result(result, len(SYNTHETIC_TEMPLATE))

    assert "One product" in track.heading.text()
    assert track.canvas._result is result, "the track must hold the engine's object"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("outcome_builder", "expected"),
    [
        (lambda: amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV), "One product"),
        (lambda: amp.amplify(repeated_site_template(), FWD, REV), "Multiple products"),
        (lambda: amp.amplify(SYNTHETIC_TEMPLATE, "GGGGGGGGGGGGGGGGGGGG", REV), "No product"),
    ],
)
def test_failure_modes_are_rendered_as_results(app, destroy_after, outcome_builder, expected):
    """Not error dialogs. These are the teaching content."""
    track = destroy_after(AmplificationTrack())
    track.show_result(outcome_builder(), len(SYNTHETIC_TEMPLATE))
    assert expected in track.heading.text()


@pytest.mark.unit
def test_the_track_shows_the_engines_notes_verbatim(app, destroy_after):
    track = destroy_after(AmplificationTrack())
    result = amp.amplify(repeated_site_template(), FWD, REV)
    track.show_result(result, len(repeated_site_template()))

    for note in result.notes:
        assert note in track.notes.text()


# ── Gel view ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_the_gel_view_reads_mobility_off_the_lane_objects(app, destroy_after):
    """A build_gel bug was caught where lanes kept a stale window.

    The view must trust the engine's repositioned values, so this asserts the
    canvas holds the engine's own lane objects rather than anything derived.
    """
    view = destroy_after(GelView())
    digest = rst.double_digest("AAAGAATTCAAAAAGCTTTTT", "EcoRI", "HindIII")
    built = gel_engine.build_gel(
        [gel_engine.product_lane(500), gel_engine.digest_lane(digest)], min_bp=50, max_bp=5000
    )

    view.show_gel(built)

    assert view.canvas._lanes == list(built.lanes)
    for lane in view.canvas._lanes:
        assert lane.min_bp == 50 and lane.max_bp == 5000


@pytest.mark.unit
def test_the_gel_view_states_that_the_mobility_model_is_a_convention(app, destroy_after):
    view = destroy_after(GelView())
    view.show_gel(gel_engine.build_gel([gel_engine.product_lane(500)]))
    assert "convention" in view.model_note.text()


@pytest.mark.unit
def test_digest_limitations_are_visible_beside_a_gel_that_has_a_digest(app, destroy_after):
    """Not buried in a methods dialog: a student comparing to a real gel needs them.

    Scoped to a gel that actually carries a digest. A PCR-only gel used to
    show these, which says nothing about a PCR — see test_gel_caveats.
    """
    view = destroy_after(GelView())
    digest = rst.digest("AAAGAATTCAAAAAAAAGAATTCTTT", "EcoRI")
    view.show_gel(
        gel_engine.build_gel([gel_engine.product_lane(500), gel_engine.digest_lane(digest)])
    )

    shown = view.limitations.text() + view.limitations.toolTip()
    for name, _ in rst.DIGEST_LIMITATIONS:
        assert name in shown
    assert "methylation sensitivity" in shown
    assert "star activity" in shown


@pytest.mark.unit
def test_both_a_product_lane_and_a_digest_lane_are_served(app, destroy_after):
    view = destroy_after(GelView())
    digest = rst.digest("AAAGAATTCAAAAAAAAGAATTCTTT", "EcoRI")
    built = gel_engine.build_gel([gel_engine.product_lane(800), gel_engine.digest_lane(digest)])
    view.show_gel(built)
    kinds = [lane.kind for lane in view.canvas._lanes]
    assert "pcr_product" in kinds and "digest" in kinds


# ── The dialog ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_the_dialog_names_the_enzyme_for_a_tail_via_the_engine(app, destroy_after):
    """A view must not map GAATTC to EcoRI itself; that is a REBASE lookup."""
    from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
        PrimerDesignDialog,
    )

    class _Controller:
        state = None

        def handle_primer_design(self, **_kwargs):
            return []

    dialog = destroy_after(PrimerDesignDialog(SYNTHETIC_TEMPLATE, _Controller()))
    dialog.fwd_overhang_edit.setText(ECORI_TAIL)

    fwd, _rev = dialog._tail_enzymes()
    assert fwd[0] == "EcoRI"
    assert fwd == rst.enzymes_for_tail(ECORI_TAIL)


@pytest.mark.unit
def test_the_dialog_ranks_candidates_rather_than_showing_one_pair(app, destroy_after):
    from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
        PrimerDesignDialog,
    )

    class _Controller:
        state = None

    dialog = destroy_after(PrimerDesignDialog(SYNTHETIC_ORF, _Controller()))
    candidates = VectorAssemblyEngine.generate_primer_candidates(SYNTHETIC_ORF, limit=4)

    dialog._on_candidates(list(candidates))

    assert dialog.candidate_table.rowCount() == len(candidates)
    assert dialog.candidate_table.rowCount() > 1, "a ranked list, not a single pair"

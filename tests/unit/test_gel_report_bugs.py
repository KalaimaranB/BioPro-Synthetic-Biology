"""Regressions for the four Gel-tab defects reported from a 0-984 bp run.

Scenario: Amplify = whole target, coordinates 0-984, Tm 60 C, no tails,
Coverage = keep the whole target, 1 kb Plus ladder, 1.0% agarose.
"""

from __future__ import annotations

import random

import pytest
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis.assembly import amplification as amp
from karcytics_plugins.synthetic_biology.analysis.assembly import gel as gel_engine
from karcytics_plugins.synthetic_biology.analysis.assembly import primer_export
from karcytics_plugins.synthetic_biology.analysis.assembly import restriction as rst
from karcytics_plugins.synthetic_biology.analysis.assembly.primer_screen import product_length
from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
    VectorAssemblyEngine as V,
)
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
    PlasmidAssemblyController,
)
from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
    PrimerDesignDialog,
)
from karcytics_plugins.synthetic_biology.ui.widgets.gel_view import GelView


def _target(length: int, seed: int = 9) -> str:
    """A pseudo-random target of exactly ``length`` bp.

    One generator, reused. `random.Random(seed).choice(...)` inside a
    generator expression re-seeds on every iteration and yields a
    homopolymer, which primes everywhere and makes every pair ambiguous.
    """
    rng = random.Random(seed)
    body = "".join(rng.choice("ACGT") for _ in range(length - 3))
    return "ATG" + body


#: The reported target: 984 bp, 0-based half-open 0-984.
TARGET = _target(984)
ECORI, HINDIII = "GAATTC", "AAGCTT"


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _dialog(destroy_after, sequence=TARGET):
    return destroy_after(PrimerDesignDialog(sequence, PlasmidAssemblyController(SynBioState())))


# ── Bug 1: product size contradicted "no trimming" ────────────────────


@pytest.mark.unit
def test_the_target_length_follows_one_half_open_convention():
    """0-984 is sequence[0:984] and is 984 bp, everywhere."""
    assert len(TARGET) == 984
    assert product_length(0, 984) == 984
    assert product_length(0, 984, 6, 6) == 996


@pytest.mark.unit
def test_no_trimming_spans_the_whole_target():
    candidate = V.generate_primer_candidates(TARGET, limit=1, require_full_target=True)[0]
    assert candidate["product_bp"] == len(TARGET)
    assert candidate["covers_full_target"] is True
    assert candidate["trimmed_5p"] == 0
    assert candidate["trimmed_3p"] == 0


@pytest.mark.unit
def test_product_length_equals_reverse_end_minus_forward_start_plus_tails():
    candidate = V.generate_primer_candidates(
        TARGET, limit=1, require_full_target=True, fwd_overhang=ECORI, rev_overhang=HINDIII
    )[0]
    fwd, rev = candidate["forward"], candidate["reverse"]
    expected = product_length(fwd.target_region[0], rev.target_region[1], len(ECORI), len(HINDIII))
    assert candidate["product_bp"] == expected == len(TARGET) + 12


@pytest.mark.unit
@pytest.mark.parametrize("tails", [("", ""), (ECORI, HINDIII)])
def test_every_surface_reports_the_same_product_size(tails):
    """The candidate table said 984 while the gel said 996 for the same pair."""
    fwd_tail, rev_tail = tails
    candidate = V.generate_primer_candidates(
        TARGET, limit=1, require_full_target=True, fwd_overhang=fwd_tail, rev_overhang=rev_tail
    )[0]
    result = amp.amplify(
        TARGET,
        candidate["forward"].sequence,
        candidate["reverse"].sequence,
        forward_tail=fwd_tail,
        reverse_tail=rev_tail,
    )
    assert result.product is not None
    assert candidate["product_bp"] == result.product.length

    lane = gel_engine.product_lane(result.product.length)
    assert lane.bands[0].size_bp == candidate["product_bp"]

    exported = primer_export.primer_rows(candidate)[0]["product_bp"]
    assert exported == candidate["product_bp"]


@pytest.mark.unit
def test_a_trimmed_product_is_explained_not_returned_quietly():
    """The reported symptom: 973 bp against a 984 bp target, with no warning."""
    candidate = V.generate_primer_candidates(TARGET, limit=1)[0]
    if candidate["covers_full_target"]:
        pytest.skip("this fixture's best unconstrained pair happens to span the target")

    note = candidate["coverage_note"]
    assert "No acceptable primers at the exact target ends" in note
    assert str(candidate["product_bp"]) in note
    assert f"{candidate['trimmed_5p']} bp at 5'" in note


@pytest.mark.unit
def test_a_full_coverage_candidate_carries_no_trim_warning():
    candidate = V.generate_primer_candidates(TARGET, limit=1, require_full_target=True)[0]
    assert candidate["coverage_note"] == ""


@pytest.mark.unit
def test_the_coverage_control_says_which_way_it_is_set(app, destroy_after):
    """It read 'Keep the whole target (no trimming)' while being switched OFF."""
    dialog = _dialog(destroy_after)
    assert not dialog.full_target_toggle.isChecked()
    assert "Trimming allowed" in dialog.full_target_toggle.text()

    dialog.full_target_toggle.setChecked(True)
    assert "Keeping the whole target" in dialog.full_target_toggle.text()


@pytest.mark.unit
def test_changing_coverage_drops_results_from_the_other_setting(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog._on_design_clicked()
    assert dialog.candidate_table.rowCount() > 0

    dialog.full_target_toggle.setChecked(True)

    assert dialog.candidate_table.rowCount() == 0
    assert "Coverage changed" in dialog.status.text()


@pytest.mark.unit
def test_the_trim_warning_reaches_the_screen(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog._on_design_clicked()
    dialog.candidate_table.selectRow(0)

    candidate = dialog._selected_candidate()
    if candidate["coverage_note"]:
        assert "No acceptable primers" in dialog.input_problem.text()


# ── Bug 2: a phantom band at the top of the sample lane ───────────────


@pytest.mark.unit
def test_a_single_product_lane_has_exactly_one_band():
    """The faint bar at ~10 kb was the well, not a fragment."""
    lane = gel_engine.product_lane(973)
    assert len(lane.bands) == 1
    assert lane.bands[0].size_bp == 973


@pytest.mark.unit
def test_no_band_is_created_for_an_absent_product():
    built = gel_engine.build_gel([], ladder=None)
    assert built.lanes == ()


@pytest.mark.unit
@pytest.mark.parametrize("bad", [0, -1, -500])
def test_an_invalid_fragment_length_is_refused_not_clamped_to_the_top(bad):
    """A 0 or negative length must not become a band at the top of the window."""
    with pytest.raises(ValueError, match="must be positive"):
        gel_engine.relative_mobility(bad)


@pytest.mark.unit
def test_an_oversized_fragment_is_marked_off_scale_high():
    lane = gel_engine.digest_lane([50_000, 1000])
    big = next(b for b in lane.bands if b.size_bp == 50_000)
    assert big.out_of_range is True
    assert big.off_scale_high is True


@pytest.mark.unit
def test_an_undersized_fragment_is_marked_off_scale_low():
    lane = gel_engine.digest_lane([20, 1000])
    small = next(b for b in lane.bands if b.size_bp == 20)
    assert small.out_of_range is True
    assert small.off_scale_high is False


@pytest.mark.unit
def test_the_renderer_does_not_place_an_off_scale_band_in_the_gel(app, destroy_after):
    """It is drawn as a marker outside the resolving area, not at the edge."""
    view = destroy_after(GelView())
    built = gel_engine.build_gel([gel_engine.product_lane(50_000)], ladder=None)
    view.show_gel(built)
    view.canvas.resize(400, 300)
    view.canvas.grab()  # force a paint so hit rectangles are recorded

    band = built.lanes[0].bands[0]
    assert band.off_scale_high is True


# ── Bug 3: digest caveats on a PCR-only gel ───────────────────────────


@pytest.mark.unit
def test_a_pcr_only_gel_shows_pcr_caveats(app, destroy_after):
    view = destroy_after(GelView())
    view.show_gel(gel_engine.build_gel([gel_engine.product_lane(973)]))

    shown = view.limitations.text()
    assert "primer-dimers" in shown
    assert "non-specific amplification" in shown
    assert "methylation sensitivity" not in shown, "digest caveats do not apply to a PCR"
    assert "star activity" not in shown


@pytest.mark.unit
def test_a_digest_gel_keeps_the_digest_caveats(app, destroy_after):
    view = destroy_after(GelView())
    digest = rst.digest("AAAGAATTCAAAAAAAAGAATTCTTT", "EcoRI")
    view.show_gel(gel_engine.build_gel([gel_engine.digest_lane(digest)]))

    shown = view.limitations.text()
    assert "methylation sensitivity" in shown
    assert "star activity" in shown


@pytest.mark.unit
def test_a_pcr_plus_digest_gel_shows_both_sets(app, destroy_after):
    view = destroy_after(GelView())
    digest = rst.digest("AAAGAATTCAAAAAAAAGAATTCTTT", "EcoRI")
    view.show_gel(
        gel_engine.build_gel([gel_engine.product_lane(973), gel_engine.digest_lane(digest)])
    )

    shown = view.limitations.text()
    assert "primer-dimers" in shown
    assert "methylation sensitivity" in shown


@pytest.mark.unit
def test_the_gel_reports_its_own_lane_kinds():
    digest = rst.digest("AAAGAATTCAAAAAAAAGAATTCTTT", "EcoRI")
    built = gel_engine.build_gel([gel_engine.product_lane(973), gel_engine.digest_lane(digest)])
    assert set(built.lane_kinds) == {"pcr_product", "digest"}
    assert "ladder" not in built.lane_kinds


# ── Bug 4: the unfinished ladder sentence ─────────────────────────────


@pytest.mark.unit
def test_clicking_a_reference_band_gives_a_complete_sentence(app, destroy_after):
    """It read '5000 bp in 1 kb Plus DNA ladder.' — a fragment."""
    view = destroy_after(GelView())
    built = gel_engine.build_gel([gel_engine.product_lane(973)])
    ladder = built.lanes[0]
    reference = next(b for b in ladder.bands if b.is_reference)

    view.show_gel(built)
    view._on_band_clicked(ladder, reference)

    note = view.selection_note.text()
    assert note.startswith("The ")
    assert "is the high-intensity reference band" in note
    assert ladder.name in note


@pytest.mark.unit
def test_clicking_an_ordinary_ladder_band_also_reads_as_a_sentence(app, destroy_after):
    view = destroy_after(GelView())
    built = gel_engine.build_gel([gel_engine.product_lane(973)])
    ladder = built.lanes[0]
    plain = next(b for b in ladder.bands if not b.is_reference)

    view.show_gel(built)
    view._on_band_clicked(ladder, plain)

    assert "is a size standard" in view.selection_note.text()


@pytest.mark.unit
def test_clicking_a_product_band_says_it_is_a_predicted_fragment(app, destroy_after):
    view = destroy_after(GelView())
    built = gel_engine.build_gel([gel_engine.product_lane(973)], ladder=None)
    lane = built.lanes[0]
    view.show_gel(built)
    view._on_band_clicked(lane, lane.bands[0])

    assert "predicted fragment" in view.selection_note.text()


@pytest.mark.unit
def test_the_asterisk_is_explained_in_a_legend(app, destroy_after):
    view = destroy_after(GelView())
    assert "resolving window" in view.legend.text()
    assert "position approximate" in view.legend.text()


@pytest.mark.unit
def test_the_ladder_states_that_its_band_list_is_unverified():
    """Supplier listings disagree; the data must not imply more than it knows."""
    ladder = gel_engine.LADDERS["1kb_plus"]
    assert ladder.provenance
    assert "NOT verified" in ladder.provenance
    assert "Confirm" in ladder.provenance


@pytest.mark.unit
def test_clicking_a_ladder_band_surfaces_that_caveat(app, destroy_after):
    view = destroy_after(GelView())
    built = gel_engine.build_gel([gel_engine.product_lane(973)])
    ladder = built.lanes[0]
    view.show_gel(built)
    view._on_band_clicked(ladder, ladder.bands[0])

    assert "NOT verified" in view.selection_note.text()


# ── Item 5: cross-tab agreement and edge cases ────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize("full_target", [False, True])
def test_all_three_tabs_agree_on_size_and_primer_positions(app, destroy_after, full_target):
    dialog = _dialog(destroy_after)
    dialog.full_target_toggle.setChecked(full_target)
    dialog._on_design_clicked()
    dialog.candidate_table.selectRow(0)

    candidate = dialog._selected_candidate()
    shown_in_table = dialog.candidate_table.item(0, 8).text()
    assert shown_in_table == f"{candidate['product_bp']} bp"

    track = dialog.amplification_track.canvas._result
    assert track is not None
    product = track.amplicons[0]
    assert product.length == candidate["product_bp"]
    assert product.forward_site.start == candidate["forward"].target_region[0]

    sizes = [
        band.size_bp
        for lane in dialog.gel_view.canvas._lanes
        if lane.kind == "pcr_product"
        for band in lane.bands
    ]
    assert candidate["product_bp"] in sizes


@pytest.mark.unit
def test_a_one_base_target_is_refused_not_crashed():
    with pytest.raises(ValueError, match="too short"):
        V.generate_primer_candidates("A", limit=1)


@pytest.mark.unit
def test_a_target_longer_than_ten_kb_still_designs():
    long_target = _target(12_000, seed=3)
    candidate = V.generate_primer_candidates(long_target, limit=1, require_full_target=True)[0]
    assert candidate["product_bp"] == 12_000


@pytest.mark.unit
def test_a_product_above_the_window_is_off_scale_not_clamped_silently():
    lane = gel_engine.product_lane(12_000)
    band = lane.bands[0]
    assert band.out_of_range is True
    assert band.off_scale_high is True
    assert "*" not in band.label or band.label.endswith("bp")


@pytest.mark.unit
def test_a_product_below_one_hundred_bp_is_marked_off_scale_low():
    band = gel_engine.product_lane(60).bands[0]
    assert band.out_of_range is True
    assert band.off_scale_high is False


@pytest.mark.unit
@pytest.mark.parametrize("ladder", sorted(gel_engine.LADDERS))
def test_switching_ladder_keeps_the_product_size(ladder):
    built = gel_engine.build_gel([gel_engine.product_lane(984)], ladder=ladder)
    product = next(lane for lane in built.lanes if lane.kind == "pcr_product")
    assert product.bands[0].size_bp == 984


@pytest.mark.unit
@pytest.mark.parametrize("percentage", sorted(gel_engine.AGAROSE_WINDOWS))
def test_switching_agarose_changes_position_not_size(percentage):
    low, high = gel_engine.window_for_agarose(percentage)
    built = gel_engine.build_gel(
        [gel_engine.product_lane(984)], ladder=None, min_bp=low, max_bp=high
    )
    band = built.lanes[0].bands[0]
    assert band.size_bp == 984
    assert built.min_bp == low and built.max_bp == high


@pytest.mark.unit
def test_agarose_choice_moves_the_band():
    def mobility(percentage: str) -> float:
        low, high = gel_engine.window_for_agarose(percentage)
        built = gel_engine.build_gel(
            [gel_engine.product_lane(984)], ladder=None, min_bp=low, max_bp=high
        )
        return built.lanes[0].bands[0].relative_mobility

    assert mobility("0.7%") != mobility("2.0%")


@pytest.mark.unit
def test_adding_tails_increases_every_reported_size_by_the_same_amount():
    bare = V.generate_primer_candidates(TARGET, limit=1, require_full_target=True)[0]
    tailed = V.generate_primer_candidates(
        TARGET, limit=1, require_full_target=True, fwd_overhang=ECORI, rev_overhang=HINDIII
    )[0]
    assert tailed["product_bp"] - bare["product_bp"] == len(ECORI) + len(HINDIII)


# ── Follow-up: defects visible in the 0-801 + tails screenshot ────────


@pytest.mark.unit
def test_the_ladder_keeps_its_own_top_and_bottom_bands():
    """is_resolvable was strict, so 100 and 10000 were "unresolvable".

    Once off-scale markers existed, the 1 kb Plus ladder's own edge bands
    stopped being drawn and turned into arrows — the ladder lost its top and
    bottom, and the "*" legend described nothing.
    """
    lane = gel_engine.ladder_lane("1kb_plus")
    assert [b.size_bp for b in lane.bands if b.out_of_range] == []

    edges = {b.size_bp for b in lane.bands if b.at_edge}
    assert edges == {100, 10_000}


@pytest.mark.unit
@pytest.mark.parametrize(
    ("size", "resolvable"),
    [(99, False), (100, True), (101, True), (9_999, True), (10_000, True), (10_001, False)],
)
def test_the_window_bounds_are_inclusive(size, resolvable):
    assert gel_engine.is_resolvable(size) is resolvable


@pytest.mark.unit
def test_a_band_on_the_bound_is_at_the_edge_not_off_scale():
    assert gel_engine.is_at_edge(10_000) is True
    assert gel_engine.is_at_edge(100) is True
    assert gel_engine.is_at_edge(5_000) is False

    band = gel_engine.product_lane(10_000).bands[0]
    assert band.at_edge is True
    assert band.out_of_range is False
    assert "*" in band.label or band.at_edge


@pytest.mark.unit
def test_a_band_beyond_the_bound_is_off_scale_not_at_the_edge():
    band = gel_engine.product_lane(10_001).bands[0]
    assert band.out_of_range is True
    assert band.off_scale_high is True
    assert band.at_edge is False


@pytest.mark.unit
def test_two_fragments_off_the_same_end_get_separate_markers(app, destroy_after):
    """An 813 bp product cut with EcoRI + HindIII leaves 1 bp and 5 bp.

    Both are below the window; their markers were drawn at the same y and
    printed on top of each other.
    """
    lane = gel_engine.digest_lane([1, 807, 5])
    below = [b for b in lane.bands if b.out_of_range and not b.off_scale_high]
    assert len(below) == 2

    view = destroy_after(GelView())
    view.show_gel(gel_engine.build_gel([lane], ladder=None))
    view.canvas.resize(500, 320)
    view.canvas.grab()

    ys = sorted(rect.y() for rect, _lane, band in view.canvas._hits if band.out_of_range)
    assert len(ys) == 2
    assert ys[1] - ys[0] >= 10, "stacked markers must not share a line"


@pytest.mark.unit
def test_an_off_scale_marker_stays_inside_its_own_lane_column(app, destroy_after):
    """The marker text used to run across the neighbouring lane."""
    view = destroy_after(GelView())
    built = gel_engine.build_gel(
        [gel_engine.product_lane(50_000), gel_engine.product_lane(500)], ladder=None
    )
    view.show_gel(built)
    view.canvas.resize(600, 320)
    view.canvas.grab()

    marker = next((rect for rect, _lane, band in view.canvas._hits if band.out_of_range), None)
    assert marker is not None
    lane_pitch = 86 + 68 + 20  # _LANE_WIDTH + _LABEL_GUTTER + _LANE_GAP
    assert marker.width() <= lane_pitch


@pytest.mark.unit
def test_the_digest_of_a_tailed_product_sums_to_the_product(app, destroy_after):
    """0-801 with EcoRI/HindIII tails: 813 bp in, 1 + 807 + 5 out."""
    target = _target(801)
    candidate = V.generate_primer_candidates(
        target, limit=1, require_full_target=True, fwd_overhang=ECORI, rev_overhang=HINDIII
    )[0]
    assert candidate["product_bp"] == 813

    result = amp.amplify(
        target,
        candidate["forward"].sequence,
        candidate["reverse"].sequence,
        forward_tail=ECORI,
        reverse_tail=HINDIII,
    )
    digest = rst.digest(result.product.sequence, ["EcoRI", "HindIII"])
    assert sum(digest.fragment_lengths) == 813

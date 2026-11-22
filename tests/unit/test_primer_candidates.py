"""Candidate generation, ranking, and the contract the old callers rely on."""

from __future__ import annotations

import pytest
from Bio.SeqUtils import MeltingTemp

from karcytics_plugins.synthetic_biology.analysis.assembly.primer_rubric import PrimerRubric
from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
    VectorAssemblyEngine as V,
)
from karcytics_plugins.synthetic_biology.analysis.models.domain import Primer

#: GFPmut3-like coding start — the kind of target BIOL341 amplifies. Its first
#: bases are notably AT-rich, which is what makes it a useful fixture.
GFP = (
    "ATGAGTAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTT"
    "AATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATAC"
)
ECORI, HINDIII = "GAATTC", "AAGCTT"


# ── The Tm model is frozen ─────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    "seq",
    [
        "ATGAGTAAAGGAGAAGAACT",
        "GGAGAAGAACTTTTCACTGGAG",
        "GCGCGCGCGCGCGCGC",
        "ATATATATATATATAT",
        "AACGCGGGAAAAAGTGGAAG",
    ],
)
def test_calculate_tm_is_unchanged(seq):
    """Tm numerics are out of scope for this work and must not have moved.

    Pinned against Biopython called directly with the same table and
    corrections the engine documents (DNA_NN3, saltcorr=7), so this fails if
    either the table or the salt model is swapped.
    """
    expected = MeltingTemp.Tm_NN(
        seq, nn_table=MeltingTemp.DNA_NN3, Na=50.0, Mg=1.5, dnac1=250.0, dnac2=250.0, saltcorr=7
    )
    assert V.calculate_tm(seq) == pytest.approx(round(float(expected), 2))


@pytest.mark.unit
def test_tm_is_computed_on_the_annealing_region_not_the_tailed_oligo():
    """A 5' restriction tail must not enter the Tm, as before this change."""
    fwd, _ = V.design_primers(GFP, target_tm=60.0, fwd_overhang=ECORI, rev_overhang=HINDIII)
    anneal = fwd.sequence[len(ECORI) :]
    assert fwd.calculated_tm == pytest.approx(V.calculate_tm(anneal))
    assert fwd.calculated_tm != pytest.approx(V.calculate_tm(fwd.sequence))


# ── The old single-pair signature still works ──────────────────────────


@pytest.mark.unit
def test_design_primers_keeps_its_signature_and_shape():
    fwd, rev = V.design_primers(
        target_sequence=GFP, target_tm=60.0, fwd_overhang=ECORI, rev_overhang=HINDIII
    )
    assert isinstance(fwd, Primer) and isinstance(rev, Primer)
    assert fwd.direction == "FWD" and rev.direction == "REV"
    assert fwd.sequence.startswith(ECORI) and rev.sequence.startswith(HINDIII)
    assert fwd.overhang == ECORI and rev.overhang == HINDIII


@pytest.mark.unit
def test_length_keywords_still_bound_the_annealing_region():
    fwd, rev = V.design_primers(GFP, min_length=20, max_length=22)
    assert 20 <= fwd.annealing_length <= 22
    assert 20 <= rev.annealing_length <= 22


@pytest.mark.unit
def test_too_short_a_target_still_raises():
    with pytest.raises(ValueError, match="too short"):
        V.design_primers("ACGTACGT")


# ── Defect 1: GC excludes the tail ─────────────────────────────────────


@pytest.mark.unit
def test_reported_gc_is_the_annealing_region_only():
    fwd, _ = V.design_primers(GFP, fwd_overhang=ECORI, rev_overhang=HINDIII)
    anneal = fwd.sequence[len(ECORI) :]
    expected = 100.0 * (anneal.count("G") + anneal.count("C")) / len(anneal)
    assert fwd.gc_content == pytest.approx(round(expected, 1))
    assert fwd.overhang_gc_content == pytest.approx(33.3)  # GAATTC: 2 of 6
    assert fwd.annealing_length == len(anneal)


@pytest.mark.unit
def test_selected_primers_satisfy_the_gc_rubric():
    """The old implementation returned a 23% GC primer because nothing checked.

    With screening in the loop the chosen pair has to sit inside the window,
    unless no candidate can — which is reported, not silently accepted.
    """
    fwd, rev = V.design_primers(GFP, fwd_overhang=ECORI, rev_overhang=HINDIII)
    for primer in (fwd, rev):
        assert 40.0 <= primer.gc_content <= 60.0, f"{primer.name} at {primer.gc_content}%"


# ── Defect 2: the offset window ────────────────────────────────────────


@pytest.mark.unit
def test_offsets_are_explored_not_pinned_to_the_target_ends():
    candidates = V.generate_primer_candidates(GFP, limit=200)
    starts = {c["forward"].target_region[0] for c in candidates}
    assert len(starts) > 1, "the forward primer never slid off position 0"


@pytest.mark.unit
def test_zero_offset_reproduces_the_original_fixed_end_behaviour():
    rubric = PrimerRubric(max_offset=0)
    for candidate in V.generate_primer_candidates(GFP, rubric=rubric, limit=50):
        assert candidate["forward"].target_region[0] == 0
        assert candidate["reverse"].target_region[1] == len(GFP)
        assert candidate["covers_full_target"] is True


@pytest.mark.unit
def test_offset_is_bounded_by_the_rubric():
    rubric = PrimerRubric(max_offset=3)
    for candidate in V.generate_primer_candidates(GFP, rubric=rubric, limit=200):
        assert candidate["trimmed_5p"] <= 3
        assert candidate["trimmed_3p"] <= 3


@pytest.mark.unit
def test_primers_never_overlap_however_wide_the_offset_window():
    """A runaway offset would otherwise let the two primers cross."""
    rubric = PrimerRubric(max_offset=500)
    for candidate in V.generate_primer_candidates(GFP, rubric=rubric, limit=100):
        assert candidate["forward"].target_region[1] <= candidate["reverse"].target_region[0]
        assert candidate["product_bp"] > 0


# ── Ranking ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_candidates_are_ranked_best_first():
    candidates = V.generate_primer_candidates(GFP, limit=50)
    scores = [c["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.unit
def test_the_top_candidate_lands_near_the_target_tm():
    """Pair matching alone is not enough: the reaction's annealing temperature
    is set from the target, so proximity to it has to drive the ranking.
    """
    best = V.generate_primer_candidates(GFP, target_tm=60.0, limit=1)[0]
    assert abs(best["forward"].calculated_tm - 60.0) < 2.0
    assert abs(best["reverse"].calculated_tm - 60.0) < 2.0


@pytest.mark.unit
def test_limit_is_honoured():
    assert len(V.generate_primer_candidates(GFP, limit=5)) == 5


@pytest.mark.unit
def test_every_candidate_carries_its_full_check_list():
    candidate = V.generate_primer_candidates(GFP, limit=1)[0]
    names = {c["name"] for c in candidate["checks"]}
    from karcytics_plugins.synthetic_biology.analysis.assembly import primer_screen as ps

    assert set(ps.SINGLE_CHECKS) <= names
    assert set(ps.PAIR_CHECKS) <= names
    assert candidate["summary"]["verdict"] in ("pass", "fail", "incomplete")


@pytest.mark.unit
def test_product_size_and_uniqueness_are_evaluated_not_skipped():
    """Generation supplies the template and both positions, so neither of
    these can come back unevaluated — a skipped check here would mean a
    candidate was ranked on incomplete information.
    """
    candidate = V.generate_primer_candidates(GFP, limit=1)[0]
    by_name = {c["name"]: c for c in candidate["checks"]}
    assert by_name["product_size"]["passed"] is not None
    assert by_name["template_uniqueness"]["passed"] is not None


# ── Full-target coverage, which cloning depends on ─────────────────────


@pytest.mark.unit
def test_trimming_is_reported_so_it_cannot_pass_unnoticed():
    for candidate in V.generate_primer_candidates(GFP, limit=20):
        fwd_start = candidate["forward"].target_region[0]
        rev_end = candidate["reverse"].target_region[1]
        assert candidate["trimmed_5p"] == fwd_start
        assert candidate["trimmed_3p"] == len(GFP) - rev_end
        assert candidate["covers_full_target"] == (fwd_start == 0 and rev_end == len(GFP))


@pytest.mark.unit
def test_require_full_target_keeps_the_start_codon():
    """Amplifying an ORF to clone must not trim the ATG off the product."""
    candidates = V.generate_primer_candidates(GFP, limit=10, require_full_target=True)
    assert candidates
    for candidate in candidates:
        assert candidate["covers_full_target"] is True
        assert candidate["forward"].sequence.endswith(
            candidate["forward"].sequence[len(candidate["forward"].overhang) :]
        )
        anneal = candidate["forward"].sequence[len(candidate["forward"].overhang) :]
        assert GFP.startswith(anneal), "the forward primer must begin at the target start"


@pytest.mark.unit
def test_an_at_rich_start_is_reported_as_failing_not_quietly_accepted():
    """This target's first bases are AT-rich, so a full-coverage forward primer
    cannot meet a 40-60% GC rubric. The honest answer is a recorded failure.
    """
    best = V.generate_primer_candidates(GFP, limit=1, require_full_target=True)[0]
    assert best["forward"].gc_content < 40.0
    assert best["summary"]["verdict"] == "fail"
    assert "gc_content" in best["summary"]["failed_names"]


@pytest.mark.unit
def test_full_coverage_is_always_available_for_a_designable_target():
    """Offset 0 is always generated, so asking for full coverage can never
    empty the list for a target that can be designed at all. The guard in the
    engine stays as insurance against a later change to generation.
    """
    narrow = PrimerRubric(min_length=18, max_length=18, max_offset=0)
    candidates = V.generate_primer_candidates("ATGC" * 10, rubric=narrow, require_full_target=True)
    assert candidates
    assert all(c["covers_full_target"] for c in candidates)


# ── Rubric plumbing ────────────────────────────────────────────────────


@pytest.mark.unit
def test_an_inconsistent_rubric_is_rejected_up_front():
    bad = PrimerRubric(gc_min_percent=80.0, gc_max_percent=20.0)
    with pytest.raises(ValueError, match="Unusable primer rubric"):
        V.generate_primer_candidates(GFP, rubric=bad)


@pytest.mark.unit
def test_the_rubric_name_travels_with_the_primer():
    """A saved workspace should record which standard judged it."""
    rubric = PrimerRubric(name="BIOL341 Lab 3")
    best = V.generate_primer_candidates(GFP, rubric=rubric, limit=1)[0]
    assert best["forward"].rubric_name == "BIOL341 Lab 3"


@pytest.mark.unit
def test_structure_energies_are_attached_to_each_primer():
    fwd, rev = V.design_primers(GFP, fwd_overhang=ECORI, rev_overhang=HINDIII)
    for primer in (fwd, rev):
        assert primer.hairpin_dg is not None
        assert primer.self_dimer_dg is not None
        assert primer.hairpin_dg <= 0.0 and primer.self_dimer_dg <= 0.0

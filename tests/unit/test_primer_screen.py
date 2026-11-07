"""Each rubric check, exercised on its own and at its boundary."""

from __future__ import annotations

import pytest

from karcytics_plugins.synthetic_biology.analysis.assembly import primer_screen as ps
from karcytics_plugins.synthetic_biology.analysis.assembly.primer_rubric import PrimerRubric

RUBRIC = PrimerRubric()


def _named(checks):
    return {c.name: c for c in checks}


# ── GC content ─────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("seq", "expected"),
    [
        ("ATATATATAT", False),  # 0% GC
        ("GCGCGCGCGC", False),  # 100% GC
        ("ATGCATGCAT", True),  # 50%
    ],
)
def test_gc_window(seq, expected):
    assert ps.check_gc_content(seq, RUBRIC).passed is expected


@pytest.mark.unit
def test_gc_window_is_inclusive_at_both_bounds():
    """40% and 60% themselves pass; the window is closed, not open."""
    assert ps.check_gc_content("GGGGAAAAAA", RUBRIC).passed is True  # exactly 40%
    assert ps.check_gc_content("GGGGGGAAAA", RUBRIC).passed is True  # exactly 60%
    assert ps.check_gc_content("GGGAAAAAAA", RUBRIC).passed is False  # 30%


@pytest.mark.unit
def test_gc_reports_its_observed_value_and_threshold():
    # ATGCATGCATGC: 6 of 12 bases are G or C.
    check = ps.check_gc_content("ATGCATGCATGC", RUBRIC)
    assert check.observed_value == pytest.approx(50.0)
    assert "40" in check.threshold and "60" in check.threshold


@pytest.mark.unit
def test_gc_is_skipped_rather_than_failed_when_there_is_nothing_to_measure():
    check = ps.check_gc_content("", RUBRIC)
    assert check.passed is None and check.skipped
    assert "No annealing region" in check.message


# ── 3' clamp ───────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("seq", "expected", "why"),
    [
        ("AAAAAAAAAATTTTT", False, "no G/C in the last 5"),
        ("AAAAAAAAAATTTTG", True, "one G/C"),
        ("AAAAAAAAAAGCGCG", False, "five G/C exceeds the cap"),
        ("AAAAAAAAAATTGCG", True, "three G/C is the cap"),
    ],
)
def test_three_prime_clamp(seq, expected, why):
    assert ps.check_three_prime_clamp(seq, RUBRIC).passed is expected, why


@pytest.mark.unit
def test_clamp_is_skipped_when_shorter_than_the_window():
    check = ps.check_three_prime_clamp("GC", RUBRIC)
    assert check.passed is None
    assert "shorter than" in check.message


# ── Poly-X runs ────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("seq", "expected"),
    [("ACGTACGTACGT", True), ("ACGTAAAACGTA", True), ("ACGTAAAAACGT", False)],
)
def test_poly_run(seq, expected):
    assert ps.check_poly_run(seq, RUBRIC).passed is expected


@pytest.mark.unit
def test_longest_homopolymer_reports_length_and_base():
    assert ps.longest_homopolymer("ACGGGGTA") == (4, "G")
    assert ps.longest_homopolymer("") == (0, "")


# ── Pair Tm match ──────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("fwd", "rev", "expected"), [(60.0, 62.0, True), (60.0, 65.0, True), (60.0, 66.0, False)]
)
def test_pair_tm_tolerance(fwd, rev, expected):
    assert ps.check_pair_tm(fwd, rev, RUBRIC).passed is expected


@pytest.mark.unit
def test_pair_tm_skipped_when_a_value_is_missing():
    assert ps.check_pair_tm(60.0, None, RUBRIC).passed is None


# ── Product size ───────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("size", "expected"), [(99, False), (100, True), (3000, True), (3001, False)]
)
def test_product_size_bounds(size, expected):
    assert ps.check_product_size(size, RUBRIC).passed is expected


@pytest.mark.unit
def test_product_size_skipped_without_positions():
    check = ps.check_product_size(None, RUBRIC)
    assert check.passed is None
    assert "without both binding positions" in check.message


# ── Template uniqueness ────────────────────────────────────────────────


@pytest.mark.unit
def test_unique_binding_sites_pass():
    template = "ATGCGTACGTTAGCACGTAGCTAGCATCGACTGACTGGGCCCTATATGGGCCCAAA"
    check = ps.check_template_uniqueness(template, template[:18], template[-18:])
    assert check.passed is True


@pytest.mark.unit
def test_a_repeated_binding_site_fails():
    """A primer matching twice has two places to start, and the product is
    then ambiguous — this is a correctness failure, not a warning.
    """
    motif = "ACGTACGTACGTACGTAC"
    template = motif + "TTTTTTTTTTTTTTTTTTTT" + motif
    check = ps.check_template_uniqueness(template, motif, "GGGGGGGGGGGGGGGGGG")
    assert check.passed is False
    assert check.detail["forward_sites"] == 2


@pytest.mark.unit
def test_template_uniqueness_skipped_without_a_template():
    check = ps.check_template_uniqueness(None, "ACGT", "ACGT")
    assert check.passed is None
    assert "No template supplied" in check.message


@pytest.mark.unit
def test_binding_sites_counts_both_strands():
    template = "AAAAGGGCCCTTTT"
    # GGGCCC is its own reverse complement: counted once, not twice.
    assert ps.count_binding_sites(template, "GGGCCC") == 1
    # A non-palindromic motif present only as the reverse complement.
    assert ps.count_binding_sites("AAAACCCTTT", "AAAGGGTTTT") == 1


# ── Annealing region vs 5' tail ────────────────────────────────────────


@pytest.mark.unit
def test_gc_excludes_the_restriction_tail():
    """The original defect: a tail dragged GC toward 50% and masked a failure.

    The annealing region here is 0% GC. Judged whole, the GAATTC tail lifts it
    to 27% — still a fail, but a different number, and with a GC-rich tail it
    would have passed outright.
    """
    anneal = "ATATATATATATATAT"
    full = "GAATTC" + anneal

    assert ps.annealing_region(full, "GAATTC") == anneal
    assert ps.gc_percent(anneal) == pytest.approx(0.0)
    assert ps.gc_percent(full) > 0.0

    checks = _named(ps.screen_primer(full, "GAATTC", RUBRIC))
    assert checks["gc_content"].observed_value == pytest.approx(0.0)


@pytest.mark.unit
def test_a_gc_rich_tail_cannot_rescue_an_at_rich_primer():
    """Direct regression on the defect: judged whole this passes, and it must not."""
    anneal = "ATATATATATATATATAT"  # 0% GC
    full = "GGGCCCGGGCCC" + anneal  # whole oligo is 40% GC — inside the window
    assert 40.0 <= ps.gc_percent(full) <= 60.0, "fixture must pass if judged whole"

    checks = _named(ps.screen_primer(full, "GGGCCCGGGCCC", RUBRIC))
    assert checks["gc_content"].passed is False


@pytest.mark.unit
def test_annealing_region_handles_a_tail_that_is_not_a_prefix():
    """A mismatched overhang is not silently trimmed by length."""
    assert ps.annealing_region("ACGTACGT", "GAATTC") == "ACGTACGT"
    assert ps.annealing_region("ACGTACGT", "") == "ACGTACGT"


@pytest.mark.unit
def test_structure_checks_use_the_full_oligo():
    """A 5' tail still folds and dimerises even though it does not anneal."""
    anneal = "ATATATATATATAT"
    full = "GGGGCCCC" + anneal
    checks = _named(ps.screen_primer(full, "GGGGCCCC", RUBRIC))
    # The tail is self-complementary; screening the annealing region alone
    # would miss it entirely.
    assert checks["hairpin"].observed_value is not None
    assert checks["hairpin"].observed_value < 0.0


# ── Composition of a full screen ───────────────────────────────────────


@pytest.mark.unit
def test_screen_primer_runs_every_single_check():
    checks = ps.screen_primer("ATGCATGCATGCATGCAT", "", RUBRIC)
    assert [c.name for c in checks] == list(ps.SINGLE_CHECKS)


@pytest.mark.unit
def test_screen_pair_runs_every_pair_check():
    checks = ps.screen_pair("ATGCATGCATGCAT", "GCATGCATGCATGC", 60.0, 60.0)
    assert [c.name for c in checks] == list(ps.PAIR_CHECKS)


@pytest.mark.unit
def test_no_check_is_ever_dropped_even_when_unevaluable():
    """Missing inputs must still yield a full list, with reasons."""
    checks = ps.screen_pair("", "", None, None)
    assert len(checks) == len(ps.PAIR_CHECKS)
    assert all(c.message for c in checks if c.skipped)


# ── Verdict and ranking ────────────────────────────────────────────────


@pytest.mark.unit
def test_an_incomplete_screen_is_not_reported_as_a_pass():
    """A skipped check must not read as a clean result to a student."""
    checks = [
        ps.RubricCheck("a", True, "ok"),
        ps.RubricCheck("b", None, "could not run"),
    ]
    assert ps.summarise(checks)["verdict"] == "incomplete"


@pytest.mark.unit
def test_verdicts():
    assert ps.summarise([ps.RubricCheck("a", True, "")])["verdict"] == "pass"
    summary = ps.summarise([ps.RubricCheck("a", False, ""), ps.RubricCheck("b", True, "")])
    assert summary["verdict"] == "fail"
    assert summary["failed_names"] == ["a"]


@pytest.mark.unit
def test_score_ignores_skipped_checks():
    """A candidate is not punished for a check the caller could not supply."""
    checks = [
        ps.RubricCheck("a", True, ""),
        ps.RubricCheck("b", True, ""),
        ps.RubricCheck("c", None, ""),
    ]
    assert ps.score(checks) == pytest.approx(1.0)
    assert ps.score([ps.RubricCheck("a", None, "")]) == 0.0


@pytest.mark.unit
def test_check_round_trips_through_dict():
    original = ps.check_gc_content("ATGCATGCAT", RUBRIC)
    assert ps.RubricCheck.from_dict(original.to_dict()) == original


@pytest.mark.unit
def test_every_check_carries_its_numbers_for_the_ui():
    """A view must be able to render "52.4% (40-60%)" without knowing the rule."""
    for check in ps.screen_primer("ATGCATGCATGCATGCAT", "", RUBRIC):
        assert check.threshold, f"{check.name} has no threshold text"
        assert check.message, f"{check.name} has no message"
        if check.passed is not None:
            assert check.observed_value is not None, f"{check.name} reports no value"


@pytest.mark.unit
def test_convention_thresholds_are_labelled_as_such():
    """The UI must be able to say a threshold is convention, not a finding."""
    checks = _named(ps.screen_primer("ATGCATGCATGCATGCAT", "", RUBRIC))
    assert checks["gc_content"].provenance == "convention"

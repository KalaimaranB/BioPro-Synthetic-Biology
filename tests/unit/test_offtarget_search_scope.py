"""No surface may claim an off-target result wider than the search performed.

Audit finding C-2(a). ``find_grna_candidates`` scored off-targets against the
user's own pasted target sequence while passing it to a parameter named
``reference_genome``; the view then reported "No significant off-target
mismatch sites detected" beside a score of 100.0.

For a 1 kb insert that says only that the guide does not match twice within
that 1 kb. The E. coli genome is ~4.6 Mb, so a 20-mer has roughly 4,600 times
more opportunity to find a near-match there. Every other finding in that audit
produced a wrong number; this one produced an unsupported **safety claim**,
which a student could read as clearance to transform a strain.

These tests pin the claim, not the arithmetic. The scoring heuristic is
deliberately untouched -- it is already honest about being "CFD-style ... (not
the CFD matrix)".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from karcytics_plugins.synthetic_biology.analysis.citations import crispr_step
from karcytics_plugins.synthetic_biology.analysis.crispr import off_target_scope
from karcytics_plugins.synthetic_biology.analysis.crispr.grna_designer import (
    CRISPRDesignEngine,
)
from karcytics_plugins.synthetic_biology.analysis.models.domain import gRNACandidate

#: A short insert: exactly the case in which "no off-targets" is least
#: supportable, and the case the demo and the course materials use.
SHORT_TARGET = (
    "ATGAGTAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTT"
    "AATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATACGGAAAACTTACCCTT"
)

#: Words that assert an absolute or genome-wide result. None of them may appear
#: in any text shown for a search of one submitted sequence.
FORBIDDEN = (
    "no significant off-target",
    "genome-wide",
    "genome wide",
    "no off-targets",
    "no off-target sites",
    "specific",
    "safe",
    "clear to proceed",
)


def _candidates(sequence=SHORT_TARGET):
    found = CRISPRDesignEngine.find_grna_candidates(sequence, pam_type="SpCas9 (NGG)")
    assert found, "the fixture must yield at least one candidate"
    return found


#: Words that negate a following claim. "This is **not** a genome-wide search"
#: must pass; "a genome-wide search found nothing" must not.
_NEGATORS = ("not ", "no ", "never ", "n't ", "cannot ", "do not ", "nor ")


def _assert_no_absolute_claim(text, where):
    """Fail on an *affirmative* absolute claim, allowing one that is denied.

    The distinction is the whole point of this task: the caveat has to be able
    to say "this is not a genome-wide search" while nothing may say a
    genome-wide search happened. So each forbidden phrase is only a failure
    when the words just before it do not negate it.
    """
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text.lower()):
        for phrase in FORBIDDEN:
            at = sentence.find(phrase)
            if at == -1:
                continue
            # Negation is sentence-scoped: "Do not treat this as evidence that
            # a guide is specific" puts the negator well before the phrase.
            negated = any(neg in sentence[:at] for neg in _NEGATORS)
            assert negated, (
                f"{where} claims more than was searched: {phrase!r} appears "
                f"un-negated in {sentence!r}"
            )


# ── The claim, for a guide with no second match in a short sequence ────


@pytest.mark.unit
def test_a_guide_with_no_second_match_makes_no_absolute_claim():
    """The headline must name the search space, not declare the guide clean."""
    candidate = next(c for c in _candidates() if not c.off_target_hits)

    text = off_target_scope.headline(candidate)

    assert "No additional matches" in text
    assert "within the submitted sequence" in text
    _assert_no_absolute_claim(text, "the headline")


@pytest.mark.unit
def test_every_reported_line_states_the_search_space():
    candidate = next(c for c in _candidates() if not c.off_target_hits)

    lines = off_target_scope.summary_lines(candidate)

    assert any("submitted sequence" in line for line in lines)
    assert any("not a genome-wide off-target search" in line for line in lines)
    for line in lines:
        _assert_no_absolute_claim(line, "a summary line")


@pytest.mark.unit
def test_the_caveat_tells_the_student_what_to_do_instead():
    """A limitation with no remedy just moves the problem."""
    text = off_target_scope.caveat()

    assert "not a genome-wide" in text
    assert "reference genome" in text, "say what would actually answer the question"
    assert "before ordering" in text


# ── The search space is pinned to what was really searched ─────────────


@pytest.mark.unit
@pytest.mark.parametrize("length", [100, 132, 500])
def test_the_named_search_space_matches_the_sequence_length(length):
    """The number quoted must be the length of the sequence actually searched."""
    sequence = (SHORT_TARGET * 10)[:length]

    for candidate in _candidates(sequence):
        assert candidate.off_target_search_bp == length
        assert candidate.off_target_search_space == "submitted sequence"
        assert f"{length:,} bp" in off_target_scope.space_label(candidate)
        assert f"{length:,} bp" in off_target_scope.headline(candidate)


@pytest.mark.unit
def test_the_search_space_is_the_target_not_some_wider_default():
    """A 132 bp target must not be reported as anything larger."""
    candidate = _candidates()[0]

    assert candidate.off_target_search_bp == len(SHORT_TARGET)
    assert candidate.off_target_search_bp < 5000, (
        "if this ever reports megabases, a genome really is being searched and "
        "the wording in off_target_scope must be revisited (C-2(b))"
    )


@pytest.mark.unit
def test_an_unscored_candidate_does_not_look_searched():
    """A placeholder 100.0 must not read as a clean result.

    The engine seeds off_target_score=100.0 before the scorer runs. With no
    search space recorded, nothing may imply a search happened.
    """
    unscored = gRNACandidate(
        id="x",
        target_id="t",
        protospacer="ACTGGAGTTGTCCCAATTCT",
        pam="TGG",
        strand=1,
        start=0,
        end=23,
        gc_content=50.0,
        efficiency_score=80.0,
        off_target_score=100.0,
    )

    assert off_target_scope.searched_span(unscored) == 0
    assert off_target_scope.space_label(unscored) == "submitted sequence", (
        "with no span recorded it must not quote a length it does not have"
    )
    assert "bp" not in off_target_scope.space_label(unscored)


# ── The score reads as what it is ──────────────────────────────────────


@pytest.mark.unit
def test_a_perfect_score_is_shown_with_what_produced_it():
    """A bare "100%" read as a clean bill of health."""
    candidate = next(c for c in _candidates() if not c.off_target_hits)

    text = off_target_scope.cell_text(candidate)

    assert text == "100% (0 hit(s))"
    assert "0 hit(s)" in text, "the number must show what it is made of"


@pytest.mark.unit
def test_the_column_heading_names_the_search_space():
    heading = off_target_scope.column_heading()

    assert "submitted sequence" in heading
    _assert_no_absolute_claim(heading, "the column heading")


@pytest.mark.unit
def test_the_clear_cut_off_lives_in_analysis_and_is_labelled_a_convention():
    """It decides a colour, so it must not masquerade as a safety threshold."""
    assert off_target_scope.CLEAR_WITHIN_SEARCH_SCORE == 90.0
    assert off_target_scope.is_clear_within_search(100.0)
    assert off_target_scope.is_clear_within_search(90.0)
    assert not off_target_scope.is_clear_within_search(89.9)

    entry = off_target_scope.PROVENANCE["clear_score"]
    assert entry.kind == "convention", "not a published criterion"
    assert entry.mechanism == (), "and it cites nothing, deliberately"
    assert "not a published specificity criterion" in entry.explanation


@pytest.mark.unit
def test_the_search_space_limitation_is_recorded_as_a_convention():
    entry = off_target_scope.PROVENANCE["search_space"]

    assert entry.kind == "convention"
    assert "not a genome-wide search" in entry.explanation
    assert "cannot be read as evidence" in entry.explanation


# ── The scorer's own contract ──────────────────────────────────────────


@pytest.mark.unit
def test_the_scorer_parameter_says_what_is_passed_to_it():
    """The old name `reference_genome` was the root of the error."""
    import inspect

    params = inspect.signature(CRISPRDesignEngine.score_off_targets).parameters

    assert "searched_sequence" in params
    assert "reference_genome" not in params, (
        "the name told every later reader a genome had been searched"
    )


@pytest.mark.unit
def test_the_scorer_still_finds_a_real_near_match():
    """The search space changed; the mathematics did not."""
    candidate = gRNACandidate(
        id="c1",
        target_id="t1",
        protospacer="ACTGGAGTTGTCCCAATTCT",
        pam="TGG",
        strand=1,
        start=0,
        end=23,
        gc_content=50.0,
        efficiency_score=80.0,
        off_target_score=100.0,
    )
    # One mismatch at position 18, followed by a valid NGG PAM.
    searched = "AAAAAAAAAAAAAAAAACTGGAGTTGTCCCAATTATCGGAAAAAAAAAAAAAAAA"

    score = CRISPRDesignEngine.score_off_targets(candidate, searched_sequence=searched)

    assert score < 100.0
    assert len(candidate.off_target_hits) == 1
    assert off_target_scope.headline(candidate).startswith("1 additional near-match")


# ── The methods write-up ───────────────────────────────────────────────


@pytest.mark.unit
def test_the_methods_entry_states_the_off_target_search_space():
    """An exported methods section had said nothing about off-targets at all."""
    entry = crispr_step("SpCas9 (NGG)", 20, len(SHORT_TARGET), 11)

    description = entry["description"]
    assert "no reference genome was loaded" in description
    assert "do not" in description and "genome-wide specificity" in description
    assert f"{len(SHORT_TARGET):,} bp submitted sequence" in description
    assert entry["parameters"]["off-target search space"] == (
        f"submitted sequence, {len(SHORT_TARGET):,} bp"
    )


# ── No surface anywhere may carry the old wording ──────────────────────


@pytest.mark.unit
def test_no_source_file_contains_the_retired_absolute_claim():
    """Step 4's requirement: a fixed dialog beside a stale column is worse.

    Scans the shipped source rather than one widget, because the defect was
    not in any single place -- it was a sentence and a bare score repeated
    across a table column, a detail inspector, a demo card and a methods
    entry. A grep is the only check that fails when a fifth surface appears.
    """
    retired = "No significant off-target mismatch sites detected"
    # off_target_scope.py quotes the retired sentence in its module docstring
    # on purpose: it is the module that exists to explain why that sentence
    # was wrong, and losing that record would invite the defect back.
    documents_the_history = {"off_target_scope.py"}
    offenders = [
        path
        for path in Path("src").rglob("*.py")
        if path.name not in documents_the_history
        and retired.lower() in path.read_text(encoding="utf-8").lower()
    ]

    assert not offenders, (
        f"the retired absolute claim is still present in: {[str(p) for p in offenders]}"
    )


@pytest.mark.unit
def test_the_crispr_view_states_its_search_space_in_source():
    """The view must get its wording from the analysis layer, not its own."""
    source = Path("src/karcytics_plugins/synthetic_biology/ui/views/crispr_view.py").read_text(
        encoding="utf-8"
    )

    assert "off_target_scope.column_heading()" in source
    assert "off_target_scope.caveat()" in source
    assert "off_target_scope.headline(cand)" in source
    assert ">= 90.0" not in source, (
        "the clear/not-clear cut-off is a threshold and belongs in analysis/"
    )


@pytest.mark.unit
def test_the_guard_would_have_caught_the_original_wording():
    """A self-check: the helper above must reject the sentence that shipped."""
    with pytest.raises(AssertionError):
        _assert_no_absolute_claim(
            "No significant off-target mismatch sites detected.", "the old inspector"
        )
    with pytest.raises(AssertionError):
        _assert_no_absolute_claim("A genome-wide search found no hits.", "a hypothetical")

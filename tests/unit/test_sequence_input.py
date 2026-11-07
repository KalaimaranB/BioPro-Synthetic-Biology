"""Validation at the engine boundary: what is accepted, converted, or refused.

The defect this closes: a GenBank ORIGIN block, an mRNA sequence, or a
sequence containing N all produced a confident Tm and GC percentage. The
nearest-neighbour tables have no parameters for U or N, so those numbers were
fabricated — confidently wrong rather than obviously broken, which on a graded
deliverable is the worse failure.
"""

from __future__ import annotations

import pytest

from karcytics_plugins.synthetic_biology.analysis.assembly import amplification as amp
from karcytics_plugins.synthetic_biology.analysis.assembly import restriction as rst
from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
    VectorAssemblyEngine as V,
)
from karcytics_plugins.synthetic_biology.analysis.sequence_input import (
    SequenceRejectedError,
    clean_sequence,
    require_sequence,
    validate_region,
)

GOOD = "ATGAGTAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTT"


# ── Accepted unchanged ─────────────────────────────────────────────────


@pytest.mark.unit
def test_plain_dna_is_accepted():
    result = clean_sequence(GOOD)
    assert result.ok
    assert result.sequence == GOOD
    assert result.transformations == ()


@pytest.mark.unit
def test_case_is_normalised_and_reported():
    result = clean_sequence(GOOD.lower())
    assert result.ok
    assert result.sequence == GOOD
    assert any("upper case" in t for t in result.transformations)


# ── Transformed, and said so ───────────────────────────────────────────


@pytest.mark.unit
def test_fasta_header_and_line_breaks_are_handled():
    raw = ">gi|12345| GFP construct\nATGACGTACGTACGT\nACGTACGTACGTACGT"
    result = clean_sequence(raw)
    assert result.ok
    assert result.sequence == "ATGACGTACGTACGTACGTACGTACGTACGT"
    assert any("FASTA header" in t for t in result.transformations)
    assert any("whitespace" in t for t in result.transformations)


@pytest.mark.unit
def test_genbank_origin_coordinates_are_stripped_not_treated_as_bases():
    """The digits in an ORIGIN block are positions, not sequence."""
    raw = "        1 atgacgtacg tacgtacgta\n       21 cgtacgtacg tacgtacgta"
    result = clean_sequence(raw)
    assert result.ok
    assert result.sequence == "ATGACGTACGTACGTACGTACGTACGTACGTACGTACGTA"
    assert len(result.sequence) == 40, "two ORIGIN rows of 20 bases"
    assert "1" not in result.sequence and "2" not in result.sequence
    assert any("ORIGIN" in t for t in result.transformations)


@pytest.mark.unit
def test_rna_is_converted_to_dna_and_the_conversion_is_reported():
    """Never silent: the caller must be able to say it converted RNA."""
    result = clean_sequence("AUGACGUACGUACGUACGU")
    assert result.ok
    assert result.sequence == "ATGACGTACGTACGTACGT"
    assert "U" not in result.sequence
    assert any("RNA to DNA" in t for t in result.transformations)


@pytest.mark.unit
def test_mixed_u_and_t_is_refused_rather_than_guessed():
    """Both bases present means it is neither DNA nor RNA, so do not convert."""
    result = clean_sequence("AUGACGTACGT")
    assert not result.ok
    assert result.refusals[0].code == "mixed_u_t"


# ── Refused, by name ───────────────────────────────────────────────────


@pytest.mark.unit
def test_ambiguity_codes_are_refused_with_a_reason():
    result = clean_sequence("ATGACGTACGTNNNNNACGTA")
    assert not result.ok
    assert result.sequence == "", "a refused sequence must not leak a partial result"
    issue = result.refusals[0]
    assert issue.code == "ambiguity"
    assert "N (any base)" in issue.message
    assert "no single melting temperature" in issue.message


@pytest.mark.unit
@pytest.mark.parametrize("code", ["R", "Y", "S", "W", "K", "M", "B", "D", "H", "V"])
def test_every_iupac_ambiguity_code_is_refused(code):
    assert not clean_sequence(f"ATGACGT{code}ACGTACGT").ok


@pytest.mark.unit
def test_stray_digits_are_refused():
    result = clean_sequence("ATG123ACGTACGT")
    assert not result.ok
    assert result.refusals[0].code == "digits"


@pytest.mark.unit
def test_empty_input_is_refused():
    for raw in ("", "   ", None):
        result = clean_sequence(raw)
        assert not result.ok
        assert result.refusals[0].code == "empty"


@pytest.mark.unit
def test_protein_pasted_by_mistake_is_refused():
    result = clean_sequence("MKVLATGSYR")
    assert not result.ok


@pytest.mark.unit
def test_nothing_is_ever_silently_dropped():
    """Any unrecognised character must surface, never be filtered away.

    This is the precedent being replaced: sequence_predictor used to do
    ``"".join(c for c in q.upper() if c in "ACGTN")``.
    """
    result = clean_sequence("ATGACGT*ACGT")
    assert not result.ok
    assert "'*'" in result.refusals[0].message


# ── The engines refuse too, not just the helper ────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    "bad",
    [
        "ATGACGTACGTNNNNNACGTACGTACGTACGTACGTACG",
        "ATGACGT*ACGTACGTACGTACGTACGTACGTACGTACG",
        "ATG123ACGTACGTACGTACGTACGTACGTACGTACGTA",
        "",
    ],
)
def test_primer_design_refuses_bad_sequences(bad):
    """Previously each of these returned a primer with a fabricated Tm."""
    with pytest.raises((SequenceRejectedError, ValueError)):
        V.design_primers(bad)


@pytest.mark.unit
def test_rna_is_designed_against_after_conversion_not_refused():
    """RNA is a transformation, not a refusal: convert it and say so."""
    rna = "AUG" + GOOD[3:].replace("T", "U")
    fwd, _rev = V.design_primers(rna)
    assert "U" not in fwd.sequence, "the primer must be DNA"
    assert fwd.calculated_tm > 0


@pytest.mark.unit
def test_amplify_refuses_a_bad_template():
    with pytest.raises(SequenceRejectedError):
        amp.amplify("ATGNNNNACGT" * 6, GOOD[:20], GOOD[:20])


@pytest.mark.unit
def test_amplify_refuses_a_bad_primer():
    with pytest.raises(SequenceRejectedError):
        amp.amplify(GOOD, "ATGNNNNACGTACGTACGTA", GOOD[:20])


@pytest.mark.unit
def test_digest_refuses_an_ambiguous_sequence():
    with pytest.raises(SequenceRejectedError):
        rst.digest("AAAGAATTCNNNNAAA", "EcoRI")


@pytest.mark.unit
def test_a_refusal_names_the_field_that_was_wrong():
    """'Forward 5' tail' not 'Sequence' — a student has four inputs."""
    with pytest.raises(SequenceRejectedError) as excinfo:
        V.design_primers(GOOD, fwd_overhang="GAANNC")
    assert "Forward 5' tail" in str(excinfo.value)


@pytest.mark.unit
def test_valid_input_still_works_through_the_engines():
    """Validation must not break the normal path."""
    fwd, rev = V.design_primers(GOOD.lower())
    assert fwd.sequence and rev.sequence
    assert amp.amplify(GOOD, fwd.sequence, rev.sequence).outcome in (
        amp.PRODUCT,
        amp.MULTIPLE_PRODUCTS,
        amp.NO_PRODUCT,
    )


@pytest.mark.unit
def test_require_sequence_carries_the_structured_result_on_the_exception():
    with pytest.raises(SequenceRejectedError) as excinfo:
        require_sequence("ATGNNN")
    assert excinfo.value.issues
    assert excinfo.value.result.original_length == 6


# ── Coordinate validation ──────────────────────────────────────────────


@pytest.mark.unit
def test_an_inverted_range_is_refused_not_widened():
    """from=600 to=400 used to silently amplify the whole template."""
    selection = validate_region(600, 400, 1002)
    assert not selection.ok
    assert selection.refusals[0].code == "inverted"
    assert "not read as the whole" in selection.refusals[0].message


@pytest.mark.unit
def test_an_empty_range_is_refused():
    selection = validate_region(500, 500, 1002)
    assert not selection.ok
    assert selection.refusals[0].code == "empty_region"


@pytest.mark.unit
def test_a_range_beyond_the_template_is_refused():
    assert not validate_region(0, 5000, 1002).ok
    assert not validate_region(-1, 100, 1002).ok


@pytest.mark.unit
def test_a_valid_range_is_accepted_with_its_length():
    selection = validate_region(100, 400, 1002)
    assert selection.ok
    assert selection.length == 300
    assert "300 bp" in selection.summary()


# ── Amplicon cap ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_a_repetitive_template_truncates_instead_of_exploding():
    """(AC)x500 built 115,921 full-sequence amplicons before this cap."""
    repeat = "AC" * 500
    reverse = "".join(
        {"A": "T", "T": "A", "G": "C", "C": "G"}[b] for b in reversed(repeat[930:950])
    )

    result = amp.amplify(repeat, repeat[50:70], reverse)

    assert result.truncated is True
    assert len(result.amplicons) <= amp.DEFAULT_MAX_AMPLICONS
    assert result.amplicons, "truncation must not mean dropping everything"


@pytest.mark.unit
def test_truncation_explains_what_it_means_about_the_template():
    """A student hitting this has learned something about repetitive DNA."""
    repeat = "AC" * 500
    reverse = "".join(
        {"A": "T", "T": "A", "G": "C", "C": "G"}[b] for b in reversed(repeat[930:950])
    )
    note = amp.amplify(repeat, repeat[50:70], reverse).notes[0]

    assert "repetitive" in note
    assert "sample, not the full set" in note
    assert "binding sites" in note


@pytest.mark.unit
def test_a_normal_template_is_never_truncated():
    reverse = "".join({"A": "T", "T": "A", "G": "C", "C": "G"}[b] for b in reversed(GOOD[-20:]))
    result = amp.amplify(GOOD, GOOD[:20], reverse)
    assert result.truncated is False
    assert result.diagnostics["max_amplicons"] == amp.DEFAULT_MAX_AMPLICONS

"""The digest engine, checked against hand arithmetic and against Biopython.

Two independent references, as in phase 1's thermodynamics tests:

1. **Hand-computed positions.** ``DIGEST_TEMPLATE`` has its sites at offsets
   written out in the fixture, so the expected cut indices are arithmetic a
   reader can follow.
2. **Biopython's own searcher and catalyse().** Our fragments must equal what
   ``enzyme.catalyse()`` produces on the same sequence. That is the check that
   would catch a coordinate-convention error, which is otherwise invisible
   because wrong fragment lengths still look plausible.
"""

from __future__ import annotations

import pytest
from Bio.Restriction import BsaI, EcoRI, HindIII, PstI, SmaI
from Bio.Seq import Seq

from karcytics_plugins.synthetic_biology.analysis.assembly import restriction as rst

from .sequence_fixtures import (
    BSAI_EXPECTED_OVERHANG,
    BSAI_TEMPLATE,
    CIRCULAR_ORIGIN_SPANNING,
    DIGEST_TEMPLATE,
)

# ── Reference 1: hand-computed positions ───────────────────────────────


@pytest.mark.unit
def test_site_positions_match_hand_arithmetic():
    """DIGEST_TEMPLATE = AAA GAATTC AAAA AAGCTT AAAA GAATTC AAA.

    EcoRI recognition sites therefore start at 0-based 3 and 23, and EcoRI
    cuts G^AATTC, so the top-strand cut is one base into each site: 4 and 24.
    """
    sites = rst.find_sites(DIGEST_TEMPLATE, "EcoRI")
    assert [s.site_start for s in sites] == [3, 23]
    assert [s.top_cut for s in sites] == [4, 24]
    # ovhg -4, so the bottom strand is cut four bases further along.
    assert [s.bottom_cut for s in sites] == [8, 28]
    assert {s.overhang for s in sites} == {"AATT"}


@pytest.mark.unit
def test_overhang_polarity_per_enzyme():
    """A 5' cutter, a 3' cutter and a blunt cutter are each described correctly."""
    ecori = rst.find_sites("AAAGAATTCAAA", "EcoRI")[0]
    assert ecori.overhang_type == rst.FIVE_PRIME
    assert ecori.overhang == "AATT"
    assert ecori.bottom_cut > ecori.top_cut

    psti = rst.find_sites("AACTGCAGTTTTTT", "PstI")[0]
    assert psti.overhang_type == rst.THREE_PRIME
    assert psti.overhang == "TGCA"
    assert psti.bottom_cut < psti.top_cut

    smai = rst.find_sites("AACCCGGGTTTTTT", "SmaI")[0]
    assert smai.overhang_type == rst.BLUNT
    assert smai.overhang == ""
    assert smai.bottom_cut == smai.top_cut
    assert smai.is_blunt


# ── Reference 2: Biopython ─────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize(
    ("sequence", "enzyme"),
    [
        ("AAAGAATTCAAAAAGAATTCTTT", EcoRI),
        (BSAI_TEMPLATE, BsaI),
        ("AACCCGGGTTTTTT", SmaI),
        ("AACTGCAGTTTTTT", PstI),
        (DIGEST_TEMPLATE, HindIII),
    ],
)
def test_fragments_match_biopython_catalyse(sequence, enzyme):
    """Our fragment sequences must be exactly Biopython's.

    Not approximate: both split the same string at the same cut, so any
    difference is a coordinate bug.
    """
    mine = [f.sequence for f in rst.digest(sequence, str(enzyme)).fragments]
    theirs = [str(x) for x in enzyme.catalyse(Seq(sequence))]
    assert mine == theirs


@pytest.mark.unit
@pytest.mark.parametrize("sequence", [DIGEST_TEMPLATE, BSAI_TEMPLATE, "AAAGAATTCAAA"])
def test_site_positions_match_biopython_search(sequence):
    """Our 0-based cut indices are Biopython's 1-based positions minus one."""
    for enzyme in (EcoRI, HindIII, BsaI):
        mine = [s.top_cut for s in rst.find_sites(sequence, str(enzyme))]
        theirs = [p - 1 for p in enzyme.search(Seq(sequence))]
        assert mine == theirs, str(enzyme)


@pytest.mark.unit
def test_fragments_reassemble_into_the_template():
    """Nothing is lost or duplicated by cutting."""
    result = rst.digest(DIGEST_TEMPLATE, ["EcoRI", "HindIII"])
    assert "".join(f.sequence for f in result.fragments) == DIGEST_TEMPLATE
    assert sum(result.fragment_lengths) == len(DIGEST_TEMPLATE)


# ── Type IIS ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_type_iis_overhang_comes_from_the_template_not_the_enzyme():
    """BsaI cuts outside its recognition site, so the overhang is sequence-dependent.

    This is the basis of Golden Gate assembly. A table of enzyme -> overhang
    would get it wrong for every Type IIS enzyme, and the fragment lengths
    would still look right.
    """
    site = rst.find_sites(BSAI_TEMPLATE, "BsaI")[0]
    assert site.overhang == BSAI_EXPECTED_OVERHANG
    # The overhang is downstream of the recognition sequence, not inside it.
    assert site.site_start == 2
    assert BSAI_TEMPLATE[2:8] == "GGTCTC"
    assert site.top_cut == 9
    assert BSAI_TEMPLATE[site.top_cut : site.bottom_cut] == BSAI_EXPECTED_OVERHANG


@pytest.mark.unit
def test_type_iis_overhang_changes_with_the_template():
    """The same enzyme, a different downstream sequence, a different overhang."""
    # Both have GGTCTC at 0-based 2-7 and are cut after 0-based 8, so the
    # overhang is sequence[9:13] in each case: GGGG here, AAAA there.
    a = rst.find_sites("TTGGTCTCAGGGGTTTTTTTT", "BsaI")[0]
    b = rst.find_sites("TTGGTCTCAAAAATTTTTTTT", "BsaI")[0]
    assert a.overhang == "GGGG"
    assert b.overhang == "AAAA"
    assert a.overhang != b.overhang


@pytest.mark.unit
def test_cuts_outside_site_distinguishes_type_iis():
    assert rst.enzyme_info("BsaI")["cuts_outside_site"] is True
    assert rst.enzyme_info("EcoRI")["cuts_outside_site"] is False


# ── Circular ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_a_site_spanning_the_origin_is_found_only_when_circular():
    """The fixture holds GAATTC only across the join of its two ends."""
    assert rst.find_sites(CIRCULAR_ORIGIN_SPANNING, "EcoRI", circular=False) == ()

    sites = rst.find_sites(CIRCULAR_ORIGIN_SPANNING, "EcoRI", circular=True)
    assert len(sites) == 1
    assert sites[0].spans_origin is True
    assert sites[0].site_start == 14  # the trailing G


@pytest.mark.unit
def test_one_cut_on_a_circle_gives_one_full_length_fragment():
    result = rst.digest(CIRCULAR_ORIGIN_SPANNING, "EcoRI", circular=True)
    assert result.cut
    assert result.fragment_lengths == (len(CIRCULAR_ORIGIN_SPANNING),)


@pytest.mark.unit
def test_n_cuts_on_a_circle_give_n_fragments_conserving_length():
    """A linear template of n cuts gives n+1 fragments; a circle gives n."""
    sequence = "AAAGAATTCAAAAAGAATTCTTT"
    circular = rst.digest(sequence, "EcoRI", circular=True)
    linear = rst.digest(sequence, "EcoRI", circular=False)

    assert len(circular.sites) == 2
    assert len(circular.fragments) == 2
    assert len(linear.fragments) == 3
    assert sum(circular.fragment_lengths) == len(sequence)
    assert sum(linear.fragment_lengths) == len(sequence)


@pytest.mark.unit
def test_the_fragment_running_through_the_origin_is_marked():
    result = rst.digest("AAAGAATTCAAAAAGAATTCTTT", "EcoRI", circular=True)
    assert [f.wraps_origin for f in result.fragments] == [False, True]


# ── Single, double and no digest ───────────────────────────────────────


@pytest.mark.unit
def test_single_digest():
    result = rst.digest(DIGEST_TEMPLATE, "EcoRI")
    assert result.enzymes == ("EcoRI",)
    assert len(result.sites) == 2
    assert len(result.fragments) == 3


@pytest.mark.unit
def test_double_digest_combines_both_enzymes_in_position_order():
    result = rst.double_digest(DIGEST_TEMPLATE, "EcoRI", "HindIII")
    assert result.enzymes == ("EcoRI", "HindIII")
    assert [s.enzyme for s in result.sites] == ["EcoRI", "HindIII", "EcoRI"]
    assert [s.top_cut for s in result.sites] == sorted(s.top_cut for s in result.sites)
    assert len(result.fragments) == 4


@pytest.mark.unit
def test_double_digest_gives_more_fragments_than_either_alone():
    single = rst.digest(DIGEST_TEMPLATE, "EcoRI")
    double = rst.double_digest(DIGEST_TEMPLATE, "EcoRI", "HindIII")
    assert len(double.fragments) > len(single.fragments)


@pytest.mark.unit
def test_no_sites_is_a_result_not_an_error():
    """An uncut template is a legitimate experimental outcome."""
    result = rst.digest("AAAAAAAAAAAATTTT", "EcoRI")
    assert result.cut is False
    assert result.sites == ()
    assert len(result.fragments) == 1
    assert result.fragments[0].sequence == "AAAAAAAAAAAATTTT"
    assert result.fragments[0].left_enzyme is None
    assert result.fragments[0].right_enzyme is None


@pytest.mark.unit
def test_an_empty_template_is_handled():
    result = rst.digest("", "EcoRI")
    assert result.cut is False
    assert result.fragments == ()


@pytest.mark.unit
def test_fragment_ends_record_the_enzyme_that_made_them():
    """Ligation depends on end chemistry, so each end names its enzyme."""
    result = rst.double_digest(DIGEST_TEMPLATE, "EcoRI", "HindIII")
    first, second, third, fourth = result.fragments

    assert first.left_enzyme is None  # the template's own end
    assert first.right_enzyme == "EcoRI"
    assert second.left_enzyme == "EcoRI"
    assert second.right_enzyme == "HindIII"
    assert third.left_enzyme == "HindIII"
    assert fourth.right_enzyme is None
    assert second.left_overhang == "AATT"
    assert second.right_overhang == "AGCT"


# ── Internal sites: the course-critical check ──────────────────────────


@pytest.mark.unit
def test_sites_in_region_finds_only_cuts_inside_the_window():
    """Warning that a tail enzyme also cuts the insert is the point of this."""
    inside = rst.sites_in_region(DIGEST_TEMPLATE, "EcoRI", 0, 20)
    assert [s.top_cut for s in inside] == [4]

    later = rst.sites_in_region(DIGEST_TEMPLATE, "EcoRI", 20, len(DIGEST_TEMPLATE))
    assert [s.top_cut for s in later] == [24]


@pytest.mark.unit
def test_sites_in_region_is_empty_when_the_region_is_clean():
    assert rst.sites_in_region(DIGEST_TEMPLATE, "EcoRI", 9, 23) == ()


# ── Enzyme lookup ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_enzyme_info_reports_rebase_geometry():
    info = rst.enzyme_info("EcoRI")
    assert info["site"] == "GAATTC"
    assert info["overhang_length"] == 4
    assert info["overhang_type"] == rst.FIVE_PRIME
    assert info["elucidate"] == "G^AATT_C"


@pytest.mark.unit
def test_an_unknown_enzyme_says_so_clearly():
    with pytest.raises(rst.UnknownEnzymeError, match="not in Biopython's REBASE"):
        rst.find_sites("AAAA", "NotAnEnzyme")


@pytest.mark.unit
def test_the_full_rebase_set_is_available():
    """Enough enzymes that nobody is tempted to hand-roll a table."""
    names = rst.available_enzymes()
    assert len(names) > 500
    for expected in ("EcoRI", "BsaI", "HindIII", "SmaI", "PstI", "BsmBI"):
        assert expected in names


@pytest.mark.unit
def test_enzymes_cutting_reports_counts_for_a_restricted_batch():
    from Bio.Restriction import RestrictionBatch

    found = rst.enzymes_cutting(
        DIGEST_TEMPLATE, batch=RestrictionBatch(["EcoRI", "HindIII", "SmaI"])
    )
    assert found == {"EcoRI": 2, "HindIII": 1}


# ── Stated limitations ─────────────────────────────────────────────────


@pytest.mark.unit
def test_limitations_are_declared_and_explained():
    """What the model cannot do has to be stated, not silently assumed."""
    names = {name for name, _ in rst.DIGEST_LIMITATIONS}
    assert {"methylation sensitivity", "star activity", "isoschizomers"} <= names
    for _, reason in rst.DIGEST_LIMITATIONS:
        assert reason.strip()


@pytest.mark.unit
def test_everything_reported_is_sourced_not_convention():
    """This engine makes no judgement calls, so it has no conventions."""
    assert rst.THRESHOLD_PROVENANCE
    for _field, (kind, explanation) in rst.THRESHOLD_PROVENANCE.items():
        assert kind == "sourced"
        assert explanation.strip()

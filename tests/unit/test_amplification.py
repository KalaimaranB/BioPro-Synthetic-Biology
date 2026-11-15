"""In-silico PCR: the product, and the failures that are the teaching content.

Every expected value here is hand-computable from the fixtures in
``sequence_fixtures``. The real pGFP-S12 template is not available; see that
module for where it drops in and why no stand-in sequence was invented.
"""

from __future__ import annotations

import pytest

from karcytics_plugins.synthetic_biology.analysis.assembly import amplification as amp
from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
    VectorAssemblyEngine,
)

from .sequence_fixtures import (
    DIMER_FORWARD,
    DIMER_REVERSE,
    ECORI_TAIL,
    HINDIII_TAIL,
    SYNTHETIC_ORF,
    SYNTHETIC_TEMPLATE,
    TEMPLATE_WITH_INTERNAL_ECORI,
    primers_for,
    repeated_site_template,
    reverse_complement,
)

FWD, REV = primers_for(SYNTHETIC_ORF)


# ── A known template gives a known product ─────────────────────────────


@pytest.mark.unit
def test_a_known_template_gives_the_expected_product():
    """The primers span the ORF exactly, so the product IS the ORF."""
    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV)

    assert result.outcome == amp.PRODUCT
    product = result.product
    assert product is not None
    assert product.length == len(SYNTHETIC_ORF)
    assert product.sequence == SYNTHETIC_ORF


@pytest.mark.unit
def test_product_gc_is_reported():
    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV)
    expected = 100.0 * (SYNTHETIC_ORF.count("G") + SYNTHETIC_ORF.count("C")) / len(SYNTHETIC_ORF)
    assert result.product.gc_percent == pytest.approx(expected)


@pytest.mark.unit
def test_both_primers_are_located_on_opposite_strands():
    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV)
    assert result.product.forward_site.strand == 1
    assert result.product.reverse_site.strand == -1
    # The forward primer's 3' end must lie upstream of the reverse primer's.
    assert (
        result.product.forward_site.three_prime_index
        < result.product.reverse_site.three_prime_index
    )


# ── Tails: in the length, out of the Tm ────────────────────────────────


@pytest.mark.unit
def test_tails_are_included_in_product_length():
    result = amp.amplify(
        SYNTHETIC_TEMPLATE,
        ECORI_TAIL + FWD,
        HINDIII_TAIL + REV,
        forward_tail=ECORI_TAIL,
        reverse_tail=HINDIII_TAIL,
    )
    assert result.outcome == amp.PRODUCT
    assert result.product.length == len(SYNTHETIC_ORF) + len(ECORI_TAIL) + len(HINDIII_TAIL)
    assert result.product.sequence.startswith(ECORI_TAIL)
    assert result.product.sequence.endswith(reverse_complement(HINDIII_TAIL))


@pytest.mark.unit
def test_tails_are_excluded_from_the_annealing_tm():
    """Phase 1 computes Tm on the binding region only. That must not regress."""
    tailed = amp.amplify(
        SYNTHETIC_TEMPLATE,
        ECORI_TAIL + FWD,
        HINDIII_TAIL + REV,
        forward_tail=ECORI_TAIL,
        reverse_tail=HINDIII_TAIL,
    )
    bare = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV)

    assert tailed.product.forward_site.annealing_tm == bare.product.forward_site.annealing_tm
    # And it is exactly phase 1's own number for the binding region.
    assert tailed.product.forward_site.annealing_tm == pytest.approx(
        VectorAssemblyEngine.calculate_tm(FWD)
    )
    assert tailed.product.forward_site.annealing_tm != pytest.approx(
        VectorAssemblyEngine.calculate_tm(ECORI_TAIL + FWD)
    )


@pytest.mark.unit
def test_a_mislabelled_tail_does_not_shorten_the_binding_region():
    """Only a tail the primer actually starts with is stripped."""
    assert amp.annealing_region(FWD, "GGGGGG") == FWD
    assert amp.annealing_region(ECORI_TAIL + FWD, ECORI_TAIL) == FWD


# ── The mismatch rule ──────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize("offset_from_three_prime", [0, 1, 2, 3, 4])
def test_a_mismatch_in_the_three_prime_window_prevents_priming(offset_from_three_prime):
    """Taq cannot proofread a terminal mismatch, so extension does not start."""
    index = len(FWD) - 1 - offset_from_three_prime
    swapped = "A" if FWD[index] != "A" else "C"
    mutated = FWD[:index] + swapped + FWD[index + 1 :]

    sites = amp.find_binding_sites(SYNTHETIC_TEMPLATE, mutated, direction="FWD")
    assert sites == (), f"primed despite a mismatch {offset_from_three_prime} from the 3' end"


@pytest.mark.unit
def test_a_mismatch_away_from_the_three_prime_end_still_primes():
    index = 3  # well inside the 5' half
    swapped = "A" if FWD[index] != "A" else "C"
    mutated = FWD[:index] + swapped + FWD[index + 1 :]

    sites = amp.find_binding_sites(SYNTHETIC_TEMPLATE, mutated, direction="FWD")
    assert len(sites) == 1
    assert sites[0].mismatches == 1
    assert sites[0].mismatch_positions == (index,)


@pytest.mark.unit
def test_too_many_upstream_mismatches_prevent_priming():
    mutated = list(FWD)
    for index in (1, 3, 5):
        mutated[index] = "A" if mutated[index] != "A" else "C"
    assert amp.find_binding_sites(SYNTHETIC_TEMPLATE, "".join(mutated), direction="FWD") == ()


@pytest.mark.unit
def test_the_three_prime_window_is_configurable():
    """The window is a convention, so it has to be a parameter, not a constant."""
    index = len(FWD) - 3
    swapped = "A" if FWD[index] != "A" else "C"
    mutated = FWD[:index] + swapped + FWD[index + 1 :]

    assert amp.find_binding_sites(SYNTHETIC_TEMPLATE, mutated, direction="FWD") == ()
    relaxed = amp.find_binding_sites(
        SYNTHETIC_TEMPLATE, mutated, direction="FWD", three_prime_exact=2
    )
    assert len(relaxed) == 1


@pytest.mark.unit
def test_a_mismatched_primer_writes_its_own_base_into_the_product():
    """The product carries what was synthesised, not what the template had."""
    index = 2
    swapped = "A" if FWD[index] != "A" else "C"
    mutated = FWD[:index] + swapped + FWD[index + 1 :]

    result = amp.amplify(SYNTHETIC_TEMPLATE, mutated, REV)
    assert result.outcome == amp.PRODUCT
    assert result.product.sequence[index] == swapped
    assert result.product.sequence != SYNTHETIC_ORF


# ── Failure modes as first-class results ───────────────────────────────


@pytest.mark.unit
def test_no_product_is_a_result_not_an_exception():
    result = amp.amplify(SYNTHETIC_TEMPLATE, "GGGGGGGGGGGGGGGGGGGG", REV)
    assert result.outcome == amp.NO_PRODUCT
    assert result.amplicons == ()
    assert result.product is None
    assert any("forward primer has no binding site" in n for n in result.notes)


@pytest.mark.unit
def test_primers_in_the_wrong_orientation_give_no_product():
    """Swapping the pair points both primers away from each other."""
    result = amp.amplify(SYNTHETIC_TEMPLATE, REV, FWD)
    assert result.outcome in (amp.NO_PRODUCT, amp.PRIMER_DIMER)
    assert result.amplicons == ()


@pytest.mark.unit
def test_two_binding_sites_give_multiple_products():
    template = repeated_site_template()
    result = amp.amplify(template, FWD, REV)

    assert result.outcome == amp.MULTIPLE_PRODUCTS
    assert len(result.amplicons) == 2
    assert len(set(a.length for a in result.amplicons)) == 2
    assert result.product is None, "a multi-product reaction has no single product"
    assert any("not unique" in n for n in result.notes)


@pytest.mark.unit
def test_multiple_products_are_ordered_by_position():
    result = amp.amplify(repeated_site_template(), FWD, REV)
    starts = [a.template_start for a in result.amplicons]
    assert starts == sorted(starts)


@pytest.mark.unit
def test_a_dimer_forming_pair_is_reported():
    """3'-complementary primers prime each other instead of the template."""
    result = amp.amplify("TTTTTTTTTTTTTTTTTTTTTTTT", DIMER_FORWARD, DIMER_REVERSE)

    assert result.dimer_risk is True
    assert result.dimer_involves_three_prime is True
    assert result.dimer_delta_g < 0
    assert result.outcome == amp.PRIMER_DIMER
    assert any("heterodimer" in n for n in result.notes)


@pytest.mark.unit
def test_dimer_energy_is_always_reported_even_with_a_good_product():
    """A clean pair still gets a number, so a UI never has to re-derive it."""
    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV)
    assert result.outcome == amp.PRODUCT
    assert isinstance(result.dimer_delta_g, float)
    assert result.dimer_risk is False


@pytest.mark.unit
def test_a_product_longer_than_the_limit_is_excluded():
    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV, max_product_bp=50)
    assert result.outcome == amp.NO_PRODUCT
    assert any("maximum product length" in n for n in result.notes)


# ── Circular templates ─────────────────────────────────────────────────


@pytest.mark.unit
def test_an_amplicon_may_span_the_origin_of_a_circular_template():
    """Rotated so the ORF is split across the origin: linear PCR cannot amplify
    it, circular can, and the product is still the ORF.
    """
    rotated = SYNTHETIC_ORF[60:] + "TTTTTTTTTT" + SYNTHETIC_ORF[:60]

    linear = amp.amplify(rotated, FWD, REV, circular=False)
    assert linear.outcome == amp.NO_PRODUCT

    circular = amp.amplify(rotated, FWD, REV, circular=True)
    assert circular.outcome == amp.PRODUCT
    assert circular.product.wraps_origin is True
    assert circular.product.sequence == SYNTHETIC_ORF


# ── Restriction sites the tails introduce ──────────────────────────────


@pytest.mark.unit
def test_tail_sites_are_located_and_labelled_as_tails():
    result = amp.amplify(
        SYNTHETIC_TEMPLATE,
        ECORI_TAIL + FWD,
        HINDIII_TAIL + REV,
        forward_tail=ECORI_TAIL,
        reverse_tail=HINDIII_TAIL,
        enzymes=["EcoRI", "HindIII"],
    )
    regions = {s.enzyme: s.region for s in result.product.sites}
    assert regions == {"EcoRI": amp.FORWARD_TAIL, "HindIII": amp.REVERSE_TAIL}
    assert result.product.internal_sites == ()


@pytest.mark.unit
def test_an_enzyme_cutting_inside_the_insert_is_flagged():
    """The whole point for this course: the tail enzyme also cuts the insert,
    so digesting the product to ligate it would destroy the insert.
    """
    fwd = TEMPLATE_WITH_INTERNAL_ECORI[10:30]
    rev = reverse_complement(TEMPLATE_WITH_INTERNAL_ECORI[48:68])

    result = amp.amplify(
        TEMPLATE_WITH_INTERNAL_ECORI,
        ECORI_TAIL + fwd,
        ECORI_TAIL + rev,
        forward_tail=ECORI_TAIL,
        reverse_tail=ECORI_TAIL,
        enzymes=["EcoRI"],
    )

    assert result.outcome == amp.PRODUCT
    internal = result.product.internal_sites
    assert internal, "the internal EcoRI site was not reported"
    assert all(s.region == amp.INSERT for s in internal)
    assert any("destroy what you are cloning" in n for n in result.notes)


@pytest.mark.unit
def test_no_sites_are_reported_when_no_enzymes_are_asked_for():
    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV)
    assert result.product.sites == ()


# ── Diagnostics and provenance ─────────────────────────────────────────


@pytest.mark.unit
def test_diagnostics_record_the_rule_that_was_applied():
    """A methods section is generated from this, so it must be the real values."""
    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV, three_prime_exact=4, max_mismatches=1)
    assert result.diagnostics["three_prime_exact"] == 4
    assert result.diagnostics["max_mismatches"] == 1
    assert result.diagnostics["template_bp"] == len(SYNTHETIC_TEMPLATE)


@pytest.mark.unit
def test_the_priming_rule_is_labelled_a_convention():
    """Neither number is a measured value and neither may claim a citation."""
    for field_name in ("three_prime_exact", "max_mismatches"):
        kind, explanation = amp.THRESHOLD_PROVENANCE[field_name]
        assert kind == "convention"
        assert explanation.strip()


@pytest.mark.unit
def test_results_serialise_for_a_saved_workspace():
    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV)
    data = result.to_dict()
    assert data["outcome"] == amp.PRODUCT
    assert data["amplicons"][0]["length"] == len(SYNTHETIC_ORF)
    assert "three_prime_exact" in data["diagnostics"]


# ── The published mechanism behind the priming rule ───────────────────


@pytest.mark.unit
def test_the_priming_rule_records_its_published_mechanism():
    """The numbers are ours; the 3'-end dependence is an empirical result.

    Before this, the claim that Taq cannot proofread a terminal mismatch
    reached the student in the generated methods paragraph citing nothing,
    because the field it belongs to is correctly labelled a convention.
    """
    entry = amp.THRESHOLD_PROVENANCE["three_prime_exact"]
    assert entry.kind == "convention", "the window of 5 is not a measured value"
    assert set(entry.mechanism) == {"newton1989", "tindall1988"}
    assert "does not function" in entry.mechanism_claim
    assert "Neither paper supports a window of 5" in entry.mechanism_claim


@pytest.mark.unit
def test_the_mismatch_count_claims_no_mechanism():
    """Only the 3'-end rule has a published basis; the tolerance does not."""
    entry = amp.THRESHOLD_PROVENANCE["max_mismatches"]
    assert entry.kind == "convention"
    assert entry.mechanism == ()


@pytest.mark.unit
def test_pcr_itself_is_now_cited():
    """The engine simulates PCR, which used to be uncited entirely."""
    from karcytics_plugins.synthetic_biology.analysis import citations

    keys = citations.FEATURE_CITATIONS["amplification"]
    assert "saiki1988" in keys, "PCR with a thermostable polymerase is what is modelled"
    assert "newton1989" in keys
    assert "tindall1988" in keys


@pytest.mark.unit
def test_the_mechanism_reaches_the_generated_methods_text():
    """The distinction is worthless if it only exists in the source."""
    from karcytics_plugins.synthetic_biology.analysis import citations

    result = amp.amplify(SYNTHETIC_TEMPLATE, FWD, REV)
    text = citations.methods_text([citations.amplification_step(result)])

    assert "polymerase chain reaction" in text
    assert "does not prime" in text
    assert "proofreading" in text
    # And the honesty clause survives alongside the citation.
    assert "conventions of this module rather than published values" in text
    for author in ("Saiki", "Newton", "Tindall"):
        assert author in text

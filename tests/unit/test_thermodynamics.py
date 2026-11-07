"""The nearest-neighbour free-energy engine, validated against two references.

`primer3-py` cannot be used here — it is GPL-2.0-or-later and this project
ships under PolyForm Noncommercial, so it is neither a dependency nor an
available oracle. Validation instead rests on two independent anchors:

1. **The published parameters.** ``test_parameters_match_published_values``
   pins every stacking term against SantaLucia & Hicks (2004) as printed. The
   module reads them from Biopython rather than transcribing them, so this
   catches a Biopython change as well as a typo.
2. **An independent implementation of the same model.** Biopython's ``Tm_NN``
   decomposes a duplex into the same stacks, initiation and terminal-AT terms,
   but was written by other people from the same paper. ``VALIDATION_PANEL``
   is the committed fixture; every duplex in it must reproduce Biopython's Tm
   exactly, which can only happen if the decomposition agrees term for term.
"""

from __future__ import annotations

import math

import pytest
from Bio.SeqUtils import MeltingTemp

from karcytics_plugins.synthetic_biology.analysis.assembly import thermodynamics as thermo

#: Duplexes spanning GC extremes, AT extremes, alternating, homopolymer and
#: real primer sequences. Committed so the oracle comparison is reproducible.
VALIDATION_PANEL: tuple[str, ...] = (
    "GCGCGC",
    "ATATATAT",
    "CGTTGA",
    "ACGTACGTAC",
    "GGGGCCCC",
    "TTTTAAAA",
    "ATGCATGCATGC",
    "GCTAGCTAGCTAGC",
    "AACGCGGGAAAAAGTGGAAG",
    "CCCCCCCCCC",
    "AGTCAGTCAGTCAGTCAGTC",
    "TGCATGCA",
    "AAAAAAAAAA",
    "GCGCGCGCGCGCGCGCGCGC",
    "ATGAGTAAAGGAGAAGAACT",
    "GGAGAAGAACTTTTCACTGGAG",
)

#: SantaLucia & Hicks (2004), as published: {stack: (ΔH kcal/mol, ΔS cal/mol·K)}.
PUBLISHED_NN: dict[str, tuple[float, float]] = {
    "AA/TT": (-7.6, -21.3),
    "AT/TA": (-7.2, -20.4),
    "TA/AT": (-7.2, -21.3),
    "CA/GT": (-8.5, -22.7),
    "GT/CA": (-8.4, -22.4),
    "CT/GA": (-7.8, -21.0),
    "GA/CT": (-8.2, -22.2),
    "CG/GC": (-10.6, -27.2),
    "GC/CG": (-9.8, -24.4),
    "GG/CC": (-8.0, -19.9),
}
PUBLISHED_INIT = (0.2, -5.7)
PUBLISHED_TERMINAL_AT = (2.2, 6.9)


# ── Reference 1: the published parameter table ─────────────────────────


@pytest.mark.unit
def test_parameters_match_published_values():
    for stack, (dh, ds) in PUBLISHED_NN.items():
        assert stack in thermo.NN_PARAMS, f"{stack} missing from the loaded table"
        got_dh, got_ds = thermo.NN_PARAMS[stack]
        assert got_dh == pytest.approx(dh, abs=1e-9), stack
        assert got_ds == pytest.approx(ds, abs=1e-9), stack

    assert thermo.NN_PARAMS["init"] == pytest.approx(PUBLISHED_INIT, abs=1e-9)
    assert thermo.NN_PARAMS["init_A/T"] == pytest.approx(PUBLISHED_TERMINAL_AT, abs=1e-9)


# ── Reference 2: Biopython, an independent implementation ──────────────


def _biopython_tm(seq: str) -> float:
    """Biopython's Tm for a perfectly complementary duplex, no salt correction."""
    return MeltingTemp.Tm_NN(
        seq, nn_table=MeltingTemp.DNA_NN4, dnac1=250, dnac2=250, Na=50, saltcorr=0
    )


def _our_tm(seq: str) -> float:
    """Tm from our ΔH/ΔS using Biopython's own formula, so only the
    thermodynamics differ, not the algebra around them.
    """
    bottom = "".join(thermo.complement(b) for b in seq)
    dh, ds = thermo.duplex_enthalpy_entropy(seq, bottom)
    k = (250 - 250 / 2.0) * 1e-9
    return (1000 * dh) / (ds + 1.987 * math.log(k)) - 273.15


@pytest.mark.unit
@pytest.mark.parametrize("seq", VALIDATION_PANEL)
def test_duplex_matches_biopython_exactly(seq: str):
    """Our decomposition must be term-for-term identical to Biopython's.

    Not an approximate agreement: both implement the same published model, so
    any difference is a bug in one of them, not tolerance.
    """
    assert _our_tm(seq) == pytest.approx(_biopython_tm(seq), abs=1e-9), seq


@pytest.mark.unit
def test_delta_g_is_consistent_with_enthalpy_and_entropy():
    dh, ds = thermo.duplex_enthalpy_entropy("GCGCGC", "CGCGCG")
    assert thermo.delta_g_37(dh, ds) == pytest.approx(dh - 310.15 * ds / 1000.0)


@pytest.mark.unit
def test_gc_rich_duplex_is_more_stable_than_at_rich():
    gc = thermo.duplex_delta_g("GCGCGCGC", "CGCGCGCG")
    at = thermo.duplex_delta_g("ATATATAT", "TATATATA")
    assert gc < at, "a GC-rich duplex must have the more negative ΔG"


@pytest.mark.unit
def test_terminal_at_penalty_is_applied_per_end():
    """Two A/T ends cost twice one. Verified against the table, not asserted."""
    penalty = thermo.NN_PARAMS["init_A/T"][0]
    # Same stacks, differing only in whether the ends are A/T.
    both_at = thermo.duplex_enthalpy_entropy("ATGCGCAT", "TACGCGTA")[0]
    no_at = thermo.duplex_enthalpy_entropy("GTGCGCAG", "CACGCGTC")[0]
    stacks_both = sum(
        thermo.NN_PARAMS[
            thermo._stack_key(
                ("ATGCGCAT"[i], "TACGCGTA"[i]), ("ATGCGCAT"[i + 1], "TACGCGTA"[i + 1])
            )
        ][0]
        for i in range(7)
    )
    stacks_no = sum(
        thermo.NN_PARAMS[
            thermo._stack_key(
                ("GTGCGCAG"[i], "CACGCGTC"[i]), ("GTGCGCAG"[i + 1], "CACGCGTC"[i + 1])
            )
        ][0]
        for i in range(7)
    )
    assert both_at - stacks_both == pytest.approx(thermo.NN_PARAMS["init"][0] + 2 * penalty)
    assert no_at - stacks_no == pytest.approx(thermo.NN_PARAMS["init"][0])


@pytest.mark.unit
def test_duplex_rejects_bad_input():
    with pytest.raises(ValueError):
        thermo.duplex_enthalpy_entropy("ATGC", "TACGA")  # length mismatch
    with pytest.raises(ValueError):
        thermo.duplex_enthalpy_entropy("A", "T")  # no stack to sum


# ── Structure prediction ───────────────────────────────────────────────


@pytest.mark.unit
def test_self_dimer_found_in_a_self_complementary_primer():
    result = thermo.self_dimer("GCGCGCGCGC")
    assert result.delta_g < -5.0
    assert result.base_pairs >= 6
    assert result.kind == "self_dimer"


@pytest.mark.unit
def test_no_self_dimer_in_a_homopolymer():
    """Poly-A cannot pair with poly-A, so there is nothing to report."""
    result = thermo.self_dimer("AAAAAAAAAAAA")
    assert result.delta_g == 0.0
    assert result.base_pairs == 0


@pytest.mark.unit
def test_hetero_dimer_detects_complementary_primers():
    strong = thermo.hetero_dimer("GCGCGCGCGC", "GCGCGCGCGC")
    weak = thermo.hetero_dimer("AAAAAAAAAA", "AAAAAAAAAA")
    assert strong.delta_g < weak.delta_g
    assert strong.kind == "hetero_dimer"


@pytest.mark.unit
def test_three_prime_involvement_is_reported():
    """A duplex reaching a 3' end is flagged, because that end primes."""
    # Reverse complement of its own 3' end -> the 3' ends pair.
    result = thermo.hetero_dimer("AAAAAAAAAAGGGCCC", "AAAAAAAAAAGGGCCC")
    assert result.base_pairs >= 3
    assert result.involves_three_prime is True


@pytest.mark.unit
def test_hairpin_found_in_a_stem_loop_and_labelled_stem_only():
    # Stem GGGGG / CCCCC with a 4 nt loop between.
    result = thermo.hairpin("GGGGGTTTTCCCCC")
    assert result.delta_g < 0.0
    assert result.base_pairs >= 3
    assert result.model == "stem-only", "an approximate model must say so"


@pytest.mark.unit
def test_no_hairpin_without_a_stem():
    assert thermo.hairpin("AAAAAAAAAAAAAAA").base_pairs == 0


@pytest.mark.unit
def test_structure_result_round_trips_to_dict():
    result = thermo.hairpin("GGGGGTTTTCCCCC")
    data = result.to_dict()
    assert data["model"] == "stem-only"
    assert data["delta_g"] == pytest.approx(round(result.delta_g, 2))

"""Committed sequence fixtures for the amplification, digest and gel engines.

EVERY SEQUENCE HERE IS SYNTHETIC AND CONSTRUCTED FOR TESTING.
None of it is pGFP-S12 or any other real plasmid.

Where the real template drops in
--------------------------------
BIOL341 amplifies from **pGFP-S12**, which we do not have. When the file
arrives (GenBank or FASTA):

1. Put it under ``tests/fixtures/pgfp_s12.gb`` and load it with
   ``Bio.SeqIO`` in a fixture, rather than pasting the sequence into Python.
2. Add it as an additional parametrisation of the amplification tests. Do not
   replace these synthetic cases: they are built so that every expected value
   is hand-computable, which a real 3-4 kb plasmid is not.
3. ``PGFP_S12_PLACEHOLDER`` below is deliberately *not* a stand-in sequence —
   it is None, so anything that reaches for it fails loudly instead of
   silently testing against invented data.

The engines take a template as an argument and hold no built-in sequence, so
nothing in ``analysis/`` needs to change when the real file lands.
"""

from __future__ import annotations

#: Intentionally None. See the module docstring: a fabricated plasmid that
#: looked plausible would be worse than an obvious absence.
PGFP_S12_PLACEHOLDER = None

#: A 117 bp synthetic open reading frame. Starts with ATG and is AT-rich at the
#: 5' end, which is what makes it useful: a full-coverage forward primer here
#: cannot meet a 40-60% GC rubric, the same situation phase 1 surfaced.
SYNTHETIC_ORF = (
    "ATGAGTAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTT"
    "AATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATAC"
)

#: The ORF flanked by homopolymer arms, so primer footprints are unambiguous
#: and the expected product is exactly SYNTHETIC_ORF.
SYNTHETIC_TEMPLATE = "CCCCCCCCCC" + SYNTHETIC_ORF + "GGGGGGGGGG"

#: Restriction tails used throughout. EcoRI/HindIII are the pair BIOL341 uses.
ECORI_TAIL = "GAATTC"
HINDIII_TAIL = "AAGCTT"

#: A template carrying an EcoRI site INSIDE the region to be amplified. This is
#: the course-critical failure: the tail enzyme also cuts the insert, so
#: digesting the product destroys what the student is cloning.
TEMPLATE_WITH_INTERNAL_ECORI = (
    "TTTTTTTTTT"
    "ATGCGTACGTTACGCATGCA"  # forward primer footprint
    "TTTTTTGAATTCTTTTTT"  # <- internal EcoRI site
    "GCATGCGTAACGTACGCATG"  # reverse primer footprint (as it appears on top)
    "AAAAAAAAAA"
)

#: Hand-computable digest substrate. Two EcoRI sites and one HindIII site at
#: known offsets; see test_restriction for the arithmetic.
#: EcoRI GAATTC at 0-based 3 and 23; HindIII AAGCTT at 0-based 13.
DIGEST_TEMPLATE = "AAAGAATTCAAAAAAGCTTAAAAGAATTCAAA"

#: Minimal circular template whose EcoRI site spans the origin: the sequence
#: begins with AATTC and ends with G, so GAATTC exists only once the ends join.
CIRCULAR_ORIGIN_SPANNING = "AATTCAAAAAAAAAG"

#: Type IIS substrate. BsaI reads GGTCTC and cuts one base downstream, leaving
#: a 4-nt 5' overhang whose sequence is whatever follows — here GGGG.
BSAI_TEMPLATE = "TTGGTCTCAGGGGTTTTTTTT"
BSAI_EXPECTED_OVERHANG = "GGGG"

#: A primer pair whose 3' ends are complementary to each other, so they form a
#: 3'-anchored heterodimer and prime each other instead of the template.
DIMER_FORWARD = "AAAAAAAAAAAAGGGCCC"
DIMER_REVERSE = "AAAAAAAAAAAAGGGCCC"


#: A template containing the forward primer footprint twice, so a single pair
#: yields two products of different length.
def repeated_site_template() -> str:
    """Template with two forward footprints and one reverse footprint."""
    fwd = SYNTHETIC_ORF[:20]
    rev_footprint = SYNTHETIC_ORF[-20:]
    spacer = "TTTTTTTTTTTTTTTTTTTT"
    return fwd + spacer + fwd + spacer + rev_footprint


def reverse_complement(seq: str) -> str:
    """Local helper so fixtures do not depend on the module under test."""
    pairs = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
    return "".join(pairs[b] for b in reversed(seq.upper()))


def primers_for(orf: str, length: int = 20) -> tuple[str, str]:
    """Perfectly matched primer pair spanning ``orf``, no tails."""
    return orf[:length], reverse_complement(orf[-length:])

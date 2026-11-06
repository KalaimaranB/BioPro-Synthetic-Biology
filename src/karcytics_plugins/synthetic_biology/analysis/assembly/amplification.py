"""In-silico PCR: where primers bind, what product comes out, and what fails.

The failure modes are the teaching content, so they are returned as results
rather than raised. A student whose primer pair yields nothing, or three bands,
or only primer-dimer, needs to see *which* of those happened and why — an
exception would collapse all three into "it didn't work".

Priming model
-------------
A primer anneals where its binding region matches the template closely enough
for a polymerase to extend it. Two parameters, both **conventions** (recorded
in :data:`THRESHOLD_PROVENANCE`, cite nothing):

* ``three_prime_exact`` (default 5) — bases at the 3' end that must match
  perfectly. Taq has no 3'→5' proofreading, so a mismatch at the extending
  terminus is not corrected and extension stalls. This is the principle
  allele-specific PCR exploits deliberately.
* ``max_mismatches`` (default 2) — mismatches tolerated in the rest of the
  binding region, where a bulge is accommodated and extension still proceeds.

The *shape* of the rule (perfect 3' window, tolerance upstream) is standard
practice; the specific window and count are our settings, not measured values,
and are labelled as such wherever they are shown.

Tails
-----
A 5' restriction tail does not anneal on the first cycle, so it is excluded
from the annealing temperature but present in the product. Phase 1's
``VectorAssemblyEngine.calculate_tm`` is called on the binding region only,
which preserves that behaviour exactly rather than re-deriving it.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import restriction as rst
from .primer_rubric import DEFAULT_RUBRIC, PrimerRubric
from .thermodynamics import hetero_dimer, reverse_complement
from .vector_builder import VectorAssemblyEngine

#: Outcomes. Each is a real experimental result, never an error.
PRODUCT = "product"
NO_PRODUCT = "no_product"
MULTIPLE_PRODUCTS = "multiple_products"
PRIMER_DIMER = "primer_dimer"

#: Where a restriction site sits relative to the amplicon's parts. ``INSERT``
#: is the one that matters: an enzyme that cuts there destroys the insert the
#: student is trying to clone.
FORWARD_TAIL = "forward_tail"
INSERT = "insert"
REVERSE_TAIL = "reverse_tail"
SPANNING = "tail_insert_junction"

#: Defaults for the priming rule. Conventions, not measurements.
THREE_PRIME_EXACT = 5
MAX_MISMATCHES = 2

#: Longest product this engine will resolve, in bp. A search setting, not a
#: statement about what a polymerase can do.
DEFAULT_MAX_PRODUCT_BP = 10_000


@dataclass(frozen=True)
class BindingSite:
    """One place a primer anneals well enough to be extended."""

    primer_name: str
    #: Strand the primer anneals to: +1 binds the bottom strand and extends
    #: rightwards along the top strand; -1 is the reverse primer.
    strand: int
    #: Half-open footprint of the *binding region* in top-strand coordinates.
    start: int
    end: int
    #: Top-strand index of the primer's 3' terminus, where extension begins.
    three_prime_index: int
    mismatches: int
    mismatch_positions: tuple[int, ...]
    #: Melting temperature of the binding region alone, tail excluded.
    annealing_tm: float
    wraps_origin: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "primer_name": self.primer_name,
            "strand": self.strand,
            "start": self.start,
            "end": self.end,
            "three_prime_index": self.three_prime_index,
            "mismatches": self.mismatches,
            "mismatch_positions": list(self.mismatch_positions),
            "annealing_tm": round(self.annealing_tm, 2),
            "wraps_origin": self.wraps_origin,
        }


@dataclass(frozen=True)
class ProductSite:
    """A restriction site in the product, with which part of it it falls in."""

    enzyme: str
    position: int
    region: str
    overhang: str
    overhang_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "enzyme": self.enzyme,
            "position": self.position,
            "region": self.region,
            "overhang": self.overhang,
            "overhang_type": self.overhang_type,
        }


@dataclass(frozen=True)
class Amplicon:
    """One predicted PCR product."""

    sequence: str
    #: Template span between the two primer footprints, in template coords.
    template_start: int
    template_end: int
    forward_site: BindingSite
    reverse_site: BindingSite
    gc_percent: float
    #: Length of each 5' tail carried into the product.
    forward_tail_bp: int
    reverse_tail_bp: int
    wraps_origin: bool = False
    sites: tuple[ProductSite, ...] = ()

    @property
    def length(self) -> int:
        """Product length in bp, tails included."""
        return len(self.sequence)

    @property
    def internal_sites(self) -> tuple[ProductSite, ...]:
        """Sites inside the insert — the ones that would destroy it."""
        return tuple(s for s in self.sites if s.region == INSERT)

    def to_dict(self) -> dict[str, Any]:
        return {
            "length": self.length,
            "sequence": self.sequence,
            "gc_percent": round(self.gc_percent, 1),
            "template_start": self.template_start,
            "template_end": self.template_end,
            "forward_tail_bp": self.forward_tail_bp,
            "reverse_tail_bp": self.reverse_tail_bp,
            "wraps_origin": self.wraps_origin,
            "forward_site": self.forward_site.to_dict(),
            "reverse_site": self.reverse_site.to_dict(),
            "sites": [s.to_dict() for s in self.sites],
        }


@dataclass(frozen=True)
class AmplificationResult:
    """What the reaction is predicted to produce."""

    outcome: str
    amplicons: tuple[Amplicon, ...]
    forward_sites: tuple[BindingSite, ...]
    reverse_sites: tuple[BindingSite, ...]
    #: Heterodimer between the two primers, always computed. A strong
    #: 3'-anchored dimer competes with the template even when a product forms.
    dimer_delta_g: float
    dimer_involves_three_prime: bool
    dimer_risk: bool
    #: Human-readable reasons, for a UI to show without re-deriving anything.
    notes: tuple[str, ...] = ()
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def product(self) -> Amplicon | None:
        """The single product, or None when there is not exactly one."""
        return self.amplicons[0] if len(self.amplicons) == 1 else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "amplicons": [a.to_dict() for a in self.amplicons],
            "n_forward_sites": len(self.forward_sites),
            "n_reverse_sites": len(self.reverse_sites),
            "dimer_delta_g": round(self.dimer_delta_g, 2),
            "dimer_involves_three_prime": self.dimer_involves_three_prime,
            "dimer_risk": self.dimer_risk,
            "notes": list(self.notes),
            "diagnostics": dict(self.diagnostics),
        }


@dataclass(frozen=True)
class PrimerPair:
    """The two primers and their 5' tails, which always travel together."""

    forward: str
    reverse: str
    forward_tail: str = ""
    reverse_tail: str = ""

    @property
    def forward_anneal(self) -> str:
        return annealing_region(self.forward, self.forward_tail)

    @property
    def reverse_anneal(self) -> str:
        return annealing_region(self.reverse, self.reverse_tail)


# ── Sequence helpers ───────────────────────────────────────────────────


def _clean(seq: str) -> str:
    return "".join(str(seq).split()).upper()


def gc_percent(seq: str) -> float:
    """GC content of ``seq`` as a percentage, 0.0 for an empty string."""
    if not seq:
        return 0.0
    return 100.0 * (seq.count("G") + seq.count("C")) / len(seq)


def annealing_region(primer: str, tail: str) -> str:
    """Strip a 5' tail from a primer, leaving the part that anneals.

    Only strips when the primer genuinely starts with the tail, so a mislabelled
    tail cannot silently shorten the binding region.
    """
    primer, tail = _clean(primer), _clean(tail)
    return primer[len(tail) :] if tail and primer.startswith(tail) else primer


# ── Binding ────────────────────────────────────────────────────────────


def _compare(
    probe: str,
    window: str,
    three_prime_at_end: bool,
    three_prime_exact: int,
) -> tuple[int, tuple[int, ...]] | None:
    """Count mismatches, rejecting any inside the 3'-terminal window.

    ``probe`` is the primer's binding region written as it appears on the top
    strand, so for a reverse primer the 3' terminus is at the *start* of the
    window — hence ``three_prime_at_end``.
    """
    if len(probe) != len(window):
        return None

    size = len(probe)
    guard = (
        range(max(size - three_prime_exact, 0), size)
        if three_prime_at_end
        else range(0, min(three_prime_exact, size))
    )
    guarded = set(guard)

    positions = []
    for i, (a, b) in enumerate(zip(probe, window, strict=True)):
        if a == b:
            continue
        if i in guarded:
            # A mismatch at the extending terminus blocks priming outright.
            return None
        positions.append(i)
    return len(positions), tuple(positions)


def _windows(template: str, size: int, circular: bool) -> list[tuple[int, str]]:
    """Every start index and window of ``size``, wrapping when circular."""
    length = len(template)
    if size > length:
        return []
    if not circular:
        return [(i, template[i : i + size]) for i in range(length - size + 1)]
    doubled = template + template
    return [(i, doubled[i : i + size]) for i in range(length)]


def find_binding_sites(  # noqa: PLR0913 - each keyword is an independent search setting; bundling them would only relocate the list
    template: str,
    primer: str,
    *,
    tail: str = "",
    direction: str = "FWD",
    name: str = "",
    circular: bool = False,
    three_prime_exact: int = THREE_PRIME_EXACT,
    max_mismatches: int = MAX_MISMATCHES,
) -> tuple[BindingSite, ...]:
    """Find everywhere a primer can prime, on either strand.

    A forward primer's binding region must appear on the top strand; a reverse
    primer's must appear on the bottom strand, i.e. its reverse complement
    appears on the top strand.
    """
    template = _clean(template)
    anneal = annealing_region(primer, tail)
    if not template or not anneal:
        return ()

    strand = 1 if direction.upper().startswith("F") else -1
    # Written on the top strand: a reverse primer's footprint is its revcomp.
    probe = anneal if strand == 1 else reverse_complement(anneal)
    # For a forward primer the 3' end is the right-hand end of the footprint;
    # for a reverse primer the footprint is reversed, so it is the left-hand end.
    three_prime_at_end = strand == 1

    tm = VectorAssemblyEngine.calculate_tm(anneal)
    size = len(probe)
    length = len(template)

    found: list[BindingSite] = []
    for start, window in _windows(template, size, circular):
        comparison = _compare(probe, window, three_prime_at_end, three_prime_exact)
        if comparison is None:
            continue
        mismatches, positions = comparison
        if mismatches > max_mismatches:
            continue
        end = start + size
        found.append(
            BindingSite(
                primer_name=name or ("forward" if strand == 1 else "reverse"),
                strand=strand,
                start=start,
                end=end,
                three_prime_index=(end - 1) if strand == 1 else start,
                mismatches=mismatches,
                mismatch_positions=positions,
                annealing_tm=tm,
                wraps_origin=circular and end > length,
            )
        )
    return tuple(found)


# ── Amplicon resolution ────────────────────────────────────────────────


def _build_amplicon(
    template: str,
    fwd: BindingSite,
    rev: BindingSite,
    pair: PrimerPair,
    circular: bool,
) -> Amplicon:
    """Assemble the product. Primer footprints contribute *primer* sequence.

    The product carries what was synthesised, not what the template had, so a
    mismatched primer writes its own base into the product — which is how
    site-directed mutagenesis by PCR works.
    """
    length = len(template)
    interior_start = fwd.three_prime_index + 1
    interior_end = rev.three_prime_index
    if circular and interior_end < interior_start:
        interior_end += length

    interior = "".join(template[i % length] for i in range(interior_start, interior_end))
    sequence = _clean(pair.forward) + interior + reverse_complement(_clean(pair.reverse))

    return Amplicon(
        sequence=sequence,
        template_start=fwd.start % length,
        template_end=interior_end,
        forward_site=fwd,
        reverse_site=rev,
        gc_percent=gc_percent(sequence),
        forward_tail_bp=len(_clean(pair.forward_tail)),
        reverse_tail_bp=len(_clean(pair.reverse_tail)),
        wraps_origin=circular and (interior_end > length or fwd.wraps_origin),
    )


def _region_of(
    position: int, fwd_tail_bp: int, product_len: int, rev_tail_bp: int, span: int
) -> str:
    """Classify a site position within the product's tail/insert layout."""
    insert_start = fwd_tail_bp
    insert_end = product_len - rev_tail_bp
    site_end = position + span
    if site_end <= insert_start:
        return FORWARD_TAIL
    if position >= insert_end:
        return REVERSE_TAIL
    if position < insert_start or site_end > insert_end:
        return SPANNING
    return INSERT


def annotate_sites(
    amplicon: Amplicon,
    enzymes: str | Any,
) -> Amplicon:
    """Return a copy of ``amplicon`` with its restriction sites located.

    Uses engine 1, so cut geometry still comes from REBASE. Each site is
    labelled with the part of the product it falls in; ``INSERT`` is the
    warning case — the tail enzyme also cuts inside what the student is cloning.
    """
    sites = rst.find_sites(amplicon.sequence, enzymes, circular=False)
    located = []
    for site in sites:
        enzyme = rst.enzyme_info(site.enzyme)
        start = site.site_start if site.site_start is not None else site.top_cut
        located.append(
            ProductSite(
                enzyme=site.enzyme,
                position=start,
                region=_region_of(
                    start,
                    amplicon.forward_tail_bp,
                    amplicon.length,
                    amplicon.reverse_tail_bp,
                    int(enzyme["site_length"]),
                ),
                overhang=site.overhang,
                overhang_type=site.overhang_type,
            )
        )
    return Amplicon(**{**amplicon.__dict__, "sites": tuple(located)})


def _dimer_note(dimer: Any, cutoff: float) -> str:
    anchor = "3'-anchored" if dimer.involves_three_prime else "internal"
    return (
        f"The primers form a {anchor} heterodimer at {dimer.delta_g:.2f} kcal/mol, "
        f"past the {cutoff:g} cutoff; it competes with the template for primer."
    )


def _no_product_notes(
    fwd_sites: tuple[BindingSite, ...], rev_sites: tuple[BindingSite, ...]
) -> list[str]:
    notes = []
    if not fwd_sites:
        notes.append("The forward primer has no binding site on this template.")
    if not rev_sites:
        notes.append("The reverse primer has no binding site on this template.")
    if fwd_sites and rev_sites:
        notes.append(
            "Both primers bind, but no pair is correctly oriented with the forward "
            "primer upstream and within the maximum product length."
        )
    return notes


def _classify(  # noqa: PLR0913 - the classification genuinely depends on all six
    amplicons: list[Amplicon],
    fwd_sites: tuple[BindingSite, ...],
    rev_sites: tuple[BindingSite, ...],
    dimer: Any,
    dimer_risk: bool,
    cutoff: float,
) -> tuple[str, tuple[str, ...]]:
    """Decide the outcome and the reasons for it. All judgement lives here."""
    notes: list[str] = []
    if dimer_risk:
        notes.append(_dimer_note(dimer, cutoff))

    if not amplicons:
        # Only dimer and no product is the classic "one low band" gel.
        outcome = PRIMER_DIMER if dimer_risk else NO_PRODUCT
        notes.extend(_no_product_notes(fwd_sites, rev_sites))
    elif len(amplicons) > 1:
        outcome = MULTIPLE_PRODUCTS
        sizes = ", ".join(str(a.length) for a in amplicons)
        notes.append(
            f"{len(amplicons)} products are predicted ({sizes} bp); the primers are "
            "not unique on this template."
        )
    else:
        outcome = PRODUCT
        internal = amplicons[0].internal_sites
        if internal:
            cutters = sorted({s.enzyme for s in internal})
            notes.append(
                f"{', '.join(cutters)} also cuts inside the insert, so digesting the "
                "product with it would destroy what you are cloning."
            )
    return outcome, tuple(notes)


def amplify(  # noqa: PLR0913 - each argument is an independent input to the reaction
    template: str,
    forward_primer: str,
    reverse_primer: str,
    *,
    forward_tail: str = "",
    reverse_tail: str = "",
    circular: bool = False,
    max_product_bp: int = DEFAULT_MAX_PRODUCT_BP,
    three_prime_exact: int = THREE_PRIME_EXACT,
    max_mismatches: int = MAX_MISMATCHES,
    enzymes: str | Any = (),
    rubric: PrimerRubric | None = None,
) -> AmplificationResult:
    """Predict what a PCR with this primer pair on this template produces.

    Returns an :class:`AmplificationResult` in every case. No product, several
    products and primer-dimer are outcomes, not exceptions.
    """
    template = _clean(template)
    rubric = rubric or DEFAULT_RUBRIC
    pair = PrimerPair(forward_primer, reverse_primer, forward_tail, reverse_tail)

    fwd_sites = find_binding_sites(
        template,
        forward_primer,
        tail=forward_tail,
        direction="FWD",
        name="forward",
        circular=circular,
        three_prime_exact=three_prime_exact,
        max_mismatches=max_mismatches,
    )
    rev_sites = find_binding_sites(
        template,
        reverse_primer,
        tail=reverse_tail,
        direction="REV",
        name="reverse",
        circular=circular,
        three_prime_exact=three_prime_exact,
        max_mismatches=max_mismatches,
    )

    dimer = hetero_dimer(
        annealing_region(forward_primer, forward_tail),
        annealing_region(reverse_primer, reverse_tail),
        three_prime_window=rubric.three_prime_window,
    )
    cutoff = (
        rubric.three_prime_dimer_min_dg
        if dimer.involves_three_prime
        else rubric.hetero_dimer_min_dg
    )
    dimer_risk = dimer.delta_g < cutoff

    amplicons: list[Amplicon] = []
    length = len(template)
    for fwd in fwd_sites:
        for rev in rev_sites:
            # The reverse primer must lie downstream of the forward primer,
            # pointing back at it; on a circle "downstream" can wrap.
            span = rev.three_prime_index - fwd.three_prime_index
            if span <= 0:
                if not circular:
                    continue
                span += length
            amplicon = _build_amplicon(template, fwd, rev, pair, circular)
            if amplicon.length > max_product_bp:
                continue
            if enzymes:
                amplicon = annotate_sites(amplicon, enzymes)
            amplicons.append(amplicon)

    amplicons.sort(key=lambda a: (a.template_start, a.length))

    outcome, notes = _classify(amplicons, fwd_sites, rev_sites, dimer, dimer_risk, cutoff)

    return AmplificationResult(
        outcome=outcome,
        amplicons=tuple(amplicons),
        forward_sites=fwd_sites,
        reverse_sites=rev_sites,
        dimer_delta_g=dimer.delta_g,
        dimer_involves_three_prime=dimer.involves_three_prime,
        dimer_risk=dimer_risk,
        notes=notes,
        diagnostics={
            "template_bp": length,
            "circular": circular,
            "three_prime_exact": three_prime_exact,
            "max_mismatches": max_mismatches,
            "max_product_bp": max_product_bp,
        },
    )


#: Provenance of every tunable in this module, in the same form as
#: ``primer_rubric.THRESHOLD_PROVENANCE``. All conventions: the priming rule's
#: shape is standard practice but these particular numbers are our settings.
THRESHOLD_PROVENANCE: dict[str, tuple[str, str]] = {
    "three_prime_exact": (
        "convention",
        "Requiring a perfect match over the last 5 bases reflects that Taq "
        "lacks 3'→5' proofreading, so a terminal mismatch is not corrected. "
        "The principle is standard practice; the window of 5 is our setting, "
        "not a measured result.",
    ),
    "max_mismatches": (
        "convention",
        "Tolerating up to 2 mismatches away from the 3' end is our setting. "
        "Real tolerance depends on position, identity and annealing "
        "temperature, none of which this model takes into account.",
    ),
    "max_product_bp": (
        "convention",
        "A search bound, not a claim about polymerase processivity.",
    ),
}

__all__ = [
    "FORWARD_TAIL",
    "INSERT",
    "MAX_MISMATCHES",
    "MULTIPLE_PRODUCTS",
    "NO_PRODUCT",
    "PRIMER_DIMER",
    "PRODUCT",
    "REVERSE_TAIL",
    "SPANNING",
    "THREE_PRIME_EXACT",
    "THRESHOLD_PROVENANCE",
    "Amplicon",
    "AmplificationResult",
    "BindingSite",
    "ProductSite",
    "amplify",
    "annealing_region",
    "annotate_sites",
    "find_binding_sites",
    "gc_percent",
]

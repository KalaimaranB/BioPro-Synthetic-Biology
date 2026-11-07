"""Restriction digest over Bio.Restriction, which carries REBASE cut geometry.

Why wrap rather than tabulate
-----------------------------
Biopython ships the full REBASE enzyme set — 1088 enzymes in the pinned
version — with recognition site, cut offsets on both strands and overhang
polarity for each. Hand-writing even a short table of "common" enzymes would
mean maintaining cut geometry by hand, and getting a Type IIS offset wrong is
silent: the fragment lengths still look plausible. So the enzyme data is read
from Biopython and never restated here.

Coordinates
-----------
Biopython's ``enzyme.search()`` returns **1-based** positions of the base
immediately 3' of the top-strand cut. Everything in this module is **0-based**
and half-open, like the rest of ``analysis/``: a cut at index ``t`` falls
between ``sequence[t - 1]`` and ``sequence[t]``. Verified against
``enzyme.catalyse()`` for a 5' overhang (EcoRI), a 3' overhang (PstI), a blunt
cutter (SmaI) and a Type IIS enzyme (BsaI) — see ``test_restriction.py``.

Overhangs
---------
Derived from the template, not from a lookup, because for a Type IIS enzyme the
overhang is *sequence-dependent*: BsaI reads GGTCTC and cuts one base
downstream leaving a 4-nt 5' overhang whose sequence is whatever the template
has there. That is the whole basis of Golden Gate assembly, so it has to come
out of the sequence:

* ``ovhg < 0`` — 5' overhang, bottom cut at ``t + |ovhg|``, single-stranded
  stretch ``sequence[t : t + |ovhg|]``
* ``ovhg > 0`` — 3' overhang, bottom cut at ``t - ovhg``, single-stranded
  stretch ``sequence[t - ovhg : t]``
* ``ovhg == 0`` — blunt

Out of scope
------------
This models an idealised complete digest of naked DNA. It does **not** model
methylation sensitivity (Dam/Dcm blocking), star activity under non-ideal
buffers, partial digestion, or isoschizomer substitution. See the module-level
notes in ``DIGEST_LIMITATIONS``; these are stated rather than silently assumed
because a student comparing a predicted gel to a real one needs to know which
discrepancies the model cannot explain.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Biopython's type stubs do not export these, though both are public API and
# documented; they are generated into Bio.Restriction at import time.
from Bio.Restriction import AllEnzymes, RestrictionBatch  # type: ignore[attr-defined]
from Bio.Seq import Seq

from ..provenance import SOURCED, Provenance

#: Overhang polarity labels, used in results and surfaced to the user.
FIVE_PRIME = "5'"
THREE_PRIME = "3'"
BLUNT = "blunt"

#: What this engine deliberately does not model, and why. Surfaced so a
#: predicted digest is never mistaken for a prediction of a real reaction.
DIGEST_LIMITATIONS: tuple[tuple[str, str], ...] = (
    (
        "methylation sensitivity",
        "Dam/Dcm and CpG methylation can block cleavage at an otherwise perfect "
        "site. Modelling it needs the methylation state of the template, which "
        "an in-silico sequence does not carry.",
    ),
    (
        "star activity",
        "Cleavage at near-cognate sites under non-ideal buffer, glycerol or "
        "enzyme excess. It is a property of the reaction conditions, not of the "
        "sequence, so it cannot be predicted from sequence alone.",
    ),
    (
        "partial digestion",
        "Every site is assumed cut to completion. Real partial digests produce "
        "additional bands that are combinations of adjacent fragments.",
    ),
    (
        "isoschizomers",
        "Enzymes are matched by the name given. REBASE lists many enzymes "
        "sharing a recognition sequence, and this engine does not substitute "
        "one for another or report that an alternative exists.",
    ),
)


class UnknownEnzymeError(ValueError):
    """Raised when an enzyme name is not in the REBASE set Biopython ships."""


@dataclass(frozen=True)
class CutSite:
    """One enzyme cut, in 0-based coordinates on the supplied sequence."""

    enzyme: str
    #: Index of the recognition sequence's first base, or None when the site
    #: spans the origin of a circular template and so has no single start.
    site_start: int | None
    #: Cut index on the top strand: the cut lies before ``sequence[top_cut]``.
    top_cut: int
    #: Cut index on the bottom strand, same convention.
    bottom_cut: int
    #: Single-stranded overhang sequence left by the cut, 5'→3' as written on
    #: whichever strand carries it. Empty for a blunt cutter.
    overhang: str
    overhang_type: str
    #: True when the recognition site wraps the origin of a circular template.
    spans_origin: bool = False

    @property
    def is_blunt(self) -> bool:
        return self.overhang_type == BLUNT

    def to_dict(self) -> dict[str, Any]:
        return {
            "enzyme": self.enzyme,
            "site_start": self.site_start,
            "top_cut": self.top_cut,
            "bottom_cut": self.bottom_cut,
            "overhang": self.overhang,
            "overhang_type": self.overhang_type,
            "spans_origin": self.spans_origin,
        }


@dataclass(frozen=True)
class Fragment:
    """One digestion product, with the end chemistry a ligation depends on."""

    start: int
    end: int
    sequence: str
    #: Enzyme that created each end, or None for a native end of linear input.
    left_enzyme: str | None
    right_enzyme: str | None
    left_overhang: str
    right_overhang: str
    left_overhang_type: str
    right_overhang_type: str
    #: True when the fragment runs through the origin of a circular template.
    wraps_origin: bool = False

    @property
    def length(self) -> int:
        """Length in bp. Taken from the sequence so it cannot disagree with it."""
        return len(self.sequence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "length": self.length,
            "left_enzyme": self.left_enzyme,
            "right_enzyme": self.right_enzyme,
            "left_overhang": self.left_overhang,
            "right_overhang": self.right_overhang,
            "left_overhang_type": self.left_overhang_type,
            "right_overhang_type": self.right_overhang_type,
            "wraps_origin": self.wraps_origin,
        }


@dataclass(frozen=True)
class DigestResult:
    """The outcome of a digest. A digest with no sites is a result, not an error."""

    enzymes: tuple[str, ...]
    circular: bool
    template_length: int
    sites: tuple[CutSite, ...]
    fragments: tuple[Fragment, ...]

    @property
    def cut(self) -> bool:
        return bool(self.sites)

    @property
    def fragment_lengths(self) -> tuple[int, ...]:
        return tuple(f.length for f in self.fragments)

    def sites_for(self, enzyme: str) -> tuple[CutSite, ...]:
        return tuple(s for s in self.sites if s.enzyme == enzyme)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enzymes": list(self.enzymes),
            "circular": self.circular,
            "template_length": self.template_length,
            "cut": self.cut,
            "sites": [s.to_dict() for s in self.sites],
            "fragments": [f.to_dict() for f in self.fragments],
        }


# ── Enzyme lookup ──────────────────────────────────────────────────────


def _enzyme_by_name(name: str) -> Any:
    """Resolve an enzyme name against the REBASE set Biopython ships."""
    for enzyme in AllEnzymes:
        if str(enzyme) == name:
            return enzyme
    raise UnknownEnzymeError(
        f"{name!r} is not in Biopython's REBASE enzyme set. "
        "Names are case-sensitive, e.g. 'EcoRI', 'BsaI', 'HindIII'."
    )


def resolve_enzymes(names: str | Any) -> tuple[Any, ...]:
    """Resolve one name or an iterable of names to Biopython enzyme objects."""
    if isinstance(names, str):
        names = [names]
    return tuple(_enzyme_by_name(n) if isinstance(n, str) else n for n in names)


def enzyme_info(name: str) -> dict[str, Any]:
    """Describe an enzyme from REBASE, for display or for a methods section."""
    enzyme = _enzyme_by_name(name)
    overhang_type = _overhang_type(enzyme.ovhg)
    return {
        "name": str(enzyme),
        "site": str(enzyme.site),
        "site_length": len(str(enzyme.site)),
        "overhang_length": abs(enzyme.ovhg),
        "overhang_type": overhang_type,
        # A Type IIS enzyme cuts outside its recognition sequence, so the
        # overhang it leaves depends on the template rather than the enzyme.
        "cuts_outside_site": _cuts_outside_site(enzyme),
        "elucidate": enzyme.elucidate(),
    }


def _overhang_type(ovhg: int) -> str:
    if ovhg < 0:
        return FIVE_PRIME
    if ovhg > 0:
        return THREE_PRIME
    return BLUNT


def _cuts_outside_site(enzyme: Any) -> bool:
    """True for a Type IIS enzyme: its cut falls beyond its recognition sequence.

    ``fst5`` is the top-strand cut offset from the start of the recognition
    site, so a cut at or beyond the site's length is outside it.
    """
    return bool(enzyme.fst5 is not None and enzyme.fst5 >= len(str(enzyme.site)))


# ── Site finding ───────────────────────────────────────────────────────


def _clean(sequence: str) -> str:
    return "".join(sequence.split()).upper()


def _site_start(
    enzyme: Any, top_cut: int, template_length: int, circular: bool
) -> tuple[int | None, bool]:
    """Locate the recognition site that produced a cut at ``top_cut``.

    Returned as (start, spans_origin). ``fst5`` is the cut's offset from the
    site start, so the start is the cut minus that offset — which can fall
    before position 0 on a circular template, meaning the site wraps.
    """
    if enzyme.fst5 is None:
        return None, False
    start = top_cut - enzyme.fst5
    if start >= 0:
        return start, False
    if circular:
        return start % template_length, True
    return None, False


def find_sites(
    sequence: str,
    enzymes: str | Any,
    *,
    circular: bool = False,
) -> tuple[CutSite, ...]:
    """Find every cut for ``enzymes``, ordered by position on the top strand.

    Args:
        sequence: The template. Whitespace is ignored and case normalised.
        enzymes: One enzyme name, or an iterable of names/enzyme objects.
        circular: Treat the template as a circle, so a recognition site may
            span the origin. Biopython handles the wrap; this function records
            which sites it affected.

    Returns:
        A tuple of :class:`CutSite`, possibly empty. An empty result means the
        enzymes do not cut this template — a real answer, not a failure.
    """
    seq = _clean(sequence)
    resolved = resolve_enzymes(enzymes)
    if not seq:
        return ()

    length = len(seq)
    sites: list[CutSite] = []

    for enzyme in resolved:
        # Biopython's own searcher, so site finding (including the circular
        # wrap) is never reimplemented here.
        for one_based in enzyme.search(Seq(seq), linear=not circular):
            top_cut = one_based - 1
            ovhg = enzyme.ovhg
            if ovhg < 0:
                bottom_cut = top_cut - ovhg
                overhang = _slice(seq, top_cut, bottom_cut, circular)
            elif ovhg > 0:
                bottom_cut = top_cut - ovhg
                overhang = _slice(seq, bottom_cut, top_cut, circular)
            else:
                bottom_cut = top_cut
                overhang = ""

            site_start, spans = _site_start(enzyme, top_cut, length, circular)
            sites.append(
                CutSite(
                    enzyme=str(enzyme),
                    site_start=site_start,
                    top_cut=top_cut,
                    bottom_cut=bottom_cut,
                    overhang=overhang,
                    overhang_type=_overhang_type(ovhg),
                    spans_origin=spans,
                )
            )

    sites.sort(key=lambda s: (s.top_cut, s.enzyme))
    return tuple(sites)


def _slice(seq: str, start: int, end: int, circular: bool) -> str:
    """Slice, wrapping around the origin when the template is circular."""
    length = len(seq)
    if 0 <= start <= end <= length:
        return seq[start:end]
    if not circular:
        # A cut whose overhang would run off a linear end: report what exists.
        return seq[max(start, 0) : min(end, length)]
    return "".join(seq[i % length] for i in range(start, end))


def sites_in_region(
    sequence: str,
    enzymes: str | Any,
    start: int,
    end: int,
    *,
    circular: bool = False,
) -> tuple[CutSite, ...]:
    """Return the cuts falling inside ``[start, end)``.

    This is the check that matters for the BIOL341 workflow: a student adds a
    restriction tail to a primer so the PCR product can be digested and
    ligated, and that only works if the chosen enzyme does **not** also cut
    inside the amplified insert. A single internal site destroys the insert,
    and it is invisible unless something looks for it.
    """
    return tuple(
        s for s in find_sites(sequence, enzymes, circular=circular) if start <= s.top_cut < end
    )


# ── Digestion ──────────────────────────────────────────────────────────


def _fragment_between(
    seq: str,
    left: CutSite | None,
    right: CutSite | None,
    start: int,
    end: int,
    *,
    wraps: bool = False,
) -> Fragment:
    """Build a fragment spanning ``[start, end)`` on the top strand."""
    sub = "".join(seq[i % len(seq)] for i in range(start, end)) if wraps else seq[start:end]
    return Fragment(
        start=start % len(seq) if seq else start,
        end=end,
        sequence=sub,
        left_enzyme=left.enzyme if left else None,
        right_enzyme=right.enzyme if right else None,
        left_overhang=left.overhang if left else "",
        right_overhang=right.overhang if right else "",
        left_overhang_type=left.overhang_type if left else BLUNT,
        right_overhang_type=right.overhang_type if right else BLUNT,
        wraps_origin=wraps,
    )


def digest(
    sequence: str,
    enzymes: str | Any,
    *,
    circular: bool = False,
) -> DigestResult:
    """Digest ``sequence`` to completion with ``enzymes``.

    Single and double (or larger) digests are the same call — pass one name or
    several. Fragment boundaries are the top-strand cuts; each fragment records
    the enzyme and overhang at both ends, which is what decides whether two
    fragments can be ligated.

    A template with no sites returns one fragment equal to the whole input,
    with ``cut`` False. That is a legitimate experimental outcome and callers
    should not have to catch an exception to discover it.
    """
    seq = _clean(sequence)
    resolved = resolve_enzymes(enzymes)
    names = tuple(sorted(str(e) for e in resolved))
    sites = find_sites(seq, resolved, circular=circular)

    if not seq:
        return DigestResult(names, circular, 0, (), ())

    if not sites:
        whole = Fragment(
            start=0,
            end=len(seq),
            sequence=seq,
            left_enzyme=None,
            right_enzyme=None,
            left_overhang="",
            right_overhang="",
            left_overhang_type=BLUNT,
            right_overhang_type=BLUNT,
        )
        return DigestResult(names, circular, len(seq), (), (whole,))

    fragments: list[Fragment] = []

    if circular:
        # n cuts on a circle give n fragments, the last running through the
        # origin back to the first cut. One cut simply linearises the circle.
        for i, site in enumerate(sites):
            nxt = sites[(i + 1) % len(sites)]
            start = site.top_cut
            end = nxt.top_cut if i + 1 < len(sites) else sites[0].top_cut + len(seq)
            fragments.append(_fragment_between(seq, site, nxt, start, end, wraps=end > len(seq)))
    else:
        # n cuts on a linear template give n+1 fragments, the outer two keeping
        # the template's own ends.
        boundaries = [0, *[s.top_cut for s in sites], len(seq)]
        for i in range(len(boundaries) - 1):
            left = sites[i - 1] if i > 0 else None
            right = sites[i] if i < len(sites) else None
            fragments.append(_fragment_between(seq, left, right, boundaries[i], boundaries[i + 1]))

    return DigestResult(names, circular, len(seq), sites, tuple(fragments))


def double_digest(
    sequence: str,
    first: str,
    second: str,
    *,
    circular: bool = False,
) -> DigestResult:
    """Convenience wrapper: digest with two enzymes at once."""
    return digest(sequence, [first, second], circular=circular)


def available_enzymes() -> tuple[str, ...]:
    """Every enzyme name available, from REBASE via Biopython."""
    return tuple(sorted(str(e) for e in AllEnzymes))


def enzymes_cutting(sequence: str, *, circular: bool = False, batch: Any = None) -> dict[str, int]:
    """Map enzyme name to site count for the enzymes that cut ``sequence``.

    ``batch`` restricts the search; without it the whole REBASE set is
    searched, which is slow for a long template.
    """
    seq = _clean(sequence)
    if not seq:
        return {}
    search_batch = batch if batch is not None else RestrictionBatch(list(AllEnzymes))
    found = search_batch.search(Seq(seq), linear=not circular)
    return {str(enzyme): len(hits) for enzyme, hits in found.items() if hits}


#: Why each reported quantity is trustworthy. This engine makes no judgement
#: calls -- there are no thresholds and nothing to tune -- so every entry is
#: sourced and none needs a mechanism: the rules *are* the enzyme geometry.
THRESHOLD_PROVENANCE: dict[str, Provenance] = {
    "recognition_site": Provenance(
        kind=SOURCED,
        explanation=("Recognition sequences come from REBASE as distributed with Biopython."),
    ),
    "cut_position": Provenance(
        kind=SOURCED,
        explanation=(
            "Top- and bottom-strand cut offsets come from REBASE as distributed "
            "with Biopython; this module converts them to 0-based coordinates."
        ),
    ),
    "overhang": Provenance(
        kind=SOURCED,
        explanation=(
            "Overhang polarity and length come from REBASE; the overhang "
            "sequence is read from the template, which is what makes Type IIS "
            "assembly work."
        ),
    ),
}

__all__ = [
    "BLUNT",
    "DIGEST_LIMITATIONS",
    "FIVE_PRIME",
    "THREE_PRIME",
    "THRESHOLD_PROVENANCE",
    "CutSite",
    "DigestResult",
    "Fragment",
    "UnknownEnzymeError",
    "available_enzymes",
    "digest",
    "double_digest",
    "enzyme_info",
    "enzymes_cutting",
    "find_sites",
    "resolve_enzymes",
    "sites_in_region",
]

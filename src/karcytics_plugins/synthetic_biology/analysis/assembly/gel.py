"""Where a DNA fragment sits on an agarose gel. Model only — nothing is drawn.

The model
---------
Migration distance is taken as **linear in the logarithm of fragment length**:

    Rf(L) = (log10(L_max) - log10(L)) / (log10(L_max) - log10(L_min))

giving a relative mobility in [0, 1] — 0 at the well for the largest resolvable
fragment, 1 at the far end of the gel for the smallest. ``L_min``/``L_max`` are
the resolving window of the gel, not properties of the sample, so two gels of
different agarose percentage place the same fragment differently. Distance in
millimetres is ``Rf * lane_length_mm``.

What is cited and what is not
-----------------------------
That mobility depends on fragment length, and that the relationship is
calibrated against a ladder run in the same gel, is the empirical result of
Southern (1979) — registered as ``southern1979``. **The log-linear form used
here is a convention, not that paper's finding.** Southern showed mobility is
*not* strictly linear in log(length) and proposed a reciprocal relationship,
1/(L + L0), which Elder & Southern (1983) found fits better across a wide size
range. The log-linear approximation is retained because it is what a teaching
gel-reading exercise uses, is monotonic and well behaved, and needs no fitted
constants — but it is labelled a convention in
:data:`THRESHOLD_PROVENANCE` and must not be presented as a published result.

Deliberately not modelled: agarose percentage, voltage, buffer, run time,
temperature, conformation (supercoiled and nicked plasmids migrate unlike
linear DNA of the same mass), band broadening and co-migration limits of
resolution. This places bands in a size order a student can read; it does not
predict a photograph.

Intensity
---------
Ethidium-style staining intercalates along the duplex, so signal scales with
the **mass** of DNA in a band, not the number of molecules. For an equimolar
digest a 3000 bp fragment is three times as bright as a 1000 bp one. Intensity
is reported normalised to the brightest band in the lane.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from ..provenance import CONVENTION, SOURCED, Provenance

#: Resolving window of a typical 1% agarose gel, in bp. A convention: a
#: different agarose percentage resolves a different window.
DEFAULT_MIN_BP = 100
DEFAULT_MAX_BP = 10_000

#: Lane length the mobilities are scaled onto, in mm. Presentation, not physics.
DEFAULT_LANE_LENGTH_MM = 80.0


#: Resolving window per agarose percentage, in bp. A convention: these are the
#: ranges agarose suppliers quote for routine work, not a measurement, and the
#: real window also depends on voltage, buffer and run time — none of which
#: this model takes. Exposed so a student can match the gel they actually
#: poured instead of being locked to one window.
AGAROSE_WINDOWS: dict[str, tuple[int, int]] = {
    "0.7%": (800, 20_000),
    "1.0%": (100, 10_000),
    "1.5%": (80, 4_000),
    "2.0%": (50, 2_000),
    "3.0%": (20, 1_000),
}

#: The percentage used when none is chosen.
DEFAULT_AGAROSE = "1.0%"


def window_for_agarose(percentage: str) -> tuple[int, int]:
    """Resolving window for an agarose percentage, falling back to the default."""
    return AGAROSE_WINDOWS.get(percentage, AGAROSE_WINDOWS[DEFAULT_AGAROSE])


@dataclass(frozen=True)
class Ladder:
    """A size standard, as data. Sizes in bp, largest first when displayed."""

    name: str
    sizes: tuple[int, ...]
    #: Where this band list came from, and how far it should be trusted.
    #: Checked against supplier listings rather than assumed: formulations of
    #: the same trade name differ, so a band list that looks authoritative but
    #: is not would be worse than one that says what it is.
    provenance: str = ""
    #: Relative mass of each band, where the supplier loads some bands heavier
    #: as orientation markers. Empty means equimolar.
    reference_bands: tuple[int, ...] = ()
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sizes": list(self.sizes),
            "reference_bands": list(self.reference_bands),
            "note": self.note,
        }


#: Ladder definitions as published by their suppliers, as data rather than code.
#: These are *fragment size lists*, which are statements of fact about a
#: product, not empirical measurements, so they carry no citation.
LADDERS: dict[str, Ladder] = {
    "1kb": Ladder(
        name="1 kb DNA ladder",
        sizes=(10000, 8000, 6000, 5000, 4000, 3000, 2000, 1500, 1000, 500),
        reference_bands=(3000,),
        note="General-purpose ladder for products from 500 bp to 10 kb.",
    ),
    "1kb_plus": Ladder(
        name="1 kb Plus DNA ladder",
        sizes=(
            10000,
            8000,
            6000,
            5000,
            4000,
            3000,
            2000,
            1650,
            1000,
            850,
            650,
            500,
            400,
            300,
            200,
            100,
        ),
        reference_bands=(1650,),
        note=(
            "Wide range; the 1650 bp band is loaded heavier as an orientation "
            "marker, forming a doublet with the 2000 bp band."
        ),
        provenance=(
            "Representative 1 kb-plus-style band list, NOT verified against a "
            "specific catalogue number. Supplier listings for products sold "
            "under this name disagree: the range is quoted as 100-15,000 bp "
            "with 18-19 fragments including bands above 10 kb, and the "
            "orientation band is quoted as both 1,500 bp and 1,650 bp. Confirm "
            "against the datasheet for the ladder you actually run before "
            "reading a size off this gel."
        ),
    ),
    "100bp": Ladder(
        name="100 bp DNA ladder",
        sizes=(1500, 1400, 1300, 1200, 1100, 1000, 900, 800, 700, 600, 500, 400, 300, 200, 100),
        reference_bands=(500,),
        note="For small products; the resolving window is roughly 100-1500 bp.",
    ),
    "lambda_hindiii": Ladder(
        name="Lambda DNA/HindIII",
        sizes=(23130, 9416, 6557, 4361, 2322, 2027, 564, 125),
        note="A real HindIII digest of phage lambda, so band spacing is uneven.",
    ),
}


@dataclass(frozen=True)
class Band:
    """One band in a lane, ready for a renderer to place."""

    size_bp: int
    #: Relative mobility in [0, 1]: 0 at the well, 1 at the gel's far end.
    relative_mobility: float
    distance_mm: float
    #: Normalised to the brightest band in the same lane.
    intensity: float
    label: str = ""
    #: True when the fragment lies outside the gel's resolving window, so its
    #: position is clamped and must not be read as a measurement.
    out_of_range: bool = False
    #: Which edge it ran off: True above the largest resolvable fragment,
    #: False below the smallest. Decided here so a renderer does not have to
    #: infer it from the mobility value.
    off_scale_high: bool = False
    #: Sitting exactly on a window bound. Drawn as a band at the extreme and
    #: labelled "*", rather than thrown off scale: the size IS known, it is
    #: only the position that is at the limit of what the gel resolves.
    at_edge: bool = False
    #: True for a supplier's overloaded orientation band.
    is_reference: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "size_bp": self.size_bp,
            "relative_mobility": round(self.relative_mobility, 4),
            "distance_mm": round(self.distance_mm, 2),
            "intensity": round(self.intensity, 4),
            "label": self.label,
            "out_of_range": self.out_of_range,
            "off_scale_high": self.off_scale_high,
            "at_edge": self.at_edge,
            "is_reference": self.is_reference,
        }


@dataclass(frozen=True)
class Lane:
    """One lane: a ladder, a PCR product, or a digest."""

    name: str
    bands: tuple[Band, ...]
    kind: str = "sample"
    min_bp: int = DEFAULT_MIN_BP
    max_bp: int = DEFAULT_MAX_BP
    lane_length_mm: float = DEFAULT_LANE_LENGTH_MM
    notes: tuple[str, ...] = ()
    #: Carried from the Ladder so a view can describe a clicked band without
    #: reaching back into the ladder table.
    reference_bands: tuple[int, ...] = ()
    provenance: str = ""

    @property
    def sizes(self) -> tuple[int, ...]:
        return tuple(b.size_bp for b in self.bands)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "min_bp": self.min_bp,
            "max_bp": self.max_bp,
            "lane_length_mm": self.lane_length_mm,
            "bands": [b.to_dict() for b in self.bands],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class Gel:
    """A set of lanes sharing one resolving window, for a renderer to draw."""

    lanes: tuple[Lane, ...]
    min_bp: int = DEFAULT_MIN_BP
    max_bp: int = DEFAULT_MAX_BP
    lane_length_mm: float = DEFAULT_LANE_LENGTH_MM
    model: str = "log-linear"
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def lane_kinds(self) -> tuple[str, ...]:
        """The kinds of lane on this gel, excluding the ladder."""
        return tuple(lane.kind for lane in self.lanes if lane.kind != "ladder")

    @property
    def limitations(self) -> tuple[tuple[str, str], ...]:
        """Caveats that apply to what this gel actually shows."""
        return limitations_for(self.lane_kinds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "min_bp": self.min_bp,
            "max_bp": self.max_bp,
            "lane_length_mm": self.lane_length_mm,
            "lanes": [lane.to_dict() for lane in self.lanes],
            "notes": list(self.notes),
        }


# ── The model ──────────────────────────────────────────────────────────


def relative_mobility(
    size_bp: float,
    *,
    min_bp: int = DEFAULT_MIN_BP,
    max_bp: int = DEFAULT_MAX_BP,
) -> float:
    """Relative mobility of a fragment, 0 at the well and 1 at the gel's end.

    Log-linear in size, clamped to the resolving window: a fragment larger than
    ``max_bp`` sits at the well and one smaller than ``min_bp`` runs off the
    end, neither of which is a measurement. See the module docstring for why
    the log-linear form is a convention.
    """
    if size_bp <= 0:
        raise ValueError(f"fragment size must be positive, got {size_bp}")
    if min_bp <= 0 or max_bp <= min_bp:
        raise ValueError(f"invalid resolving window: {min_bp}-{max_bp} bp")

    if size_bp >= max_bp:
        return 0.0
    if size_bp <= min_bp:
        return 1.0
    span = math.log10(max_bp) - math.log10(min_bp)
    return (math.log10(max_bp) - math.log10(size_bp)) / span


def is_resolvable(
    size_bp: float, *, min_bp: int = DEFAULT_MIN_BP, max_bp: int = DEFAULT_MAX_BP
) -> bool:
    """Whether this fragment lies within the gel's resolving window.

    Inclusive of the bounds. It used to be strict, which made a fragment of
    exactly 100 or exactly 10000 bp "unresolvable" -- so the 1 kb Plus
    ladder's own top and bottom bands were flagged and, once off-scale
    markers were introduced, vanished from the gel entirely. A fragment
    sitting exactly on the window edge is at the edge, not beyond it.
    """
    return min_bp <= size_bp <= max_bp


def is_at_edge(
    size_bp: float, *, min_bp: int = DEFAULT_MIN_BP, max_bp: int = DEFAULT_MAX_BP
) -> bool:
    """Whether the fragment sits exactly on a bound, where position is extreme."""
    return size_bp in (min_bp, max_bp)


def _bands(  # noqa: PLR0913 - each argument is an independent lane property
    sizes: list[int],
    *,
    min_bp: int,
    max_bp: int,
    lane_length_mm: float,
    masses: dict[int, float] | None = None,
    labels: dict[int, str] | None = None,
    reference_bands: tuple[int, ...] = (),
) -> tuple[Band, ...]:
    """Build bands, merging equal sizes because they co-migrate as one band."""
    labels = labels or {}
    merged: dict[int, float] = {}
    for size in sizes:
        # Two fragments of the same length cannot be separated, so their mass
        # adds into a single brighter band rather than producing two.
        weight = (masses or {}).get(size, float(size))
        merged[size] = merged.get(size, 0.0) + weight

    brightest = max(merged.values()) if merged else 1.0
    bands = []
    for size in sorted(merged, reverse=True):
        rf = relative_mobility(size, min_bp=min_bp, max_bp=max_bp)
        count = sizes.count(size)
        label = labels.get(size) or (f"{size} bp" + (f" (x{count})" if count > 1 else ""))
        bands.append(
            Band(
                size_bp=size,
                relative_mobility=rf,
                distance_mm=rf * lane_length_mm,
                intensity=merged[size] / brightest if brightest else 0.0,
                label=label,
                out_of_range=not is_resolvable(size, min_bp=min_bp, max_bp=max_bp),
                off_scale_high=size > max_bp,
                at_edge=is_at_edge(size, min_bp=min_bp, max_bp=max_bp),
                is_reference=size in reference_bands,
            )
        )
    return tuple(bands)


def ladder_lane(
    ladder: str | Ladder = "1kb_plus",
    *,
    min_bp: int = DEFAULT_MIN_BP,
    max_bp: int = DEFAULT_MAX_BP,
    lane_length_mm: float = DEFAULT_LANE_LENGTH_MM,
) -> Lane:
    """Build the size-standard lane."""
    definition = LADDERS[ladder] if isinstance(ladder, str) else ladder
    masses = {
        size: float(size) * (2.5 if size in definition.reference_bands else 1.0)
        for size in definition.sizes
    }
    return Lane(
        name=definition.name,
        kind="ladder",
        bands=_bands(
            list(definition.sizes),
            min_bp=min_bp,
            max_bp=max_bp,
            lane_length_mm=lane_length_mm,
            masses=masses,
            reference_bands=definition.reference_bands,
        ),
        min_bp=min_bp,
        max_bp=max_bp,
        lane_length_mm=lane_length_mm,
        notes=(definition.note,) if definition.note else (),
        reference_bands=definition.reference_bands,
        provenance=definition.provenance,
    )


def product_lane(
    length_bp: int,
    *,
    name: str = "PCR product",
    min_bp: int = DEFAULT_MIN_BP,
    max_bp: int = DEFAULT_MAX_BP,
    lane_length_mm: float = DEFAULT_LANE_LENGTH_MM,
) -> Lane:
    """One lane for a single PCR product."""
    return Lane(
        name=name,
        kind="pcr_product",
        bands=_bands(
            [int(length_bp)],
            min_bp=min_bp,
            max_bp=max_bp,
            lane_length_mm=lane_length_mm,
        ),
        min_bp=min_bp,
        max_bp=max_bp,
        lane_length_mm=lane_length_mm,
    )


def digest_lane(
    fragment_lengths: Any,
    *,
    name: str = "Digest",
    min_bp: int = DEFAULT_MIN_BP,
    max_bp: int = DEFAULT_MAX_BP,
    lane_length_mm: float = DEFAULT_LANE_LENGTH_MM,
) -> Lane:
    """One lane for a digest, which usually has several fragments.

    Accepts fragment lengths, or the ``DigestResult`` from
    :mod:`restriction` directly.
    """
    lengths = getattr(fragment_lengths, "fragment_lengths", fragment_lengths)
    sizes = [int(n) for n in lengths]
    notes = []
    if len(sizes) != len(set(sizes)):
        notes.append(
            "Fragments of equal length co-migrate as one brighter band; the "
            "band count is lower than the fragment count."
        )
    return Lane(
        name=name,
        kind="digest",
        bands=_bands(sizes, min_bp=min_bp, max_bp=max_bp, lane_length_mm=lane_length_mm),
        min_bp=min_bp,
        max_bp=max_bp,
        lane_length_mm=lane_length_mm,
        notes=tuple(notes),
    )


def _reposition(lane: Lane, min_bp: int, max_bp: int, lane_length_mm: float) -> Lane:
    """Re-place a lane's bands on a different resolving window.

    A lane built with the default window carries positions computed against it.
    Dropping that lane into a gel with a different window would leave the band
    positions disagreeing with the axis the gel advertises, and the two lanes
    would no longer be comparable — which is the one thing a gel is for.
    Mobility depends only on size and the window, so the bands are re-placed
    while intensity and labels, which do not, are kept.
    """
    if (lane.min_bp, lane.max_bp, lane.lane_length_mm) == (min_bp, max_bp, lane_length_mm):
        return lane

    moved = []
    for band in lane.bands:
        rf = relative_mobility(band.size_bp, min_bp=min_bp, max_bp=max_bp)
        moved.append(
            Band(
                size_bp=band.size_bp,
                relative_mobility=rf,
                distance_mm=rf * lane_length_mm,
                intensity=band.intensity,
                label=band.label,
                out_of_range=not is_resolvable(band.size_bp, min_bp=min_bp, max_bp=max_bp),
                off_scale_high=band.size_bp > max_bp,
                at_edge=is_at_edge(band.size_bp, min_bp=min_bp, max_bp=max_bp),
                is_reference=band.is_reference,
            )
        )
    return Lane(
        name=lane.name,
        bands=tuple(moved),
        kind=lane.kind,
        min_bp=min_bp,
        max_bp=max_bp,
        lane_length_mm=lane_length_mm,
        notes=lane.notes,
        reference_bands=lane.reference_bands,
        provenance=lane.provenance,
    )


def build_gel(
    lanes: Any,
    *,
    ladder: str | Ladder | None = "1kb_plus",
    min_bp: int = DEFAULT_MIN_BP,
    max_bp: int = DEFAULT_MAX_BP,
    lane_length_mm: float = DEFAULT_LANE_LENGTH_MM,
) -> Gel:
    """Assemble lanes into a gel, with the ladder first if one is named."""
    collected: list[Lane] = []
    if ladder is not None:
        collected.append(
            ladder_lane(ladder, min_bp=min_bp, max_bp=max_bp, lane_length_mm=lane_length_mm)
        )
    collected.extend(lanes)
    # One window for the whole gel, so every lane is on the same axis.
    collected = [_reposition(lane, min_bp, max_bp, lane_length_mm) for lane in collected]

    notes = []
    if any(b.out_of_range for lane in collected for b in lane.bands):
        notes.append(
            f"Some fragments fall outside the {min_bp}-{max_bp} bp resolving "
            "window. They are shown off scale rather than placed at the edge, "
            "because this gel cannot resolve a size for them."
        )
    return Gel(
        lanes=tuple(collected),
        min_bp=min_bp,
        max_bp=max_bp,
        lane_length_mm=lane_length_mm,
        notes=tuple(notes),
    )


#: What a gel of each kind does not model. Chosen by what the gel actually
#: contains: a PCR-only gel was showing the restriction-digest caveats
#: (methylation sensitivity, star activity, isoschizomers), which say nothing
#: about a PCR and leave its real failure modes unmentioned.
PCR_LIMITATIONS: tuple[tuple[str, str], ...] = (
    (
        "primer-dimers",
        "Primers that prime each other give a small, often bright band near "
        "the dye front. The screening engine reports dimer free energies, but "
        "no dimer product is placed on this gel.",
    ),
    (
        "non-specific amplification",
        "Partial matches elsewhere on the template can prime at low annealing "
        "temperatures and give extra bands that this model does not predict.",
    ),
    (
        "secondary structure",
        "Hairpins in the template can stall the polymerase, weakening or "
        "removing a band that is predicted here.",
    ),
    (
        "polymerase errors",
        "Misincorporation is not modelled; every predicted product is an exact "
        "copy of the template between the primers.",
    ),
    (
        "yield and band intensity",
        "Intensity here follows fragment mass only. Real brightness depends on "
        "amplification efficiency, cycle number and template amount.",
    ),
)


def limitations_for(kinds: Any) -> tuple[tuple[str, str], ...]:
    """The caveats that apply to a gel carrying lanes of these kinds.

    A gel showing a PCR product and its digest gets both sets, in that order,
    because both reactions stand between the prediction and the photograph.
    """
    from .restriction import DIGEST_LIMITATIONS

    present = set(kinds or ())
    chosen: list[tuple[str, str]] = []
    if present & {"pcr_product", "sample"}:
        chosen.extend(PCR_LIMITATIONS)
    if "digest" in present:
        chosen.extend(DIGEST_LIMITATIONS)
    if not chosen:
        chosen.extend(PCR_LIMITATIONS)
    return tuple(chosen)


#: Provenance per field. The mobility model is the one place this module could
#: overclaim, so its entry records the paper that was weighed and declined.
THRESHOLD_PROVENANCE: dict[str, Provenance] = {
    "mobility_model": Provenance(
        kind=CONVENTION,
        explanation=(
            "Migration linear in log10(size) is a teaching approximation. The "
            "size-dependence itself is an empirical result and is cited; this "
            "particular functional form is not. Southern (1979) showed "
            "mobility is not strictly log-linear and proposed a reciprocal "
            "relationship, and Elder & Southern (1983) compared the forms."
        ),
        rejected=(
            (
                "Aaij & Borst (1972), Biochim. Biophys. Acta 269:192-200, "
                "doi:10.1016/0005-2787(72)90426-1",
                "Considered as a source for the log-linear form itself, and "
                "declined because its content could not be verified. The paper "
                "is real and correctly identified (PMID 5063906), but no "
                "abstract is indexed in PubMed, Crossref, OpenAlex or Europe "
                "PMC, and the full text is paywalled. A secondary fragment "
                "suggested it may in fact report mobility as NOT linear in log "
                "MW for linear DNA above ~1e6 Da in 1% gels, which would "
                "argue against the sourced label, but that is equally "
                "unverified. Citing it unread would make the claim look "
                "checked when it is not.",
            ),
        ),
    ),
    "resolving_window": Provenance(
        kind=CONVENTION,
        explanation=(
            "The window is the range an agarose percentage resolves, as "
            "suppliers quote it for routine work rather than as a measured "
            "result. The real window also depends on voltage, buffer and run "
            "time, none of which this model takes."
        ),
    ),
    "lane_length_mm": Provenance(
        kind=CONVENTION,
        explanation="A presentation scale for a renderer, not a physical quantity.",
    ),
    "intensity": Provenance(
        kind=CONVENTION,
        explanation=(
            "Intensity proportional to band mass follows from intercalating "
            "dye binding along the duplex. The proportionality is conventional "
            "and ignores saturation and the dye's own size preference."
        ),
        rejected=(
            (
                "Le Pecq & Paoletti (1967), J. Mol. Biol. 27:87-106, "
                "doi:10.1016/0022-2836(67)90353-1",
                "Considered as the source for ethidium fluorescence scaling "
                "with bound DNA, and declined for the same reason as Aaij & "
                "Borst: no abstract is indexed anywhere (PMID 6033613) and the "
                "full text is paywalled, so the claim could not be checked "
                "against the paper.",
            ),
        ),
    ),
    "ladder_sizes": Provenance(
        kind=SOURCED,
        explanation=(
            "Fragment sizes are as published by the ladder's supplier; they "
            "state a product's composition rather than an experimental "
            "measurement."
        ),
    ),
}

__all__ = [
    "AGAROSE_WINDOWS",
    "DEFAULT_AGAROSE",
    "DEFAULT_LANE_LENGTH_MM",
    "DEFAULT_MAX_BP",
    "DEFAULT_MIN_BP",
    "LADDERS",
    "THRESHOLD_PROVENANCE",
    "Band",
    "Gel",
    "Ladder",
    "Lane",
    "build_gel",
    "digest_lane",
    "is_at_edge",
    "is_resolvable",
    "ladder_lane",
    "product_lane",
    "relative_mobility",
    "window_for_agarose",
]

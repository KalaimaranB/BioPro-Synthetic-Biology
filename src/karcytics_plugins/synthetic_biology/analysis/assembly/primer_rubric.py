"""Thresholds a PCR primer pair is judged against, as data rather than code.

A course sets what counts as an acceptable primer, and courses disagree. Every
threshold the screening layer applies lives here, is overridable, and is
loadable from JSON, so a department can ship its own rubric without editing
Python. Nothing in :mod:`primer_screen` carries a literal threshold.

Provenance of the defaults
--------------------------
Two kinds of number appear below, and they are not equivalent:

* **Convention** — long-standing community practice in primer design, not a
  measured result. The 40-60% GC window and the 3' clamp rule are of this kind:
  they are widely taught and widely used, but they are rules of thumb, and no
  citation would honestly support them as empirical findings. Per this module's
  citation rule, these cite nothing and are labelled a convention wherever they
  are shown to a user. ``source`` is ``CONVENTION`` for each.
* **Sourced** — derived from a published model. Only the free-energy cutoffs
  are in this category, and even then only partly: the *model* that computes
  ΔG is SantaLucia & Hicks (2004), but the *cutoff* chosen on that scale is
  still a convention. ``source`` records the distinction.

``THRESHOLD_PROVENANCE`` below states this per field, and is what the UI reads
to label a value; it is not decorative.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..provenance import CONVENTION, SOURCED, Provenance

#: Re-exported from ``analysis.provenance`` so existing importers of
#: ``primer_rubric.CONVENTION`` keep working; the definitions now live in one
#: place alongside the mechanism category.
__all_provenance__ = (CONVENTION, SOURCED)


@dataclass(frozen=True)
class PrimerRubric:
    """Every threshold the screening layer applies.

    Lengths are in bases, temperatures in °C, free energies in kcal/mol.

    Free-energy fields are *upper bounds on stability*: a structure is reported
    as failing when its ΔG is **more negative** than the cutoff, because more
    negative means more stable and therefore more likely to compete with
    priming.
    """

    # ── Composition ────────────────────────────────────────────────────
    gc_min_percent: float = 40.0
    gc_max_percent: float = 60.0
    #: Window at the 3' end inspected for the G/C clamp, in bases.
    clamp_window: int = 5
    #: Permitted count of G or C within that window. The upper bound matters as
    #: much as the lower: a 3' end that is all G/C promotes mispriming.
    clamp_min_gc: int = 1
    clamp_max_gc: int = 3
    #: Longest permitted run of a single base (AAAA..., GGGG...).
    max_poly_run: int = 4

    # ── Pairing ────────────────────────────────────────────────────────
    #: Largest permitted |Tm(fwd) − Tm(rev)|.
    pair_tm_tolerance: float = 5.0
    product_min_bp: int = 100
    product_max_bp: int = 3000

    # ── Secondary structure (ΔG°37, kcal/mol) ──────────────────────────
    hairpin_min_dg: float = -3.0
    self_dimer_min_dg: float = -6.0
    hetero_dimer_min_dg: float = -6.0
    #: A 3'-anchored duplex primes; an internal one mostly does not. Stacking
    #: that reaches within this many bases of a 3' end is scored against the
    #: stricter cutoff below.
    three_prime_window: int = 5
    three_prime_dimer_min_dg: float = -4.0

    # ── Candidate generation ───────────────────────────────────────────
    min_length: int = 18
    max_length: int = 30
    #: How far the annealing start may slide from the requested end of the
    #: target. 0 reproduces the original fixed-end behaviour.
    max_offset: int = 12
    target_tm: float = 60.0

    #: Free-form label so a saved workspace records which rubric judged it.
    name: str = "Karcytics default"

    # ── Serialisation ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PrimerRubric:
        """Build a rubric from a mapping, ignoring keys this version does not know.

        Unknown keys are dropped rather than raising: a rubric file written for
        a later version should still load, minus the fields that did not exist.
        """
        if not data:
            return cls()
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def from_json(cls, path: str | Path) -> PrimerRubric:
        """Load a rubric from a JSON file, e.g. a course's own thresholds."""
        with open(path, encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))

    def _window_problems(self) -> list[str]:
        """Ranges whose lower bound sits above the upper."""
        problems: list[str] = []
        for low, high, label in (
            ("gc_min_percent", "gc_max_percent", "gc_min_percent is above gc_max_percent"),
            ("clamp_min_gc", "clamp_max_gc", "clamp_min_gc is above clamp_max_gc"),
            ("min_length", "max_length", "min_length is above max_length"),
            ("product_min_bp", "product_max_bp", "product_min_bp is above product_max_bp"),
        ):
            if getattr(self, low) > getattr(self, high):
                problems.append(label)
        return problems

    def _bound_problems(self) -> list[str]:
        """Individual values outside the range that makes them meaningful."""
        problems: list[str] = []
        if self.clamp_window <= 0:
            problems.append("clamp_window must be at least 1")
        elif self.clamp_max_gc > self.clamp_window:
            problems.append("clamp_max_gc exceeds clamp_window, so it can never fail")
        if self.max_offset < 0:
            problems.append("max_offset cannot be negative")
        if self.max_poly_run < 1:
            problems.append("max_poly_run must be at least 1")
        for name in ("hairpin_min_dg", "self_dimer_min_dg", "hetero_dimer_min_dg"):
            if getattr(self, name) > 0:
                problems.append(f"{name} should be a negative free energy")
        return problems

    def validate(self) -> list[str]:
        """Return a list of self-inconsistencies, empty when the rubric is usable.

        Checked rather than assumed: a rubric is user-supplied data, and an
        inverted window would otherwise fail every candidate with no
        explanation.
        """
        return self._window_problems() + self._bound_problems()


#: Where each threshold's default comes from, and the wording a view shows.
#:
#: Keep every field of :class:`PrimerRubric` that is a threshold represented
#: here; ``test_primer_rubric`` asserts the mapping stays complete, so a new
#: threshold cannot be added without declaring its provenance.
THRESHOLD_PROVENANCE: dict[str, Provenance] = {
    "gc_min_percent": Provenance(
        kind=CONVENTION,
        explanation=("40-60% GC is standard primer-design practice, not a measured result."),
    ),
    "gc_max_percent": Provenance(
        kind=CONVENTION,
        explanation=("40-60% GC is standard primer-design practice, not a measured result."),
    ),
    "clamp_window": Provenance(
        kind=CONVENTION,
        explanation=("Inspecting the last 5 bases for a G/C clamp is convention."),
    ),
    "clamp_min_gc": Provenance(
        kind=CONVENTION,
        explanation=("Requiring at least one 3' G or C is convention."),
    ),
    "clamp_max_gc": Provenance(
        kind=CONVENTION,
        explanation=("Capping 3' G/C to discourage mispriming is convention."),
    ),
    "max_poly_run": Provenance(
        kind=CONVENTION,
        explanation=("Avoiding runs of four or more identical bases is convention."),
    ),
    "pair_tm_tolerance": Provenance(
        kind=CONVENTION,
        explanation=(
            "Matching the pair to within 5 °C is convention; the Tm values themselves are computed from a published nearest-neighbour model."
        ),
    ),
    "product_min_bp": Provenance(
        kind=CONVENTION,
        explanation=("Product-size limits are set by the experiment, not by theory."),
    ),
    "product_max_bp": Provenance(
        kind=CONVENTION,
        explanation=("Product-size limits are set by the experiment, not by theory."),
    ),
    "hairpin_min_dg": Provenance(
        kind=CONVENTION,
        explanation=(
            "The cutoff is a convention; the ΔG it is compared against is computed with the SantaLucia & Hicks (2004) nearest-neighbour parameters."
        ),
    ),
    "self_dimer_min_dg": Provenance(
        kind=CONVENTION,
        explanation=(
            "The cutoff is a convention; the ΔG it is compared against is computed with the SantaLucia & Hicks (2004) nearest-neighbour parameters."
        ),
    ),
    "hetero_dimer_min_dg": Provenance(
        kind=CONVENTION,
        explanation=(
            "The cutoff is a convention; the ΔG it is compared against is computed with the SantaLucia & Hicks (2004) nearest-neighbour parameters."
        ),
    ),
    "three_prime_window": Provenance(
        kind=CONVENTION,
        explanation=(
            "Treating the last 5 bases as the priming end is convention; the "
            "count of 5 is ours. That the 3' end is what decides whether a "
            "duplex primes is not."
        ),
        mechanism=("newton1989",),
        mechanism_claim=(
            "Newton et al. (1989) demonstrated that an oligonucleotide "
            "mismatched at its 3' residue does not function as a primer, which "
            "is why this module judges 3'-anchored structures differently from "
            "internal ones. The paper does not support a window of 5 bases."
        ),
    ),
    "three_prime_dimer_min_dg": Provenance(
        kind=CONVENTION,
        explanation=(
            "A stricter cutoff for 3'-anchored duplexes is a convention; the value is ours."
        ),
        mechanism=("newton1989",),
        mechanism_claim=(
            "A duplex involving the 3' terminus can prime, so it competes with "
            "the template in a way an internal duplex does not (Newton et al. "
            "1989). The cutoff value itself is not supported by that paper."
        ),
    ),
    "min_length": Provenance(
        kind=CONVENTION,
        explanation=("18-30 nt is standard primer-length practice."),
    ),
    "max_length": Provenance(
        kind=CONVENTION,
        explanation=("18-30 nt is standard primer-length practice."),
    ),
    "max_offset": Provenance(
        kind=CONVENTION,
        explanation=("How far the search may slide is a search setting, not a result."),
    ),
    "target_tm": Provenance(
        kind=CONVENTION,
        explanation=("A 60 °C target is convention; the Tm model behind it is published."),
    ),
}

#: Fields of PrimerRubric that are labels rather than thresholds.
NON_THRESHOLD_FIELDS: frozenset[str] = frozenset({"name"})


DEFAULT_RUBRIC = PrimerRubric()

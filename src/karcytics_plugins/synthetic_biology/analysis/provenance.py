"""Where a number or a rule in this module comes from, in three categories.

The module used to sort every value into two buckets: ``sourced`` (it follows
from a published model) or ``convention`` (it is our own practice and cites
nothing). That is right for *numbers* and wrong for *rules*, because it has no
place for a third thing:

    the published finding that justifies a rule's **shape**, as distinct from
    the value of its parameters.

The clear case is the priming rule in :mod:`assembly.amplification`. Its
numbers — a 5-base exact 3' window, 2 mismatches tolerated upstream — are
conventions, chosen by us, and must keep citing nothing. But the *reason the
rule has that shape at all* is an empirical result about enzyme biochemistry:
an oligonucleotide with a mismatched 3' residue does not prime. Under a
two-category scheme that claim reaches the student in the generated methods
paragraph with no citation, because the field it belongs to is correctly
labelled a convention.

So :class:`Provenance` carries both at once. A field can say: *my parameters
are a convention, and my mechanism is this paper.*

Reading it
----------
``Provenance`` unpacks and indexes like the ``(kind, explanation)`` tuple it
replaces, so existing readers keep working::

    kind, explanation = THRESHOLD_PROVENANCE["gc_min_percent"]
    kind = THRESHOLD_PROVENANCE["gc_min_percent"][0]

New code should use the attributes, and the UI should use
:meth:`Provenance.label` and :attr:`Provenance.mechanism` so the three-way
distinction reaches the screen. It is worthless if it only exists in the source.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

#: The value follows from a published model or a published dataset.
SOURCED = "sourced"

#: The value is our own practice. It cites nothing, deliberately.
CONVENTION = "convention"

#: Not a `kind`. Marks that a rule's *shape* rests on a published finding even
#: when its parameters are conventions — see the module docstring.
MECHANISM = "mechanism"

VALID_KINDS = (SOURCED, CONVENTION)


@dataclass(frozen=True)
class Provenance:
    """Why one reported value or rule can be trusted, and how far.

    Attributes:
        kind: ``SOURCED`` or ``CONVENTION``, describing the *parameter value*.
        explanation: Prose shown next to the value. For a convention this says
            plainly that it is not a measured result.
        mechanism: Citation keys supporting the rule's **shape**, not its
            parameters. Empty when the rule has no published mechanism, which
            is the honest answer for most thresholds.
        mechanism_claim: The exact claim those keys support, written out so the
            attachment is auditable. A citation that does not support the
            specific claim it is attached to is worse than none, because it
            looks checked.
        rejected: Papers considered for the mechanism and deliberately *not*
            cited, each with the reason. Recorded because the reasoning is the
            artifact — a later reader should not have to redo the search to
            discover a candidate was already weighed and declined.
    """

    kind: str
    explanation: str
    mechanism: tuple[str, ...] = ()
    mechanism_claim: str = ""
    rejected: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in VALID_KINDS:
            raise ValueError(f"kind must be one of {VALID_KINDS}, got {self.kind!r}")
        if self.mechanism and not self.mechanism_claim:
            raise ValueError(
                "a mechanism citation must say which claim it supports; set mechanism_claim"
            )

    # ── Back-compatible tuple shape ────────────────────────────────────

    def __iter__(self) -> Iterator[str]:
        """Yield exactly ``kind, explanation``, as the old 2-tuple did."""
        yield self.kind
        yield self.explanation

    def __getitem__(self, index: int) -> str:
        return (self.kind, self.explanation)[index]

    # ── For display ────────────────────────────────────────────────────

    @property
    def has_mechanism(self) -> bool:
        return bool(self.mechanism)

    def label(self) -> str:
        """A short phrase for a UI badge, covering all three states."""
        if self.kind == SOURCED:
            return "published value"
        if self.has_mechanism:
            return "our threshold, published mechanism"
        return "our convention"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label(),
            "explanation": self.explanation,
            "mechanism": list(self.mechanism),
            "mechanism_claim": self.mechanism_claim,
            "rejected": [{"citation": c, "reason": r} for c, r in self.rejected],
        }


def mechanism_keys(*tables: dict[str, Provenance]) -> tuple[str, ...]:
    """Every citation key any mechanism in ``tables`` depends on, deduplicated."""
    seen: dict[str, None] = {}
    for table in tables:
        for entry in table.values():
            for key in entry.mechanism:
                seen.setdefault(key, None)
    return tuple(seen)


__all__ = [
    "CONVENTION",
    "MECHANISM",
    "SOURCED",
    "VALID_KINDS",
    "Provenance",
    "mechanism_keys",
]

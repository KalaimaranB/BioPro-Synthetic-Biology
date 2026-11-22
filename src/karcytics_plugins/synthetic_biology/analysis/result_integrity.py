"""Whether a payload may be presented to a user as a result.

The rule
--------
**No view may present a payload as a result when that payload's own flags say
it is mock, invalid, failed or demonstration data. Where such a payload is
shown at all, its status is shown with it and is the most prominent thing on
screen.**

Why the rule exists rather than two patches
-------------------------------------------
Audit findings C-3 and C-4 were the same defect twice, and in both the
analysis layer was already honest:

* ``NGSAlignmentService.align_ngs_reads`` returns three fabricated variant
  calls for any file, sets ``is_mock=True``, and carries a status beginning
  "MOCK DEMO DATA". ``_on_ngs_aligned`` read neither field and tabulated the
  variants as findings from the user's own sequencing run — one of them
  labelled Critical, at a hardcoded position with a hardcoded score.
* ``CircuitMLOptimizationEngine.fit_kinetic_parameters`` built its target
  curves from the simulator's own output when no flow-cytometry data was
  present, then reported "Hill parameters optimized against empirical
  dataset". It never looked at ``FCSEventData.is_valid``.

Each could have been fixed where it stood. Fixing them that way leaves the
next view free to do it again, which is why the judgement lives here, once, in
a module every consumer can reach. ``assess`` is the only place that decides
what a flag combination means; a view asks and renders the answer.

Keeping it in ``analysis/`` is deliberate. "Is this payload presentable as a
result" is a statement about data integrity, not about layout, and the
standing rule is that no view may hold such a judgement. The rendering of the
verdict is a view's business and lives in ``ui/widgets/integrity_banner.py``.

This module reads flags by duck-typing rather than importing the payload
classes, so a new result type is covered the moment it carries the same field
names, and so ``analysis/`` grows no new internal coupling.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: The payload is a real result computed from the user's own input.
TRUSTWORTHY = "trustworthy"

#: The payload is fabricated for demonstration. It describes nothing the user
#: supplied, whatever it was computed from.
DEMO = "demo"

#: The payload is real in intent but its inputs did not load or did not
#: validate, so its numbers describe nothing.
INVALID = "invalid"

#: The computation was attempted and reported its own failure.
FAILED = "failed"

#: Every level other than this one must not be presented as a result.
PRESENTABLE_LEVELS = (TRUSTWORTHY,)

#: Headline shown in place of, or above, the numbers. Short enough for a banner
#: and specific enough to act on.
_HEADLINES = {
    DEMO: "Demonstration data — not computed from your file",
    INVALID: "No usable input — these numbers describe nothing",
    FAILED: "This run did not complete",
}


@dataclass(frozen=True)
class ResultIntegrity:
    """The verdict on one payload.

    Attributes:
        level: One of :data:`TRUSTWORTHY`, :data:`DEMO`, :data:`INVALID`,
            :data:`FAILED`.
        headline: Short phrase for a banner. Empty when trustworthy.
        detail: The payload's own explanation, preserved verbatim so a view
            never paraphrases an engine's reason.
    """

    level: str
    headline: str = ""
    detail: str = ""

    @property
    def presentable(self) -> bool:
        """True when a view may render this payload's numbers as a result."""
        return self.level in PRESENTABLE_LEVELS

    @property
    def must_warn(self) -> bool:
        """True when a view must show the status prominently if it shows anything."""
        return not self.presentable

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "headline": self.headline,
            "detail": self.detail,
            "presentable": self.presentable,
        }


def _flag(payload: Any, name: str, default: Any = None) -> Any:
    return getattr(payload, name, default)


def assess(payload: Any) -> ResultIntegrity:
    """Decide whether ``payload`` may be presented to a user as a result.

    Checked in order of how badly the payload would mislead: demonstration
    data first, because a fabricated number that looks computed is worse than
    an obvious failure; then invalid input; then self-reported failure.

    A payload carrying none of these flags is trustworthy. That default is
    safe only because the flags are opt-in on the engine side and every engine
    that can produce untrustworthy output already sets one — which the
    layer-wide test in ``tests/unit/test_mock_data_never_reaches_user.py``
    enforces.

    Args:
        payload: Any result object. Flags are read by name, so this works for
            any type carrying ``is_mock``, ``is_valid``, ``success``,
            ``status_message`` or ``error_message``.

    Returns:
        A :class:`ResultIntegrity`.
    """
    if payload is None:
        return ResultIntegrity(INVALID, _HEADLINES[INVALID], "No result was produced.")

    status = str(_flag(payload, "status_message", "") or "")
    error = str(_flag(payload, "error_message", "") or "")

    if _flag(payload, "is_mock", False):
        return ResultIntegrity(DEMO, _HEADLINES[DEMO], status)

    # `is_valid` is only meaningful when the payload defines it; a payload
    # without the field must not be read as invalid.
    if _flag(payload, "is_valid", True) is False:
        return ResultIntegrity(INVALID, _HEADLINES[INVALID], error or status)

    if _flag(payload, "success", True) is False:
        return ResultIntegrity(FAILED, _HEADLINES[FAILED], status or error)

    return ResultIntegrity(TRUSTWORTHY)


def require_presentable(payload: Any) -> ResultIntegrity:
    """Assess ``payload`` and return the verdict, for a caller that will branch.

    A convenience for the common view shape::

        verdict = require_presentable(result)
        self.banner.show_verdict(verdict)
        if not verdict.presentable:
            return
    """
    return assess(payload)


__all__ = [
    "DEMO",
    "FAILED",
    "INVALID",
    "PRESENTABLE_LEVELS",
    "TRUSTWORTHY",
    "ResultIntegrity",
    "assess",
    "require_presentable",
]

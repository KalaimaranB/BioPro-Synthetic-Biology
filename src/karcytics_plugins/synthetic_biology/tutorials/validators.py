"""Validators the plasmid-assembly course checks the workspace against.

Each one answers a single yes/no question about what the learner has actually
done, and — this is the part that matters pedagogically — says *why* when the
answer is no. ``IValidator.describe_failure()`` returns a
:class:`~karcytics_sdk.plugin.tutorial_models.ValidationFailure` whose
``reason`` is shown in Cyto's bubble, so a student who is stuck is told which
of several possible mistakes they made instead of watching a Next button stay
grey.

Two rules hold throughout:

* **Read the snapshot, never the widgets.** Every validator here reads
  :class:`~.context.SynBioAcademyContext` (and, where the question is about
  saved work rather than what is on screen, ``SynBioState``). See that
  module's docstring for why.
* **Verify the analysis, not the view.** Where a step claims the learner ran
  something, the validator prefers the Methods log over the screen: a redrawn
  gel with a stale product behind it would pass a "is a gel visible" check and
  fail the lesson's actual intent.

No Qt imports.
"""

from __future__ import annotations

from typing import Any

from karcytics_sdk.plugin.tutorial_models import IValidator, ValidationFailure

from .context import SynBioAcademyContext

#: Below this, a sequence is too short to design a sensible primer pair
#: against, and the dialog will rank nothing. A convention for teaching, not a
#: biological limit — a 60 bp template is legal, just not instructive.
MIN_TEACHABLE_BP = 100


def _context(context: Any) -> SynBioAcademyContext:
    """The snapshot, or an empty one when the panel offered nothing.

    A validator must never raise: the driver polls it on a timer, and an
    exception there would take the overlay down mid-lesson rather than simply
    leaving the step unsatisfied.
    """
    return context if isinstance(context, SynBioAcademyContext) else SynBioAcademyContext()


class _ContextValidator(IValidator):
    """Base for validators whose question is about what is on screen.

    ``IValidator.validate()`` is abstract and takes only the state, but every
    validator below asks something the state cannot answer — whether a dialog
    is open, which tab is showing, how many rows the table holds. Those
    override ``check()``/``describe()``, which the Academy actually calls and
    which receive the context too. This supplies the one unreachable
    ``validate()`` they all need, so the intent is stated once instead of
    copied five times.
    """

    def validate(self, app_state: Any) -> bool:  # noqa: ARG002 - signature set by IValidator
        """Never reached: subclasses override ``check()``, which is what runs."""
        return False


class PlasmidLoaded(IValidator):
    """A sequence is loaded and is long enough to teach with."""

    def validate(self, app_state: Any) -> bool:
        getter = getattr(app_state, "get_active_plasmid", None)
        if not callable(getter):
            return False
        plasmid = getter()
        return plasmid is not None and len(getattr(plasmid, "sequence", "")) >= MIN_TEACHABLE_BP

    def describe_failure(self, app_state: Any) -> ValidationFailure | None:
        getter = getattr(app_state, "get_active_plasmid", None)
        plasmid = getter() if callable(getter) else None
        if plasmid is None:
            return ValidationFailure(
                reason=(
                    "Nothing is loaded yet. Use **📋 Paste Sequence** or **📁 Import File** — "
                    "raw bases, FASTA and GenBank all work."
                )
            )
        length = len(getattr(plasmid, "sequence", ""))
        return ValidationFailure(
            reason=(
                f"**{getattr(plasmid, 'name', 'That sequence')}** is only {length} bp. "
                f"Load something at least {MIN_TEACHABLE_BP} bp so there is room for a "
                "primer pair and a product between them."
            )
        )


class PrimerDialogOpen(_ContextValidator):
    """The primer-design dialog is on screen."""

    def check(self, app_state: Any, context: Any = None) -> bool:  # noqa: ARG002
        return _context(context).primer_dialog.is_open

    def describe(self, app_state: Any, context: Any = None) -> ValidationFailure | None:  # noqa: ARG002
        return ValidationFailure(
            reason="Click **🧬 Design Primers** in the toolbar to open the dialog."
        )


class CandidatesRanked(_ContextValidator):
    """The learner pressed Design Primers and got a ranked table back.

    Checks the Methods log as well as the table, so clicking through the tabs
    with a stale table showing cannot satisfy it.
    """

    def check(self, app_state: Any, context: Any = None) -> bool:  # noqa: ARG002
        snapshot = _context(context)
        return snapshot.primer_dialog.has_candidates and snapshot.recorded("primer_design")

    def describe(self, app_state: Any, context: Any = None) -> ValidationFailure | None:  # noqa: ARG002
        snapshot = _context(context)
        if not snapshot.primer_dialog.is_open:
            return ValidationFailure(reason="The dialog closed. Reopen **🧬 Design Primers**.")
        if not snapshot.primer_dialog.has_candidates:
            return ValidationFailure(
                reason=(
                    "No candidates yet. Press **Design Primers**. If it refuses, read the red "
                    "line under the form — an inverted or empty coordinate range is the usual "
                    "cause."
                )
            )
        return ValidationFailure(
            reason=(
                "The table has rows but no design was recorded. Press **Design Primers** again "
                "so the run reaches the Methods log."
            )
        )


class CandidateSelected(_ContextValidator):
    """A row in the candidate table is highlighted.

    Selecting is what populates the Amplification and Gel tabs, so three later
    steps depend on it.
    """

    def check(self, app_state: Any, context: Any = None) -> bool:  # noqa: ARG002
        return _context(context).primer_dialog.has_selection

    def describe(self, app_state: Any, context: Any = None) -> ValidationFailure | None:  # noqa: ARG002
        if not _context(context).primer_dialog.has_candidates:
            return ValidationFailure(reason="Rank some candidates first with **Design Primers**.")
        return ValidationFailure(
            reason=(
                "Click a **row** in the table — anywhere on it. Selecting a pair is what fills "
                "in the Amplification and Gel tabs; they stay empty until you do."
            )
        )


class ViewingDialogTab(_ContextValidator):
    """The dialog is showing one particular inner tab."""

    #: Labels as the dialog writes them, for the failure message.
    _LABELS = {"candidates": "Candidates", "amplification": "Amplification", "gel": "Gel"}

    def __init__(self, tab: str) -> None:
        self._tab = tab

    def check(self, app_state: Any, context: Any = None) -> bool:  # noqa: ARG002
        return _context(context).primer_dialog.visible_tab == self._tab

    def describe(self, app_state: Any, context: Any = None) -> ValidationFailure | None:  # noqa: ARG002
        label = self._LABELS.get(self._tab, self._tab)
        return ValidationFailure(reason=f"Open the **{label}** tab at the top of the dialog.")


class TailAdded(_ContextValidator):
    """At least one 5' tail has been entered.

    The lesson is that a tail is how a restriction site gets into the product,
    so it is satisfied by either tail — which one is the learner's choice.
    """

    def check(self, app_state: Any, context: Any = None) -> bool:  # noqa: ARG002
        dialog = _context(context).primer_dialog
        return dialog.has_forward_tail or dialog.has_reverse_tail

    def describe(self, app_state: Any, context: Any = None) -> ValidationFailure | None:  # noqa: ARG002
        return ValidationFailure(
            reason=(
                "Type a tail into **Forward 5' tail** — `GAATTC` is EcoRI. Watch the caption "
                "beside the box name the enzyme once it recognises the site."
            )
        )


class MethodRecorded(_ContextValidator):
    """A given analysis kind reached the Methods log.

    ``kind`` is one of ``citations.STEP_ORDER``. This is the strongest evidence
    a course can ask for: the log is written by the analysis layer when a real
    run completes, not by the view when it repaints.
    """

    def __init__(self, kind: str, *, action: str) -> None:
        self._kind = kind
        self._action = action

    def check(self, app_state: Any, context: Any = None) -> bool:  # noqa: ARG002
        return _context(context).recorded(self._kind)

    def describe(self, app_state: Any, context: Any = None) -> ValidationFailure | None:  # noqa: ARG002
        return ValidationFailure(reason=self._action)

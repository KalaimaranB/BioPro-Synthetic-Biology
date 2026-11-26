"""The plasmid-assembly Academy course must be runnable, not merely importable.

A course is data, so almost everything that can be wrong with one is wrong
quietly: a step pointing at a ``next_step_id`` that does not exist, a question
whose wrong answers carry no feedback, a spotlight naming a widget nobody ever
called ``setObjectName`` on. None of that raises on import, and none of it is
visible until a student is sitting in front of it.

So this module checks three things the author cannot check by reading:

1. **The graph closes.** Every id a step routes to exists, every step is
   reachable from the first, and no step is a dead end.
2. **The spotlights resolve.** Every ``objectName`` the course points at is
   actually set in ``plasmid_assembly_view.py``, against the real widget tree.
3. **The validators are honest.** Each one passes when the thing it claims to
   check is true, fails when it is not, and explains itself on failure.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from karcytics_sdk.plugin.tutorial_models import (
    QUESTION_CHECK,
    QUESTION_PREDICT,
    BaseStep,
    BranchingStep,
    QuestionStep,
    VerificationStep,
)
from PySide6.QtWidgets import QApplication, QWidget

from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.tutorials import ALL_COURSES
from karcytics_plugins.synthetic_biology.tutorials.context import (
    PrimerDialogSnapshot,
    SynBioAcademyContext,
)
from karcytics_plugins.synthetic_biology.tutorials.plasmid_assembly import (
    TARGETED_WIDGETS,
    plasmid_assembly_course,
)
from karcytics_plugins.synthetic_biology.tutorials.validators import (
    MIN_TEACHABLE_BP,
    CandidateSelected,
    CandidatesRanked,
    MethodRecorded,
    PlasmidLoaded,
    PrimerDialogOpen,
    TailAdded,
    ViewingDialogTab,
)
from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
    PlasmidAssemblyController,
)
from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
    PlasmidAssemblyView,
    PrimerDesignDialog,
)

from .sequence_fixtures import SYNTHETIC_TEMPLATE

COURSE = plasmid_assembly_course


def _ids() -> set[str]:
    return {step.id for step in COURSE.steps}


def _routes(step: BaseStep) -> list[str]:
    """Every step id this step can hand control to."""
    targets = [step.next_step_id]
    targets.extend(getattr(step, "options", {}).values())
    for attr in ("on_success_step_id", "on_fail_step_id", "resume_step_id"):
        targets.append(getattr(step, attr, None))
    return [t for t in targets if t]


# ── The course is registered and discoverable ──────────────────────────


@pytest.mark.unit
def test_the_course_is_exported_for_registration():
    assert COURSE in ALL_COURSES, "a course the panel never registers cannot be taken"


@pytest.mark.unit
def test_the_course_identifies_itself_for_the_catalogue():
    assert COURSE.id == "synbio_plasmid_assembly_v1"
    assert COURSE.title and COURSE.description
    assert COURSE.estimated_minutes > 0, "the catalogue card shows this"
    assert COURSE.badge_reward and COURSE.badge_icon


@pytest.mark.unit
def test_course_ids_are_unique_across_the_module():
    ids = [course.id for course in ALL_COURSES]
    assert len(ids) == len(set(ids))


# ── The graph closes ───────────────────────────────────────────────────


@pytest.mark.unit
def test_step_ids_are_unique():
    """`Course.get_step` returns the first match, so a duplicate silently wins."""
    ids = [step.id for step in COURSE.steps]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"duplicate step ids: {duplicates}"


@pytest.mark.unit
def test_every_route_points_at_a_real_step():
    ids = _ids()
    dangling = [
        (step.id, target)
        for step in COURSE.steps
        for target in _routes(step)
        if target not in ids and not target.startswith("__")
    ]
    assert not dangling, f"steps route to ids that do not exist: {dangling}"


@pytest.mark.unit
def test_every_step_is_reachable_from_the_first():
    by_id = {step.id: step for step in COURSE.steps}
    seen: set[str] = set()
    stack = [COURSE.steps[0].id]
    while stack:
        current = stack.pop()
        if current in seen or current not in by_id:
            continue
        seen.add(current)
        stack.extend(_routes(by_id[current]))

    orphans = sorted(_ids() - seen)
    assert not orphans, f"steps no path reaches: {orphans}"


@pytest.mark.unit
def test_no_step_is_a_dead_end():
    """A step with nowhere to go strands the learner with a dead Next button."""
    stranded = [
        step.id
        for step in COURSE.steps
        if not _routes(step) and not isinstance(step, BranchingStep)
    ]
    assert not stranded, f"steps with no route out: {stranded}"


@pytest.mark.unit
def test_the_course_ends_on_a_completion_branch():
    final = COURSE.steps[-1]
    assert isinstance(final, BranchingStep)
    assert "__complete__" in final.options.values(), "without this the badge is never awarded"


# ── The spotlights resolve ─────────────────────────────────────────────


@pytest.mark.unit
def test_the_course_actually_spotlights_something():
    assert len(TARGETED_WIDGETS) > 10, "a course that highlights nothing is a slideshow"


@pytest.fixture(scope="module")
def live_object_names(request) -> frozenset[str]:
    """Every `objectName` the real widget tree carries, view and dialog both.

    Built from live widgets rather than grepped out of the source: the two tail
    boxes are produced by one helper that takes the name as an argument, so no
    literal `setObjectName("primer_fwd_tail_edit")` appears anywhere, and a
    source scan declared it missing while the running app had it. What matters
    is whether `findChildren(QWidget, name)` — which is exactly how
    `AcademyStepDriver` resolves a target — can see it.
    """
    QApplication.instance() or QApplication([])
    names: set[str] = set()
    widgets = [
        PlasmidAssemblyView(SynBioState(), PlasmidAssemblyController(SynBioState())),
        PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(SynBioState())),
    ]
    request.addfinalizer(lambda: [w.deleteLater() for w in widgets])
    for root in widgets:
        if root.objectName():
            names.add(root.objectName())
        names.update(w.objectName() for w in root.findChildren(QWidget) if w.objectName())
    return frozenset(names)


@pytest.mark.unit
@pytest.mark.parametrize("name", TARGETED_WIDGETS)
def test_every_spotlight_target_exists_in_the_widget_tree(name, live_object_names):
    """The driver resolves a target by `objectName`; an unset name finds nothing.

    This is the test that makes the course real. Without it a step can name a
    widget that was renamed or never named at all, and the only symptom is a
    lesson that dims the screen and points at nothing.
    """
    assert name in live_object_names, (
        f"the course spotlights {name!r} but no widget in the plasmid view or primer "
        "dialog carries that objectName, so the step would highlight nothing"
    )


@pytest.mark.unit
def test_targets_are_derived_from_the_steps_not_duplicated():
    """A hand-kept list drifts; this one must stay a projection of the steps."""
    used = {name for step in COURSE.steps for name in (step.target_widget_names or [])}
    assert set(TARGETED_WIDGETS) == used


# ── Questions can be answered, and teach when answered wrongly ─────────


@pytest.mark.unit
def test_the_course_asks_questions():
    questions = [s for s in COURSE.steps if isinstance(s, QuestionStep)]
    assert len(questions) >= 4, "the Academy's whole advantage over a slideshow is that it asks"


@pytest.mark.unit
def test_every_wrong_answer_explains_itself():
    """`QuestionStep.__post_init__` enforces this; losing it would be silent.

    A wrong choice with empty feedback teaches nothing — the learner is told
    "no" and left to guess, which is worse than not asking.
    """
    for step in COURSE.steps:
        if not isinstance(step, QuestionStep) or step.kind != QUESTION_CHECK:
            continue
        for choice in step.choices:
            if not choice.correct:
                assert choice.feedback.strip(), f"{step.id}: {choice.text!r} has no feedback"


@pytest.mark.unit
def test_check_questions_explain_the_answer():
    for step in COURSE.steps:
        if isinstance(step, QuestionStep) and step.kind == QUESTION_CHECK:
            assert step.explanation.strip(), f"{step.id} has no explanation"


@pytest.mark.unit
def test_every_prediction_is_revealed_later():
    """A `predict` question is pointless unless something recalls the answer.

    The engine substitutes `{answer:<question_id>}` into a later step's text;
    a prediction nothing recalls is a click with no payoff.
    """
    predictions = {
        step.question_id
        for step in COURSE.steps
        if isinstance(step, QuestionStep) and step.kind == QUESTION_PREDICT
    }
    assert predictions, "no predict-then-observe step in a course about predictions"

    revealed = {
        qid for qid in predictions for step in COURSE.steps if f"{{answer:{qid}}}" in step.text
    }
    assert predictions == revealed, f"predictions never shown back: {predictions - revealed}"


# ── Verification steps are answerable ──────────────────────────────────


@pytest.mark.unit
def test_every_verification_step_has_a_validator():
    naked = [s.id for s in COURSE.steps if isinstance(s, VerificationStep) and s.validator is None]
    assert not naked, f"verification steps that check nothing: {naked}"


@pytest.mark.unit
def test_blocking_steps_let_the_learner_act():
    """A step that waits on a click must not also swallow the click."""
    for step in COURSE.steps:
        if isinstance(step, VerificationStep) and step.hide_next_button:
            assert step.allow_interaction, (
                f"{step.id} hides Next and blocks interaction, so it cannot be satisfied"
            )


@pytest.mark.unit
def test_dialog_steps_can_recover_if_it_closes():
    """Closing the dialog mid-course must not leave an unsatisfiable step.

    `resume_step_id` points a paused course back at the step that reopens the
    dialog, which is the only way back for a step that needs it open.
    """
    reopen = next(s for s in COURSE.steps if s.id == "open_dialog")
    assert reopen.target_widget_names == ["btn_design_primers"]
    assert any(getattr(s, "resume_step_id", None) == "open_dialog" for s in COURSE.steps), (
        "no step knows how to get the dialog back"
    )


# ── The validators ─────────────────────────────────────────────────────


class _FakeState:
    def __init__(self, plasmid=None):
        self._plasmid = plasmid

    def get_active_plasmid(self):
        return self._plasmid


class _FakePlasmid:
    def __init__(self, length, name="pTest"):
        self.sequence = "A" * length
        self.name = name


@pytest.mark.unit
def test_plasmid_loaded_accepts_a_teachable_sequence():
    assert PlasmidLoaded().validate(_FakeState(_FakePlasmid(MIN_TEACHABLE_BP)))


@pytest.mark.unit
def test_plasmid_loaded_rejects_nothing_loaded():
    validator, state = PlasmidLoaded(), _FakeState(None)

    assert not validator.validate(state)
    failure = validator.describe_failure(state)
    assert failure is not None and "Paste Sequence" in failure.reason


@pytest.mark.unit
def test_plasmid_loaded_says_how_short_a_short_sequence_is():
    """The two failures need different advice, so they must not share a message."""
    validator, state = PlasmidLoaded(), _FakeState(_FakePlasmid(40, name="pTiny"))

    assert not validator.validate(state)
    failure = validator.describe_failure(state)
    assert failure is not None
    assert "40 bp" in failure.reason and "pTiny" in failure.reason


@pytest.mark.unit
def test_a_validator_survives_a_state_that_is_not_one():
    """The driver polls on a timer; raising here would drop the overlay."""
    assert PlasmidLoaded().validate(object()) is False


@pytest.mark.unit
def test_context_validators_fail_closed_without_a_context():
    """No snapshot must mean "not yet", never a pass or an exception."""
    for validator in (
        PrimerDialogOpen(),
        CandidatesRanked(),
        CandidateSelected(),
        TailAdded(),
        ViewingDialogTab("gel"),
        MethodRecorded("gel_migration", action="run it"),
    ):
        assert validator.check(None, None) is False
        assert validator.check(None, "not a context") is False


@pytest.mark.unit
def test_primer_dialog_open_reads_the_snapshot():
    closed = SynBioAcademyContext()
    opened = SynBioAcademyContext(primer_dialog=PrimerDialogSnapshot(is_open=True))

    assert not PrimerDialogOpen().check(None, closed)
    assert PrimerDialogOpen().check(None, opened)


@pytest.mark.unit
def test_candidates_ranked_needs_the_methods_log_too():
    """A stale table must not satisfy it; only a recorded run counts."""
    validator = CandidatesRanked()
    table_only = SynBioAcademyContext(
        primer_dialog=PrimerDialogSnapshot(is_open=True, candidate_count=5)
    )
    recorded = SynBioAcademyContext(
        primer_dialog=PrimerDialogSnapshot(is_open=True, candidate_count=5),
        method_kinds=("primer_design",),
    )

    assert not validator.check(None, table_only)
    assert validator.check(None, recorded)

    failure = validator.describe(None, table_only)
    assert failure is not None and "Methods log" in failure.reason


@pytest.mark.unit
def test_candidates_ranked_distinguishes_a_closed_dialog_from_an_empty_table():
    validator = CandidatesRanked()

    closed = validator.describe(None, SynBioAcademyContext())
    empty = validator.describe(
        None, SynBioAcademyContext(primer_dialog=PrimerDialogSnapshot(is_open=True))
    )

    assert closed is not None and "Reopen" in closed.reason
    assert empty is not None and "No candidates yet" in empty.reason
    assert closed.reason != empty.reason, "two different mistakes need two messages"


@pytest.mark.unit
def test_candidate_selected_requires_a_row():
    validator = CandidateSelected()
    ranked = PrimerDialogSnapshot(is_open=True, candidate_count=3)

    assert not validator.check(None, SynBioAcademyContext(primer_dialog=ranked))
    chosen = PrimerDialogSnapshot(is_open=True, candidate_count=3, selected_index=0)
    assert validator.check(None, SynBioAcademyContext(primer_dialog=chosen))


@pytest.mark.unit
def test_candidate_selected_accepts_row_zero():
    """`selected_index=0` is a real selection; a truthiness check would miss it."""
    chosen = PrimerDialogSnapshot(is_open=True, candidate_count=3, selected_index=0)
    assert PrimerDialogSnapshot(selected_index=0).has_selection
    assert CandidateSelected().check(None, SynBioAcademyContext(primer_dialog=chosen))


@pytest.mark.unit
@pytest.mark.parametrize("tab", ["candidates", "amplification", "gel"])
def test_viewing_dialog_tab_matches_only_its_own_tab(tab):
    validator = ViewingDialogTab(tab)
    for candidate in ("candidates", "amplification", "gel"):
        context = SynBioAcademyContext(
            primer_dialog=PrimerDialogSnapshot(is_open=True, visible_tab=candidate)
        )
        assert validator.check(None, context) is (candidate == tab)


@pytest.mark.unit
def test_tail_added_accepts_either_tail():
    validator = TailAdded()
    for snapshot in (
        PrimerDialogSnapshot(has_forward_tail=True),
        PrimerDialogSnapshot(has_reverse_tail=True),
    ):
        assert validator.check(None, SynBioAcademyContext(primer_dialog=snapshot))
    assert not validator.check(None, SynBioAcademyContext())


@pytest.mark.unit
def test_method_recorded_checks_the_named_kind():
    validator = MethodRecorded("gel_migration", action="Open the Gel tab and run it.")

    assert not validator.check(None, SynBioAcademyContext(method_kinds=("primer_design",)))
    assert validator.check(None, SynBioAcademyContext(method_kinds=("gel_migration",)))

    failure = validator.describe(None, SynBioAcademyContext())
    assert failure is not None and failure.reason == "Open the Gel tab and run it."


# ── The context snapshot ───────────────────────────────────────────────


@pytest.mark.unit
def test_the_context_knows_which_tab_is_the_plasmid_tab():
    """The course must never hardcode the tab index."""
    context = SynBioAcademyContext(active_tab_index=SynBioAcademyContext.PLASMID_TAB)
    assert context.on_plasmid_tab
    assert not SynBioAcademyContext(active_tab_index=0).on_plasmid_tab


@pytest.mark.unit
def test_an_empty_context_claims_nothing():
    context = SynBioAcademyContext()

    assert not context.has_plasmid
    assert not context.primer_dialog.is_open
    assert not context.primer_dialog.has_candidates
    assert not context.primer_dialog.has_selection
    assert not context.recorded("primer_design")


@pytest.mark.unit
def test_the_context_is_frozen():
    """A validator must not be able to edit the workspace it is inspecting."""
    context = SynBioAcademyContext()
    with pytest.raises(FrozenInstanceError):
        context.plasmid_length_bp = 500  # type: ignore[misc]


# ── Scope ──────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_the_course_never_teaches_orthogonality_checking():
    """It is advertised in the manifest and has no implementation.

    An Academy course validates what the learner did, so a lesson on a missing
    feature would hang rather than merely mislead. If orthogonality is ever
    built, this test is the reminder that a course may then mention it.
    """
    prose = " ".join(step.text for step in COURSE.steps).lower()
    assert "orthogonal" not in prose

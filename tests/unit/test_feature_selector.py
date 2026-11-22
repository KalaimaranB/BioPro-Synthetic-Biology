"""The primer dialog's feature selector must offer the construct's features.

Audit finding H-3. ``_annotated_features`` read ``state.active_vector``, an
attribute ``SynBioState`` has never had — it exposes the construct as
``plasmid``. Every call returned an empty list, so the "Amplify:" combo held
exactly one option for a vector with ten annotated features and feature-based
primer design was dead for the whole life of the control.

The defect was a wrong key. What made it survive was
``getattr(..., "active_vector", None)``: a defensive default turns a wrong key
into an empty result that looks deliberate. These tests pin both halves — the
selector populates, and a future rename fails loudly rather than quietly
yielding nothing.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis.models.domain import (
    GeneticFeature,
    PlasmidVector,
)
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
    PlasmidAssemblyController,
)
from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
    PrimerDesignDialog,
)

#: A vector annotated the way a real expression construct is.
FEATURES = [
    ("gfp_reporter", "cds", 350, 1100),
    ("kanR", "cds", 1250, 2060),
    ("J23119", "promoter", 2100, 2160),
    ("B0034", "rbs", 2160, 2175),
    ("lacZ_alpha", "cds", 2200, 3400),
    ("ori", "rep_origin", 3500, 4100),
    ("B0015", "terminator", 4200, 4260),
]


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _vector(features=FEATURES):
    return PlasmidVector(
        id="pKARC",
        name="pKARC-TEST",
        sequence="ACGT" * 1311,
        is_circular=True,
        features=[
            GeneticFeature(id=str(i), name=n, feature_type=t, start=a, end=b)
            for i, (n, t, a, b) in enumerate(features)
        ],
    )


def _dialog(destroy_after, vector=None):
    state = SynBioState()
    if vector is not None:
        state.set_active_plasmid(vector)
    sequence = vector.sequence if vector is not None else "ACGT" * 60
    return destroy_after(PrimerDesignDialog(sequence, PlasmidAssemblyController(state)))


# ── The selector populates ─────────────────────────────────────────────


@pytest.mark.unit
def test_the_selector_offers_every_named_feature(app, destroy_after):
    dialog = _dialog(destroy_after, _vector())

    offered = dialog._annotated_features()

    assert len(offered) == len(FEATURES), (
        "every annotated feature must be offered as an amplification target; "
        "this returned an empty list for the whole life of the control"
    )
    assert ("gfp_reporter", 350, 1100) in offered


@pytest.mark.unit
def test_the_combo_carries_the_features_beside_the_whole_sequence(app, destroy_after):
    dialog = _dialog(destroy_after, _vector())

    # One entry for the whole target, then one per feature.
    assert dialog.feature_combo.count() == len(FEATURES) + 1
    assert dialog.feature_combo.itemText(0) == "Whole target sequence"
    assert dialog.feature_combo.itemData(0) is None

    labels = [dialog.feature_combo.itemText(i) for i in range(1, dialog.feature_combo.count())]
    assert "gfp_reporter (350-1100)" in labels


@pytest.mark.unit
def test_selecting_a_feature_narrows_the_region(app, destroy_after):
    """The payoff: the span must follow the selection, not stay at the whole template."""
    dialog = _dialog(destroy_after, _vector())
    index = next(
        i
        for i in range(dialog.feature_combo.count())
        if dialog.feature_combo.itemData(i) == (350, 1100)
    )

    dialog.feature_combo.setCurrentIndex(index)

    assert dialog.feature_combo.currentData() == (350, 1100)
    assert dialog._region() == (350, 1100)


@pytest.mark.unit
def test_a_feature_without_a_name_is_not_offered(app, destroy_after):
    """An unnamed feature cannot be labelled in a combo, so it is skipped."""
    dialog = _dialog(destroy_after, _vector([("", "misc_feature", 10, 20)] + FEATURES))

    assert len(dialog._annotated_features()) == len(FEATURES)


@pytest.mark.unit
def test_no_construct_loaded_is_an_empty_list_not_an_error(app, destroy_after):
    """The one legitimate empty case: nothing has been assembled or imported."""
    dialog = _dialog(destroy_after, vector=None)

    assert dialog._annotated_features() == []
    assert dialog.feature_combo.count() == 1


# ── A rename must fail loudly ──────────────────────────────────────────


@pytest.mark.unit
def test_the_state_attribute_the_selector_depends_on_exists():
    """Names the coupling, so a rename of SynBioState.plasmid fails here.

    H-3 was invisible because nothing asserted the key. This is the assertion
    that was missing.
    """
    state = SynBioState()

    assert hasattr(state, "plasmid"), (
        "the feature selector reads state.plasmid; renaming it breaks the "
        "Amplify selector and must break this test first"
    )
    assert not hasattr(state, "active_vector"), (
        "active_vector is the key that never existed — if it is ever added, "
        "resolve which one the selector should read rather than having both"
    )


@pytest.mark.unit
def test_a_missing_state_attribute_raises_rather_than_yielding_nothing(app, destroy_after):
    """The defensive default is gone: a wrong key must not look like 'no features'."""
    dialog = _dialog(destroy_after, _vector())

    class StateWithoutPlasmid:
        pass

    dialog.controller.state = StateWithoutPlasmid()  # type: ignore[assignment]

    with pytest.raises(AttributeError):
        dialog._annotated_features()


@pytest.mark.unit
def test_the_selector_does_not_use_a_defensive_default_for_the_state_key():
    """A getattr default here is what hid the defect; it must not come back."""
    import ast
    import inspect

    # The docstring names active_vector on purpose, to record why this exists.
    # Only the executable body may not mention it.
    tree = ast.parse(inspect.getsource(PrimerDesignDialog._annotated_features).strip())
    func = tree.body[0]
    body = func.body[1:] if ast.get_docstring(func) else func.body  # type: ignore[arg-type]
    code = "\n".join(ast.unparse(stmt) for stmt in body)

    assert "active_vector" not in code, "the key that never existed is back in the code"
    assert "getattr" not in code, (
        "reading state through getattr-with-default turns a wrong key into an "
        "empty result that looks deliberate — which is how H-3 survived"
    )
    assert "state.plasmid" in code

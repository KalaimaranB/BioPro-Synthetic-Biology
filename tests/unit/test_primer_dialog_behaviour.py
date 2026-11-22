"""Dialog behaviour: stale results, worker lifecycle, and refusals on screen."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
    PlasmidAssemblyController,
)
from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
    PrimerDesignDialog,
)

from .sequence_fixtures import ECORI_TAIL, HINDIII_TAIL, SYNTHETIC_ORF, SYNTHETIC_TEMPLATE


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _dialog(destroy_after, sequence=SYNTHETIC_TEMPLATE):
    return destroy_after(PrimerDesignDialog(sequence, PlasmidAssemblyController(SynBioState())))


# ── Validation reaches the screen ──────────────────────────────────────


@pytest.mark.unit
def test_an_inverted_range_is_refused_on_screen_not_silently_widened(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog.start_spin.setValue(100)
    dialog.end_spin.setValue(40)

    dialog._on_design_clicked()

    assert dialog.candidate_table.rowCount() == 0
    assert "after end" in dialog.input_problem.text()


@pytest.mark.unit
def test_an_empty_range_is_refused_on_screen(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog.start_spin.setValue(50)
    dialog.end_spin.setValue(50)

    dialog._on_design_clicked()

    assert "empty" in dialog.input_problem.text().lower()


@pytest.mark.unit
def test_an_ambiguous_template_is_refused_with_the_engines_wording(app, destroy_after):
    dialog = _dialog(destroy_after, "ATGACGTACGTNNNNNACGTACGTACGTACGTACGTACGTACG")

    dialog._on_design_clicked()

    assert "ambiguity code" in dialog.input_problem.text()
    assert dialog.candidate_table.rowCount() == 0


# ── Stale results ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_changing_a_tail_clears_candidates_computed_against_the_old_one(app, destroy_after):
    """Designing with GAATTC then typing AAGCTT left the old primers up."""
    dialog = _dialog(destroy_after)
    dialog.fwd_overhang_edit.setText(ECORI_TAIL)
    dialog._on_design_clicked()
    assert dialog.candidate_table.rowCount() > 0
    assert dialog.candidate_table.item(0, 2).text().startswith(ECORI_TAIL)

    dialog.fwd_overhang_edit.setText(HINDIII_TAIL)

    assert dialog.candidate_table.rowCount() == 0, "stale candidates still shown"
    assert "Press Design Primers" in dialog.status.text()


@pytest.mark.unit
def test_invalidating_also_clears_the_dependent_views(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog.fwd_overhang_edit.setText(ECORI_TAIL)
    dialog._on_design_clicked()
    dialog.candidate_table.selectRow(0)

    dialog.fwd_overhang_edit.setText(HINDIII_TAIL)

    assert dialog.rubric_panel.table.rowCount() == 0
    assert not dialog.amplification_hint.isHidden()


# ── Worker lifecycle ───────────────────────────────────────────────────


@pytest.mark.unit
def test_tail_typing_is_debounced(app, destroy_after):
    """Typing six characters must not resolve the tail six times."""
    dialog = _dialog(destroy_after)
    for ch in ECORI_TAIL:
        dialog.fwd_overhang_edit.setText(dialog.fwd_overhang_edit.text() + ch)

    assert dialog._tail_debounce.isActive(), "keystrokes should be coalesced"


@pytest.mark.unit
def test_a_superseded_design_result_is_discarded(app, destroy_after):
    """A slow earlier run must not overwrite a newer one."""
    dialog = _dialog(destroy_after)
    dialog._on_design_clicked()
    dialog._on_design_clicked()
    fresh = list(dialog._candidates)
    assert fresh

    stale_request = dialog._design_request - 1
    assert stale_request >= 1
    dialog._on_candidates([{"bogus": True}], stale_request)

    assert dialog._candidates == fresh, "a stale result overwrote the current one"


@pytest.mark.unit
def test_a_superseded_amplification_result_is_discarded(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog._on_design_clicked()
    dialog.candidate_table.selectRow(0)
    dialog.candidate_table.selectRow(1)
    heading = dialog.amplification_track.heading.text()

    stale = dialog._amp_request - 1
    assert stale >= 1
    dialog._on_amplification({"result": None, "template_bp": 0}, stale)

    assert dialog.amplification_track.heading.text() == heading


@pytest.mark.unit
def test_cancel_abandons_the_run_and_restores_the_button(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog._set_running(True)
    assert not dialog.btn_cancel.isHidden()
    assert not dialog.btn_design.isEnabled()

    dialog._on_cancel()

    assert dialog.btn_design.isEnabled()
    assert dialog.btn_design.text() == "Design Primers"
    assert dialog.status.text() == "Cancelled."


# ── Small UX ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_whole_target_sequence_resets_the_coordinates(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog.start_spin.setValue(100)
    dialog.end_spin.setValue(200)

    dialog.feature_combo.setCurrentIndex(0)
    dialog._on_region_changed()

    assert dialog._region() == (0, len(SYNTHETIC_TEMPLATE))


@pytest.mark.unit
def test_the_amplification_and_gel_tabs_say_what_they_are_waiting_for(app, destroy_after):
    dialog = _dialog(destroy_after)
    for hint in (dialog.amplification_hint, dialog.gel_hint):
        assert "select a candidate" in hint.text().lower()


@pytest.mark.unit
def test_the_hints_disappear_once_a_candidate_is_shown(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog._on_design_clicked()
    dialog.candidate_table.selectRow(0)

    assert dialog.amplification_hint.isHidden()
    assert dialog.gel_hint.isHidden()


@pytest.mark.unit
def test_a_transformed_sequence_reports_the_transformation(app, destroy_after):
    """RNA is converted, and the student is told."""
    rna = "AUG" + SYNTHETIC_ORF[3:].replace("T", "U")
    dialog = _dialog(destroy_after, rna)

    dialog._on_design_clicked()

    assert "RNA to DNA" in dialog.input_note.text()
    assert dialog.candidate_table.rowCount() > 0

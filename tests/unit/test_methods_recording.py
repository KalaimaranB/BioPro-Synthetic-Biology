"""A completed primer run must appear in Methods & References.

This is the test whose absence let the whole citation chain die unnoticed.
``primer_screen_step``, ``amplification_step``, ``digest_step`` and
``gel_step`` all existed, were unit-tested, were registered in ``STEP_ORDER``
— and had zero callers. A student could run the entire workflow and the
Methods dialog would show nothing about any of it, so every Crossref-verified
citation behind the numbers was invisible in the exported write-up.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis import citations
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
    PlasmidAssemblyController,
)
from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
    PrimerDesignDialog,
)
from karcytics_plugins.synthetic_biology.ui.workers import AmplificationWorker

from .sequence_fixtures import (
    ECORI_TAIL,
    HINDIII_TAIL,
    SYNTHETIC_ORF,
    SYNTHETIC_TEMPLATE,
    primers_for,
)

FWD, REV = primers_for(SYNTHETIC_ORF)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _run_full_workflow(dialog):
    """Design, select the top candidate, and let amplification complete."""
    dialog.fwd_overhang_edit.setText(ECORI_TAIL)
    dialog.rev_overhang_edit.setText(HINDIII_TAIL)
    dialog._on_design_clicked()
    assert dialog.candidate_table.rowCount() > 0, "no candidates to select"
    dialog.candidate_table.selectRow(0)


@pytest.mark.unit
def test_a_full_run_records_all_four_method_steps(app, destroy_after):
    """Design -> screen -> amplify -> digest -> gel, all written up."""
    state = SynBioState()
    controller = PlasmidAssemblyController(state)
    dialog = destroy_after(PrimerDesignDialog(SYNTHETIC_TEMPLATE, controller))

    _run_full_workflow(dialog)

    kinds = {entry["kind"] for entry in state.data.methods_log}
    for required in ("primer_design", "primer_screen", "amplification"):
        assert required in kinds, f"{required} missing from the methods log: {sorted(kinds)}"


@pytest.mark.unit
def test_the_digest_and_gel_steps_are_recorded_when_tails_name_an_enzyme(app, destroy_after):
    state = SynBioState()
    dialog = destroy_after(PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(state)))

    _run_full_workflow(dialog)

    kinds = {entry["kind"] for entry in state.data.methods_log}
    assert "restriction_digest" in kinds
    assert "gel_migration" in kinds


@pytest.mark.unit
def test_the_recorded_run_produces_a_methods_paragraph_with_references(app, destroy_after):
    """What the student actually submits."""
    state = SynBioState()
    dialog = destroy_after(PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(state)))
    _run_full_workflow(dialog)

    text = citations.methods_text(state.data.methods_log)

    assert "polymerase chain reaction" in text
    assert "REBASE" in text
    assert "References" in text
    for author in ("Saiki", "Newton", "Roberts", "Southern"):
        assert author in text, f"{author} missing from the write-up"


@pytest.mark.unit
def test_the_recorded_run_produces_bibtex(app, destroy_after):
    state = SynBioState()
    dialog = destroy_after(PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(state)))
    _run_full_workflow(dialog)

    bib = citations.bibtex(state.data.methods_log)
    for key in ("saiki1988", "newton1989", "roberts2022", "southern1979"):
        assert f"{{{key}," in bib


@pytest.mark.unit
def test_the_honesty_clauses_survive_into_the_submitted_paragraph(app, destroy_after):
    """A convention must still read as a convention in the exported text."""
    state = SynBioState()
    dialog = destroy_after(PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(state)))
    _run_full_workflow(dialog)

    text = citations.methods_text(state.data.methods_log)
    assert "convention" in text
    assert "does not account for" in text


# ── The controller's recorders, without a view ─────────────────────────


@pytest.mark.unit
def test_the_controller_records_amplification_digest_and_gel(app):
    state = SynBioState()
    controller = PlasmidAssemblyController(state)

    worker = AmplificationWorker(
        template=SYNTHETIC_TEMPLATE,
        forward_primer=ECORI_TAIL + FWD,
        reverse_primer=HINDIII_TAIL + REV,
        forward_tail=ECORI_TAIL,
        reverse_tail=HINDIII_TAIL,
        enzymes=("EcoRI", "HindIII"),
    )
    received: list = []
    worker.amplification_ready.connect(received.append)
    worker._execute()
    payload = received[0]

    controller.record_amplification(payload["result"])
    controller.record_digest(payload["digest"])
    controller.record_gel(payload["gel"])

    kinds = [entry["kind"] for entry in state.data.methods_log]
    assert kinds == ["amplification", "restriction_digest", "gel_migration"]


@pytest.mark.unit
def test_re_running_replaces_rather_than_appends(app):
    """Methods describes the results on screen, not every run along the way."""
    state = SynBioState()
    controller = PlasmidAssemblyController(state)
    worker = AmplificationWorker(
        template=SYNTHETIC_TEMPLATE, forward_primer=FWD, reverse_primer=REV
    )
    received: list = []
    worker.amplification_ready.connect(received.append)
    worker._execute()

    controller.record_amplification(received[0]["result"])
    controller.record_amplification(received[0]["result"])

    kinds = [e["kind"] for e in state.data.methods_log]
    assert kinds.count("amplification") == 1


@pytest.mark.unit
def test_the_old_dead_primer_path_is_gone():
    """One recording path, not two — the orphan used to be the only recorder."""
    for removed in ("handle_primer_design", "handle_primer_design_request", "primers_ready"):
        assert not hasattr(PlasmidAssemblyController, removed), f"{removed} still present"

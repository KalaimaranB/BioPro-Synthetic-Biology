"""The export is the graded deliverable, so its contents are a contract."""

from __future__ import annotations

import csv
import io

import pytest
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis import citations
from karcytics_plugins.synthetic_biology.analysis.assembly import primer_export
from karcytics_plugins.synthetic_biology.analysis.assembly.vector_builder import (
    VectorAssemblyEngine as V,
)
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


@pytest.fixture
def candidate():
    return V.generate_primer_candidates(
        SYNTHETIC_ORF, fwd_overhang=ECORI_TAIL, rev_overhang=HINDIII_TAIL, limit=1
    )[0]


# ── Required contents ──────────────────────────────────────────────────


@pytest.mark.unit
def test_the_full_oligo_and_the_annealing_region_are_separate_columns(candidate):
    """Conflating them is the defect this whole workflow started with."""
    rows = primer_export.primer_rows(candidate)
    forward = rows[0]

    assert forward["full_oligo"].startswith(ECORI_TAIL)
    assert forward["tail"] == ECORI_TAIL
    assert not forward["annealing_region"].startswith(ECORI_TAIL)
    assert forward["full_oligo"] == forward["tail"] + forward["annealing_region"]
    assert forward["full_length_nt"] == forward["annealing_length_nt"] + len(ECORI_TAIL)


@pytest.mark.unit
def test_tm_and_gc_describe_the_annealing_region(candidate):
    rows = primer_export.primer_rows(candidate)
    forward = rows[0]
    assert forward["annealing_tm_c"] == pytest.approx(round(candidate["forward"].calculated_tm, 2))
    assert forward["annealing_gc_percent"] == pytest.approx(
        round(candidate["forward"].gc_content, 1)
    )


@pytest.mark.unit
def test_every_required_field_is_present(candidate):
    row = primer_export.primer_rows(candidate)[0]
    for field in (
        "full_oligo",
        "annealing_region",
        "annealing_tm_c",
        "annealing_gc_percent",
        "annealing_length_nt",
        "three_prime_clamp",
        "product_bp",
        "verdict",
    ):
        assert field in row and row[field] != "", field


@pytest.mark.unit
def test_the_three_prime_clamp_status_is_reported(candidate):
    status = primer_export.primer_rows(candidate)[0]["three_prime_clamp"]
    assert "G/C" in status
    assert any(word in status for word in ("pass", "fail", "not run"))


@pytest.mark.unit
def test_every_rubric_check_is_exported_with_its_threshold(candidate):
    rows = primer_export.check_rows(candidate)
    assert len(rows) == len(candidate["checks"])
    for row in rows:
        assert row["check"]
        assert row["result"] in ("pass", "fail", "not run")
        assert "basis" in row


@pytest.mark.unit
def test_a_failing_check_carries_its_remediation_into_the_export():
    """A marker should see what the student was told to do about it."""
    at_rich = V.generate_primer_candidates(SYNTHETIC_ORF, limit=1, require_full_target=True)[0]
    failing = [r for r in primer_export.check_rows(at_rich) if r["result"] == "fail"]
    assert failing
    assert all(r["what_to_do"] for r in failing)


# ── Formats ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_csv_contains_primers_checks_and_methods(candidate):
    text = primer_export.to_csv(
        candidate,
        methods="Methods paragraph.\n\nReferences\n1. Someone (1999).",
        rubric_name="BIOL341",
    )
    assert "PRIMERS" in text
    assert "RUBRIC CHECKS" in text
    assert "METHODS" in text
    assert "BIOL341" in text
    rows = list(csv.reader(io.StringIO(text)))
    assert any(r and r[0] == "name" for r in rows), "header row missing"


@pytest.mark.unit
def test_csv_is_parseable(candidate):
    rows = list(csv.reader(io.StringIO(primer_export.to_csv(candidate))))
    assert len(rows) > 4


@pytest.mark.unit
def test_fasta_defaults_to_the_full_oligo_and_says_so(candidate):
    text = primer_export.to_fasta(candidate)
    assert text.startswith(">")
    assert "full oligo, tail included" in text
    assert ECORI_TAIL in text


@pytest.mark.unit
def test_fasta_can_emit_the_annealing_region_and_labels_it(candidate):
    text = primer_export.to_fasta(candidate, annealing_only=True)
    assert "annealing region only" in text
    body = [line for line in text.splitlines() if not line.startswith(">")]
    assert all(not line.startswith(ECORI_TAIL) for line in body)


@pytest.mark.unit
def test_clipboard_text_names_the_tail_and_the_annealing_region(candidate):
    text = primer_export.clipboard_text(candidate["forward"])
    assert candidate["forward"].sequence in text
    assert "tail" in text and "Tm" in text and "GC" in text


# ── Wired to the dialog ────────────────────────────────────────────────


@pytest.mark.unit
def test_export_is_disabled_until_a_candidate_is_selected(app, destroy_after):
    dialog = destroy_after(
        PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(SynBioState()))
    )
    assert not dialog.btn_export.isEnabled()
    dialog._on_design_clicked()
    dialog.candidate_table.selectRow(0)
    assert dialog.btn_export.isEnabled()


@pytest.mark.unit
def test_exported_csv_from_a_real_run_carries_the_methods_paragraph(app, destroy_after, tmp_path):
    state = SynBioState()
    dialog = destroy_after(PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(state)))
    dialog.fwd_overhang_edit.setText(ECORI_TAIL)
    dialog._on_design_clicked()
    dialog.candidate_table.selectRow(0)

    text = primer_export.to_csv(
        dialog._selected_candidate(),
        methods=citations.methods_text(state.data.methods_log),
    )
    assert "References" in text
    assert "polymerase chain reaction" in text


# ── Surfaced engine capabilities ───────────────────────────────────────


@pytest.mark.unit
def test_all_four_ladders_are_offered(app, destroy_after):
    from karcytics_plugins.synthetic_biology.analysis.assembly import gel as gel_engine

    dialog = destroy_after(
        PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(SynBioState()))
    )
    assert dialog.ladder_combo.count() == len(gel_engine.LADDERS)


@pytest.mark.unit
def test_agarose_percentage_changes_the_resolving_window(app, destroy_after):
    from karcytics_plugins.synthetic_biology.analysis.assembly import gel as gel_engine

    assert gel_engine.window_for_agarose("2.0%") != gel_engine.window_for_agarose("0.7%")
    dialog = destroy_after(
        PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(SynBioState()))
    )
    assert dialog.agarose_combo.count() == len(gel_engine.AGAROSE_WINDOWS)


@pytest.mark.unit
def test_the_agarose_window_is_labelled_a_convention():
    from karcytics_plugins.synthetic_biology.analysis.assembly import gel as gel_engine

    kind, explanation = gel_engine.THRESHOLD_PROVENANCE["resolving_window"]
    assert kind == "convention"
    assert "rather than as a measured result" in explanation


@pytest.mark.unit
def test_clicking_a_band_identifies_it(app, destroy_after):
    from karcytics_plugins.synthetic_biology.analysis.assembly import gel as gel_engine
    from karcytics_plugins.synthetic_biology.ui.widgets.gel_view import GelView

    view = destroy_after(GelView())
    built = gel_engine.build_gel([gel_engine.product_lane(900)])
    view.show_gel(built)

    lane = built.lanes[-1]
    view._on_band_clicked(lane, lane.bands[0])

    assert "900 bp" in view.selection_note.text()
    assert lane.name in view.selection_note.text()


@pytest.mark.unit
def test_clicking_a_clamped_band_warns_it_is_not_a_measurement(app, destroy_after):
    from karcytics_plugins.synthetic_biology.analysis.assembly import gel as gel_engine
    from karcytics_plugins.synthetic_biology.ui.widgets.gel_view import GelView

    view = destroy_after(GelView())
    built = gel_engine.build_gel([gel_engine.product_lane(50_000)], ladder=None)
    lane = built.lanes[0]
    view.show_gel(built)
    view._on_band_clicked(lane, lane.bands[0])

    assert "this gel cannot place it" in view.selection_note.text()

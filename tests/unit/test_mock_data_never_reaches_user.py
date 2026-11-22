"""No view may present a payload as a result when its own flags deny it.

Audit findings C-3 and C-4 were the same defect twice. In both the analysis
layer was honest and the view discarded the honesty at the layer boundary:

* the NGS service returned three fabricated variant calls for any file, set
  ``is_mock=True`` and a MOCK DEMO DATA status, and ``_on_ngs_aligned``
  tabulated them as findings from the user's own run;
* the optimiser fitted targets it had derived from the circuit's own output
  and reported "Hill parameters optimized against empirical dataset", never
  having looked at ``FCSEventData.is_valid``.

The first test below is the one whose absence allowed both. It does not know
about NGS or optimisation: it walks the handlers that receive a payload and
asserts each consults :func:`assess` before rendering. A new panel that
forgets fails it.

The rest are per-site, driven headlessly through the real widgets so that what
is asserted is what a user would see.
"""

from __future__ import annotations

import inspect

import pytest
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis.empirical.fcs_ingestion import (
    FCSDataIngestionService,
    FCSEventData,
)
from karcytics_plugins.synthetic_biology.analysis.empirical.ml_optimizer import (
    DEMO_TARGET_SEED,
    CircuitMLOptimizationEngine,
)
from karcytics_plugins.synthetic_biology.analysis.empirical.ngs_alignment import (
    NGSAlignmentService,
)
from karcytics_plugins.synthetic_biology.analysis.models.domain import (
    CircuitComponent,
    PlasmidVector,
    SimulationParameters,
)
from karcytics_plugins.synthetic_biology.analysis.result_integrity import (
    DEMO,
    FAILED,
    INVALID,
    TRUSTWORTHY,
    assess,
)
from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
    CircuitSimulationEngine,
)
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.controllers.empirical_controller import (
    EmpiricalAnalyticsController,
)
from karcytics_plugins.synthetic_biology.ui.views.empirical_analytics_view import (
    EmpiricalAnalyticsView,
)


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _view(destroy_after):
    state = SynBioState()
    return destroy_after(EmpiricalAnalyticsView(state, EmpiricalAnalyticsController(state)))


# ── The layer-wide rule ────────────────────────────────────────────────

#: Handlers that receive an analysis payload and render it. Each must consult
#: the integrity rule before showing anything.
PAYLOAD_HANDLERS = (
    "_on_fcs_loaded",
    "_on_ngs_aligned",
    "_on_optimization_finished",
)


@pytest.mark.unit
@pytest.mark.parametrize("handler", PAYLOAD_HANDLERS)
def test_every_payload_handler_consults_the_integrity_rule(handler):
    """The test whose absence allowed C-3 and C-4.

    A handler that renders a payload without asking whether the payload may be
    rendered is the defect, independently of which panel it is in.
    """
    source = inspect.getsource(getattr(EmpiricalAnalyticsView, handler))

    assert "assess(" in source, (
        f"{handler} renders a payload without consulting result_integrity.assess; "
        "this is the defect recorded as C-3 and C-4"
    )
    assert "presentable" in source, f"{handler} calls assess but does not branch on the verdict"


@pytest.mark.unit
@pytest.mark.parametrize("handler", PAYLOAD_HANDLERS)
def test_every_payload_handler_shows_the_verdict(handler):
    """Consulting the rule is not enough; the status must reach the screen."""
    source = inspect.getsource(getattr(EmpiricalAnalyticsView, handler))

    assert "show_verdict" in source, f"{handler} does not surface the verdict"


# ── The rule itself ────────────────────────────────────────────────────


class _Payload:
    def __init__(self, **kw):
        self.__dict__.update(kw)


@pytest.mark.unit
def test_mock_payloads_are_not_presentable():
    verdict = assess(_Payload(is_mock=True, status_message="MOCK DEMO DATA: simulated"))

    assert verdict.level == DEMO
    assert not verdict.presentable
    assert verdict.must_warn
    assert "not computed from your file" in verdict.headline
    assert "MOCK DEMO DATA" in verdict.detail, "the engine's own words are preserved"


@pytest.mark.unit
def test_invalid_payloads_are_not_presentable():
    verdict = assess(_Payload(is_valid=False, error_message="File not found: /tmp/x.fcs"))

    assert verdict.level == INVALID
    assert not verdict.presentable
    assert "File not found" in verdict.detail


@pytest.mark.unit
def test_failed_payloads_are_not_presentable():
    verdict = assess(_Payload(success=False, status_message="No circuit components provided"))

    assert verdict.level == FAILED
    assert not verdict.presentable


@pytest.mark.unit
def test_an_ordinary_result_is_presentable():
    assert assess(_Payload(success=True)).level == TRUSTWORTHY
    assert assess(_Payload()).presentable, "a payload with no flags is a real result"


@pytest.mark.unit
def test_mock_outranks_the_other_flags():
    """Fabricated data that also claims success is still fabricated."""
    verdict = assess(_Payload(is_mock=True, is_valid=True, success=True))

    assert verdict.level == DEMO


@pytest.mark.unit
def test_none_is_not_presentable():
    assert not assess(None).presentable


# ── C-3, at the site ───────────────────────────────────────────────────


@pytest.mark.unit
def test_the_ngs_panel_does_not_tabulate_fabricated_variants(app, destroy_after):
    """The engine returns three invented variants for any file; none may be shown."""
    view = _view(destroy_after)
    plasmid = PlasmidVector(id="p", name="pMine", sequence="ACGT" * 200, is_circular=True)
    result = NGSAlignmentService.align_ngs_reads("/tmp/my_real_reads.fastq", plasmid)

    assert result.is_mock, "fixture guard: the service still returns demo data"
    assert len(result.variants) == 3, "fixture guard: three fabricated calls"

    view._on_ngs_aligned(result)

    assert view.ngs_table.rowCount() == 0, (
        "fabricated variant calls must not be tabulated as findings from the "
        "user's own sequencing run"
    )
    assert not view.ngs_banner.isHidden(), "the banner must be shown"
    assert "not computed from your file" in view.ngs_banner._headline.text()


@pytest.mark.unit
def test_the_critical_off_target_call_does_not_reach_the_table(app, destroy_after):
    """The specific invention that made this Critical: a hardcoded CRISPR hit."""
    view = _view(destroy_after)
    plasmid = PlasmidVector(id="p", name="pMine", sequence="ACGT" * 200)
    result = NGSAlignmentService.align_ngs_reads("/tmp/reads.fastq", plasmid)

    crispr = [v for v in result.variants if v.variant_type == "CRISPR_OffTarget"]
    assert crispr and crispr[0].severity == "Critical", "fixture guard"

    view._on_ngs_aligned(result)

    shown = [
        view.ngs_table.item(r, 0).text()
        for r in range(view.ngs_table.rowCount())
        if view.ngs_table.item(r, 0)
    ]
    assert crispr[0].id not in shown


@pytest.mark.unit
def test_a_real_ngs_result_is_still_tabulated(app, destroy_after):
    """The rule must not suppress genuine results."""
    view = _view(destroy_after)
    plasmid = PlasmidVector(id="p", name="pMine", sequence="ACGT" * 200)
    result = NGSAlignmentService.align_ngs_reads("/tmp/reads.fastq", plasmid)
    result.is_mock = False  # as a real aligner would return it

    view._on_ngs_aligned(result)

    assert view.ngs_table.rowCount() == len(result.variants)
    assert view.ngs_banner.isHidden(), "a real result needs no banner"


# ── C-4, at the site ───────────────────────────────────────────────────


@pytest.mark.unit
def test_the_optimiser_refuses_to_call_a_synthetic_fit_empirical():
    """It may demonstrate; it may not claim a measurement."""
    fcs = FCSDataIngestionService().ingest_fcs_file("/tmp/does_not_exist.fcs")
    assert not fcs.is_valid, "fixture guard"

    components, edges = CircuitSimulationEngine.create_preset_repressilator()
    result = CircuitMLOptimizationEngine.fit_kinetic_parameters(components, edges, fcs)

    assert result.is_mock, "a synthetic-target fit must flag itself"
    assert "empirical dataset" not in result.status_message
    assert "Demonstration fit" in result.status_message
    assert not assess(result).presentable


@pytest.mark.unit
def test_the_optimiser_panel_does_not_show_a_synthetic_fit_as_a_result(app, destroy_after):
    view = _view(destroy_after)
    fcs = FCSDataIngestionService().ingest_fcs_file("/tmp/does_not_exist.fcs")
    components, edges = CircuitSimulationEngine.create_preset_repressilator()
    result = CircuitMLOptimizationEngine.fit_kinetic_parameters(components, edges, fcs)

    view._on_optimization_finished(result)

    assert view.ml_table.rowCount() == 0
    assert not view.ml_banner.isHidden(), "the banner must be shown"
    assert "MSE" not in view.ml_status_lbl.text(), (
        "an error value computed against synthesised targets must not be "
        "presented beside the word Complete"
    )
    assert "Demonstration fit" in view.ml_status_lbl.text()


@pytest.mark.unit
def test_the_demonstration_targets_are_reproducible():
    """Three identical runs gave MSE 0.2319 / 0.1890 / 0.2435 before the seed.

    Asserts the seeded step — the synthetic targets — rather than the fitted
    error. The targets are the only stochastic input, so identical targets
    mean an identical fit, and testing them directly avoids running three
    L-BFGS-B optimisations that each integrate the repressilator ODE per
    objective evaluation. The original form of this test took over two minutes
    and timed out on the Windows runner.
    """
    components, edges = CircuitSimulationEngine.create_preset_repressilator()
    simulated = CircuitSimulationEngine.simulate_circuit(
        components, edges, SimulationParameters(t_start=0.0, t_end=100.0, num_points=50)
    )

    runs = [
        CircuitMLOptimizationEngine._build_target_curves(components, simulated, None)[0]
        for _ in range(3)
    ]

    assert runs[0] == runs[1] == runs[2], "the demonstration targets are not reproducible"
    assert runs[0], "fixture guard: targets were actually built"
    assert DEMO_TARGET_SEED


@pytest.mark.unit
def test_the_demonstration_fit_is_reproducible_end_to_end():
    """The same property through the public entry point, on a one-gene circuit.

    Kept small deliberately: the point is that the fit is deterministic, not
    that a three-gene ring optimises quickly.
    """
    fcs = FCSDataIngestionService().ingest_fcs_file("/tmp/does_not_exist.fcs")
    gene = CircuitComponent(
        id="P",
        name="P",
        component_type="cds",
        y_min=0.001,
        y_max=10.0,
        K_d=1.0,
        n=2.0,
        degradation_rate=0.2,
        initial_concentration=0.0,
    )
    params = SimulationParameters(t_start=0.0, t_end=20.0, num_points=10)

    finals = [
        CircuitMLOptimizationEngine.fit_kinetic_parameters(
            [gene], [], fcs, sim_params=params
        ).final_mse
        for _ in range(2)
    ]

    assert finals[0] == finals[1], f"not reproducible: {finals}"


@pytest.mark.unit
def test_the_optimiser_refuses_outright_when_there_is_nothing_to_fit():
    fcs = FCSDataIngestionService().ingest_fcs_file("/tmp/does_not_exist.fcs")

    result = CircuitMLOptimizationEngine.fit_kinetic_parameters([], [], fcs)

    assert not result.success
    assert not assess(result).presentable


# ── FCS, the third site found by the sweep ─────────────────────────────


@pytest.mark.unit
def test_an_unreadable_fcs_file_says_so_rather_than_showing_an_empty_table(app, destroy_after):
    """An empty table reads as 'no events', not as 'the file never loaded'."""
    view = _view(destroy_after)
    data = FCSDataIngestionService().ingest_fcs_file("/tmp/not_a_real_file.fcs")

    view._on_fcs_loaded(data)

    assert view.fcs_table.rowCount() == 0
    assert not view.fcs_banner.isHidden(), "the banner must be shown"
    assert "not_a_real_file.fcs" in view.fcs_banner._detail.text()


@pytest.mark.unit
def test_a_valid_fcs_payload_is_rendered(app, destroy_after):
    view = _view(destroy_after)
    data = FCSEventData(file_path="/tmp/ok.fcs", total_events=1000, is_valid=True)

    view._on_fcs_loaded(data)

    assert view.fcs_banner.isHidden(), "a real result needs no banner"


# ── Sites the sweep found already correct, pinned so they stay that way ──


@pytest.mark.unit
def test_the_simulation_view_already_refuses_a_failed_result():
    """The precedent the rule was generalised from."""
    from karcytics_plugins.synthetic_biology.ui.views.circuit_simulation_view import (
        CircuitSimulationView,
    )

    source = inspect.getsource(CircuitSimulationView.render_simulation_results)

    assert "result.success" in source
    assert "status_message" in source, "it shows the engine's reason, not its own"


@pytest.mark.unit
def test_a_failed_simulation_never_enters_the_methods_log():
    """A run that produced no trace must not be written up as one that did."""
    from karcytics_plugins.synthetic_biology.ui.controllers.circuit_controller import (
        CircuitSimulationController,
    )

    source = inspect.getsource(CircuitSimulationController._record_run)

    assert "success" in source and "time_points" in source


@pytest.mark.unit
def test_the_amplification_track_shows_the_engines_notes_verbatim():
    """Truncated is communicated through notes; the view must not compose its own."""
    from karcytics_plugins.synthetic_biology.ui.widgets.amplification_track import (
        AmplificationTrack,
    )

    source = inspect.getsource(AmplificationTrack.show_result)

    assert 'getattr(result, "notes"' in source

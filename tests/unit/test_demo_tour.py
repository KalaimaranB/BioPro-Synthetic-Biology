"""The guided demo tour drives the workspace at the presenter's pace.

Loading the demo hands over to a step bar that switches tabs and fires each
simulation as its step is reached, so the presenter narrates while the app
moves itself.
"""

from __future__ import annotations

import pytest

from karcytics_plugins.synthetic_biology.ui.wizards.demo_tour import (
    DemoTourBar,
    build_demo_tour_steps,
)


@pytest.mark.unit
def test_tour_steps_target_real_tabs(destroy_after):
    """Every step must point at a tab that exists, or the tour navigates nowhere."""
    from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel

    panel = destroy_after(SynBioPanel())
    steps = build_demo_tour_steps()

    assert steps, "the tour needs at least one step"
    for step in steps:
        assert 0 <= step.tab_index < panel._tab_bar.count(), step.title
        assert step.title and step.narration


@pytest.mark.unit
def test_tour_bar_navigation_bounds(destroy_after):
    bar = destroy_after(DemoTourBar(build_demo_tour_steps()))
    last = len(build_demo_tour_steps()) - 1

    bar.start()
    assert bar.current_index == 0
    assert bar.isVisible()
    assert not bar.btn_back.isEnabled()

    # Back at the first step is a no-op rather than an index underflow.
    bar.previous_step()
    assert bar.current_index == 0

    for _ in range(last):
        bar.next_step()
    assert bar.current_index == last
    assert bar.btn_next.text() == "Finish"

    # Next on the final step ends the tour instead of overrunning.
    finished: list[bool] = []
    bar.tour_finished.connect(lambda: finished.append(True))
    bar.next_step()
    assert finished == [True]
    assert not bar.isVisible()


@pytest.mark.unit
def test_loading_the_demo_starts_the_tour(destroy_after, monkeypatch):
    from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel

    panel = destroy_after(SynBioPanel())
    # isHidden(), not isVisible(): a child of a panel that was never shown is
    # never "visible", but it does record whether it was explicitly hidden.
    assert panel._demo_tour_bar.isHidden()

    # Loading the demo kicks off a Tellurium run on a background thread; this
    # test is about the hand-over to the tour, not the solver.
    monkeypatch.setattr(
        panel._simulate_view, "plot_time_series", lambda *a, **k: None, raising=False
    )

    panel.demo_showcase_view._on_load_demo_clicked()

    assert not panel._demo_tour_bar.isHidden()
    assert panel._demo_tour_bar.current_index == 0


@pytest.mark.unit
def test_retuning_hill_n_survives_pressing_run(destroy_after):
    """The Hill spin box must not spring back to the circuit's value on Run.

    The Circuit Simulation view adopts a newly loaded circuit's own n, so a
    circuit tuned above its oscillation threshold is not silently detuned. But
    ``_describe_topology`` also runs on every Run of the active design, so
    adopting unconditionally undid the user's retuning the instant they pressed
    Run — which broke the tour's "drop n to 2.1 and watch it damp" step.
    """
    from karcytics_plugins.synthetic_biology.analysis.simulation.topology import circuit_from_parts
    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
    from karcytics_plugins.synthetic_biology.ui.controllers.circuit_controller import (
        CircuitSimulationController,
    )
    from karcytics_plugins.synthetic_biology.ui.views.circuit_simulation_view import (
        CircuitSimulationView,
    )
    from karcytics_plugins.synthetic_biology.ui.views.demo_showcase_view import build_demo_strand

    state = SynBioState()
    parts = build_demo_strand()
    components, edges = circuit_from_parts(parts)
    state.design_parts = parts
    state.set_circuit_components(components)
    state.set_circuit_edges(edges)

    view = destroy_after(CircuitSimulationView(state, CircuitSimulationController(state)))

    # The circuit's own n is adopted when it first loads.
    view._load_active_design()
    view._describe_topology()
    assert view.hill_n_spin.value() == pytest.approx(2.5)

    # A deliberate retune then sticks across a reload of the same circuit.
    view.hill_n_spin.setValue(2.1)
    view._load_active_design()
    view._describe_topology()
    assert view.hill_n_spin.value() == pytest.approx(2.1)


@pytest.mark.unit
def test_tour_ends_with_the_write_up_and_saving():
    """The syllabus-facing features must be part of the demo, in a sensible order:
    the write-up after the analyses it describes, saving last.
    """
    titles = [s.title for s in build_demo_tour_steps()]
    assert titles[-2:] == ["The write-up", "Save and come back next week"]
    assert titles.index("Molecule by molecule") < titles.index("The write-up")


@pytest.mark.unit
def test_tour_opens_methods_dialog_and_closes_it_when_moving_on(destroy_after, monkeypatch):
    from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel

    panel = destroy_after(SynBioPanel())
    monkeypatch.setattr(panel._simulate_view, "plot_time_series", lambda *a, **k: None)
    monkeypatch.setattr(panel.circuit_view, "_on_run_sim_clicked", lambda: None)
    panel.demo_showcase_view._on_load_demo_clicked()

    bar = panel._demo_tour_bar
    write_up = [s.title for s in build_demo_tour_steps()].index("The write-up")
    while bar.current_index < write_up:
        bar.next_step()

    dialog = panel._methods_dialog
    assert dialog is not None and not dialog.isHidden()
    text = dialog.methods_edit.toPlainText()
    assert "Protein dynamics of the 3-gene circuit" in text
    assert "solver = RK45" in text

    bar.next_step()  # to the save step: the dialog must not cover it
    assert dialog.isHidden()

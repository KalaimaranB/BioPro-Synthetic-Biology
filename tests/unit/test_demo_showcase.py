"""The Demo Showcase tab must describe the circuit the engines actually produce.

This tab used to carry a hand-written copy of the circuit, the plasmid map, the
guide RNAs and the simulation trace alongside the real engines, and the copies
had drifted:

* the trace was a closed-form damped sine, captioned "Sustained Repressilator
  Limit Cycle", that plotted a species (cI) the hand-written circuit did not
  contain;
* the hand-written circuit was not an oscillator at all — two of its four edges
  had ``interaction_type="transcription"``, which the Hill solver skips, so the
  real engine returned monotonic saturating curves;
* promoters and a terminator were circuit nodes, so the solver gave a terminator
  a protein concentration;
* the card claimed 4,382 bp over a 43,820 bp sequence;
* the protospacers were 18 nt under a column headed "Protospacer (20bp)" and
  occurred in none of the sequences the module ships.

Each test below pins one of those properties so the panels cannot drift from
engine output again.
"""

from __future__ import annotations

import numpy as np
import pytest

from karcytics_plugins.synthetic_biology.analysis.models.domain import SimulationParameters
from karcytics_plugins.synthetic_biology.analysis.parts.components import CDS, Promoter, Terminator
from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
    CircuitSimulationEngine,
)
from karcytics_plugins.synthetic_biology.analysis.simulation.topology import circuit_from_parts
from karcytics_plugins.synthetic_biology.ui.views.demo_showcase_view import (
    DEMO_NUM_POINTS,
    DEMO_T_END,
    build_demo_grnas,
    build_demo_plasmid,
    build_demo_strand,
)


def _demo_circuit():
    return circuit_from_parts(build_demo_strand())


@pytest.mark.unit
def test_demo_strand_compiles_to_a_three_node_repressor_ring():
    components, edges = _demo_circuit()

    assert len(components) == 3
    assert {c.name for c in components} == {"LacI", "cI", "TetR"}

    # Every edge is repression: a 'transcription' edge is silently skipped by
    # the Hill solver, which is how the old demo lost its feedback loop.
    assert [e.interaction_type for e in edges] == ["repression"] * 3

    # One in, one out per node — a cycle, not a chain.
    assert sorted(e.source_id for e in edges) == sorted(c.id for c in components)
    assert sorted(e.target_id for e in edges) == sorted(c.id for c in components)


@pytest.mark.unit
def test_demo_circuit_contains_only_diffusible_species():
    """Only coding parts become nodes; a promoter or terminator has no concentration."""
    components, _ = _demo_circuit()

    assert all(c.component_type in {"cds", "sgrna"} for c in components)

    strand = build_demo_strand()
    non_coding = {p.name for p in strand if isinstance(p, Promoter | Terminator)}
    assert non_coding, "the demo strand should contain promoters and terminators"
    assert non_coding.isdisjoint({c.name for c in components})


@pytest.mark.unit
def test_demo_oscillation_is_sustained_not_damping():
    """The tab says 'sustained'; the solver has to agree.

    At the n = 2.1 the demo used to request, the amplitude over the last third
    of the window fell to about 6% of the first third.
    """
    components, edges = _demo_circuit()
    result = CircuitSimulationEngine.simulate_circuit(
        components,
        edges,
        SimulationParameters(t_start=0.0, t_end=DEMO_T_END, num_points=DEMO_NUM_POINTS),
    )

    assert result.success, result.status_message
    # Traces are named for the protein and the organism the gene came from.
    assert set(result.species_concentrations) == {
        "LacI (E. coli lac operon)",
        "cI (phage lambda)",
        "TetR (Tn10)",
    }

    for name, series in result.species_concentrations.items():
        trace = np.asarray(series, dtype=float)
        assert np.all(np.isfinite(trace)), name

        third = len(trace) // 3
        amp_first = trace[:third].max() - trace[:third].min()
        amp_last = trace[-third:].max() - trace[-third:].min()

        assert amp_first > 1.0, f"{name} never oscillated"
        assert amp_last > 0.8 * amp_first, (
            f"{name} amplitude decayed {amp_first:.3f} -> {amp_last:.3f} RPU; "
            "the tab claims a sustained cycle"
        )


@pytest.mark.unit
def test_demo_plasmid_length_matches_its_feature_map():
    """The displayed bp count is read off the sequence, so it cannot disagree."""
    parts = build_demo_strand()
    plasmid = build_demo_plasmid(parts)

    assert plasmid.is_circular
    assert len(plasmid.sequence) > 0
    # Every part on the strand is annotated, plus the backbone.
    assert len(plasmid.features) == len(parts) + 1

    for feat in plasmid.features:
        assert 0 <= feat.start < feat.end <= len(plasmid.sequence), feat.name

    # Features tile the sequence end to end with no gap or overlap.
    ordered = sorted(plasmid.features, key=lambda f: f.start)
    for previous, nxt in zip(ordered, ordered[1:], strict=False):
        assert previous.end == nxt.start, f"{previous.name} -> {nxt.name}"
    assert ordered[-1].end == len(plasmid.sequence)


@pytest.mark.unit
def test_demo_grnas_are_real_twenty_mers_in_the_demo_target():
    """The guides shown must occur in a sequence the demo actually ships."""
    guides = build_demo_grnas()
    assert guides, "the lacI CDS should yield SpCas9 sites"

    laci = next(
        p.sequence for p in build_demo_strand() if isinstance(p, CDS) and p.product == "LacI"
    )
    reverse_complement = (
        laci.upper().translate(str.maketrans("ACGT", "TGCA"))[::-1]  # noqa: FURB184
    )

    for guide in guides:
        assert len(guide.protospacer) == 20, guide.protospacer
        haystack = laci.upper() if guide.strand >= 0 else reverse_complement
        assert guide.protospacer in haystack, guide.protospacer
        assert 0.0 <= guide.gc_content <= 100.0
        assert 0.0 <= guide.efficiency_score <= 100.0


@pytest.mark.unit
def test_source_organism_reaches_both_simulators():
    """A trace names the organism the gene came from, in every tab.

    Antimony identifiers cannot hold spaces or parentheses, so the compiled
    species is bare ("LacI") and the Simulate tab has to recover the full label
    from the circuit. Without that mapping the organism reached the Circuit
    Simulation tab and silently vanished from the Simulate tab.
    """
    from karcytics_plugins.synthetic_biology.ui.controllers.circuit_controller import (
        antimony_var_names,
        species_display_labels,
    )

    components, _ = _demo_circuit()

    organisms = {c.name: c.source_organism for c in components}
    assert organisms == {
        "LacI": "E. coli lac operon",
        "cI": "phage lambda",
        "TetR": "Tn10",
    }

    # The Antimony identifier stays a bare, valid identifier.
    for var in antimony_var_names(components).values():
        assert var.isidentifier(), var

    # And it maps back to the label a reader should see.
    assert set(species_display_labels(components).items()) == {
        ("LacI", "LacI (E. coli lac operon)"),
        ("cI", "cI (phage lambda)"),
        ("TetR", "TetR (Tn10)"),
    }


@pytest.mark.unit
def test_display_label_falls_back_to_the_bare_name():
    """A part with no declared organism is labelled by name alone, not 'X ()'."""
    from karcytics_plugins.synthetic_biology.analysis.models.domain import CircuitComponent

    assert CircuitComponent(id="g", name="GFP", component_type="cds").display_label == "GFP"
    assert (
        CircuitComponent(
            id="g", name="GFP", component_type="cds", source_organism="A. victoria"
        ).display_label
        == "GFP (A. victoria)"
    )


@pytest.mark.unit
def test_loading_the_demo_records_its_methods(destroy_after):
    """The Methods paragraph must describe what the demo actually ran, with the
    parameters it used and the papers behind them.
    """
    from karcytics_plugins.synthetic_biology.analysis.citations import cited_keys, methods_text
    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
    from karcytics_plugins.synthetic_biology.ui.views.demo_showcase_view import (
        DemoShowcaseView,
        scan_demo_target,
    )

    state = SynBioState()
    view = destroy_after(DemoShowcaseView(state))
    view._on_load_demo_clicked()

    by_kind = {e["kind"]: e for e in state.methods_log}
    assert set(by_kind) == {"design", "assembly", "crispr_scan", "circuit_ode"}
    assert by_kind["circuit_ode"]["parameters"]["Hill coefficient n"] == "2.5"
    assert by_kind["circuit_ode"]["parameters"]["duration"] == "400 min"
    assert by_kind["crispr_scan"]["parameters"]["candidates"] == len(scan_demo_target())
    assert by_kind["assembly"]["description"].startswith(
        f"The construct was assembled in silico into pSB1A3-Repressilator, a "
        f"{len(state.get_active_plasmid().sequence):,} bp circular vector"
    )

    keys = cited_keys(state.methods_log)
    assert {"elowitz2000", "virtanen2020", "dormand1980", "jinek2012"} <= set(keys)
    assert "Images were analysed" not in methods_text(state.methods_log)


@pytest.mark.unit
def test_reloading_the_demo_does_not_keep_stale_methods(destroy_after):
    from karcytics_plugins.synthetic_biology.analysis.citations import primer_step
    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
    from karcytics_plugins.synthetic_biology.ui.views.demo_showcase_view import DemoShowcaseView

    state = SynBioState()
    state.record_method(primer_step(60.0, 60.0, 60.0))  # from an earlier workspace
    destroy_after(DemoShowcaseView(state))._on_load_demo_clicked()

    assert "primer_design" not in {e["kind"] for e in state.methods_log}

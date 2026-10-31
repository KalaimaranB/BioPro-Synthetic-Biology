"""Compiling a designed strand into a simulatable circuit topology.

Before this existed, nothing turned the Design canvas into a network: the
Circuit Simulation tab only ever ran its built-in presets, and promoters with
no declared repressors made every circuit silently constitutive.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from karcytics_plugins.synthetic_biology.analysis.parts.components import (
    CDS,
    RBS,
    Promoter,
    Terminator,
)
from karcytics_plugins.synthetic_biology.analysis.simulation.topology import circuit_from_parts


def _inverter_strand() -> list:
    """PTet drives GFP; pTet is repressed by TetR, expressed from its own unit."""
    return [
        Promoter(
            id="pConst",
            name="pConst",
            sequence="TTGACA",
            y_min=0.01,
            y_max=5.0,
            K_d=1.0,
            n=2.0,
        ),
        RBS(id="rbs1", name="B0034", sequence="AAAGAGGAGAAA"),
        CDS(
            id="cds_tetr", name="TetR CDS", sequence="ATGTCT", product="TetR", degradation_rate=0.2
        ),
        Terminator(id="t1", name="B0015", sequence="CCAGGCAT"),
        Promoter(
            id="pTet",
            name="pTet",
            sequence="TCCCTATCAG",
            y_min=0.02,
            y_max=10.0,
            K_d=0.5,
            n=2.4,
            repressors=["TetR"],
        ),
        RBS(id="rbs2", name="B0034", sequence="AAAGAGGAGAAA"),
        CDS(id="cds_gfp", name="GFP CDS", sequence="ATGAGT", product="GFP", degradation_rate=0.05),
    ]


@pytest.mark.unit
def test_strand_compiles_to_one_node_per_coding_part():
    components, _ = circuit_from_parts(_inverter_strand())

    assert [c.id for c in components] == ["cds_tetr", "cds_gfp"]
    assert [c.name for c in components] == ["TetR", "GFP"]


@pytest.mark.unit
def test_gene_inherits_expression_params_from_its_governing_promoter():
    """GFP sits under pTet, so it takes pTet's transfer curve, not pConst's."""
    components, _ = circuit_from_parts(_inverter_strand())
    gfp = {c.id: c for c in components}["cds_gfp"]

    assert gfp.y_max == pytest.approx(10.0)
    assert gfp.K_d == pytest.approx(0.5)
    assert gfp.n == pytest.approx(2.4)
    # Decay belongs to the coding part itself.
    assert gfp.degradation_rate == pytest.approx(0.05)


@pytest.mark.unit
def test_declared_repressor_becomes_an_edge_from_its_producer():
    _, edges = circuit_from_parts(_inverter_strand())

    assert len(edges) == 1
    assert edges[0].source_id == "cds_tetr"
    assert edges[0].target_id == "cds_gfp"
    assert edges[0].interaction_type == "repression"


@pytest.mark.unit
def test_terminator_ends_the_transcription_unit():
    """A gene after a terminator with no new promoter is not expressed."""
    parts = [
        Promoter(id="p1", name="p1", sequence="TTGACA", y_max=5.0),
        CDS(id="c1", name="A", sequence="ATG", product="A"),
        Terminator(id="t1", name="term", sequence="CCAGG"),
        CDS(id="c2", name="B", sequence="ATG", product="B"),
    ]

    components, _ = circuit_from_parts(parts)

    assert [c.id for c in components] == ["c1"]


@pytest.mark.unit
def test_coding_part_before_any_promoter_is_not_expressed():
    parts = [
        CDS(id="orphan", name="Orphan", sequence="ATG", product="Orphan"),
        Promoter(id="p1", name="p1", sequence="TTGACA", y_max=5.0),
        CDS(id="c1", name="A", sequence="ATG", product="A"),
    ]

    components, _ = circuit_from_parts(parts)

    assert [c.id for c in components] == ["c1"]


@pytest.mark.unit
def test_repressor_declared_but_not_produced_yields_no_edge():
    """A dangling repressor name must not fabricate an edge."""
    parts = [
        Promoter(id="p1", name="p1", sequence="TTGACA", y_max=5.0, repressors=["NotPresent"]),
        CDS(id="c1", name="A", sequence="ATG", product="A"),
    ]

    components, edges = circuit_from_parts(parts)

    assert len(components) == 1
    assert edges == []


@pytest.mark.unit
def test_empty_and_partless_strands_compile_to_nothing():
    assert circuit_from_parts([]) == ([], [])
    assert circuit_from_parts([Terminator(id="t", name="t", sequence="CC")]) == ([], [])


@pytest.mark.unit
def test_repressed_circuit_gets_a_nonzero_initial_condition():
    """An all-zero repressor ring is a fixed point and would plot flat."""
    components, edges = circuit_from_parts(_inverter_strand())

    assert edges, "expected regulation in this strand"
    assert any(c.initial_concentration > 0 for c in components)


@pytest.mark.unit
def test_compiled_design_simulates_with_visible_regulation():
    """End-to-end: the repressed gene stays below its own maximum."""
    from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
        CircuitSimulationEngine,
    )

    components, edges = circuit_from_parts(_inverter_strand())
    result = CircuitSimulationEngine.simulate_circuit(components, edges)

    assert result.success, result.status_message
    gfp_trace = result.species_concentrations["GFP"]
    gfp_max = {c.id: c for c in components}["cds_gfp"].y_max
    # Repression holds GFP well under the promoter's unrepressed ceiling.
    assert max(gfp_trace) < gfp_max


@pytest.mark.unit
def test_shipped_catalogue_promoters_declare_their_repressor():
    """Every catalogue promoter links to a repressor CDS that is also shipped.

    Empty repressor lists made real catalogue parts compile to constitutive
    circuits with no regulation at all.
    """
    cat_path = (
        Path(__file__).resolve().parents[2]
        / "src/karcytics_plugins/synthetic_biology/catalogue.json"
    )
    catalogue = json.loads(cat_path.read_text())

    products = {p.get("product") for p in catalogue if p.get("part_type") == "cds"}
    promoters = [p for p in catalogue if p.get("part_type") == "promoter"]

    assert promoters, "catalogue should ship promoters"
    for promoter in promoters:
        repressors = promoter.get("repressors") or []
        assert repressors, f"{promoter['id']} declares no repressor"
        for rep in repressors:
            assert rep in products, f"{promoter['id']} names unknown repressor {rep}"

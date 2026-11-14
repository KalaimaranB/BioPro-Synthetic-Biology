"""elowitz2000 may be attached only to the topology the paper establishes.

Elowitz & Leibler (2000) integrate six equations - an mRNA and a protein
species per gene - and the transcription-translation delay drives the cycle.
This module integrates one species per gene. The paper supports the cyclic
repressor-ring wiring; it does not support these dynamics, and a student's
methods paragraph must not claim otherwise.
"""

from __future__ import annotations

import pytest

from karcytics_plugins.synthetic_biology.analysis import citations
from karcytics_plugins.synthetic_biology.analysis.models.domain import (
    CircuitComponent,
    CircuitEdge,
)
from karcytics_plugins.synthetic_biology.analysis.simulation.circuit_engine import (
    MODEL_PROVENANCE,
    CircuitSimulationEngine,
)
from karcytics_plugins.synthetic_biology.analysis.simulation.topology import is_repressor_ring


def _nodes(ids, n=2.5):
    return [CircuitComponent(id=i, name=i, component_type="cds", n=n) for i in ids]


def _ring(size=3):
    ids = [chr(ord("A") + i) for i in range(size)]
    edges = [CircuitEdge(ids[i], ids[(i + 1) % size], "repression") for i in range(size)]
    return _nodes(ids), edges


def _toggle():
    return _nodes("AB"), [
        CircuitEdge("A", "B", "repression"),
        CircuitEdge("B", "A", "repression"),
    ]


# ── The methods text must name the model that ran ─────────────────────


@pytest.mark.unit
def test_the_methods_text_names_the_reduction_not_the_published_model():
    entry = citations.circuit_ode_step(*_ring(), "RK45", 400, 1600)
    text = citations.methods_text([entry])

    assert "single protein species" in text
    assert "reduced, protein-only form of their model" in text
    assert "mRNA species per gene" in text
    assert entry["parameters"]["model"] == "reduced protein-only ring (no mRNA species)"


@pytest.mark.unit
def test_the_methods_text_does_not_claim_the_six_equation_system():
    """A student pasting this into a report must not assert the published model."""
    text = citations.methods_text([citations.circuit_ode_step(*_ring(), "RK45", 400, 1600)])
    lowered = text.lower()
    for overclaim in ("as described by elowitz", "reproducing elowitz", "the elowitz model"):
        assert overclaim not in lowered


@pytest.mark.unit
def test_a_non_ring_run_says_nothing_about_a_ring():
    entry = citations.circuit_ode_step(*_toggle(), "RK45", 400, 1600)
    assert "cyclic repressor ring" not in entry["description"]
    assert "model" not in entry["parameters"]


# ── Scope: only a repressor ring may collect the citation ─────────────


@pytest.mark.unit
def test_a_two_gene_toggle_switch_does_not_pick_up_elowitz():
    """It used to: any repressing edge attached the citation."""
    assert (
        "elowitz2000" not in citations.circuit_ode_step(*_toggle(), "RK45", 400, 1600)["citations"]
    )


@pytest.mark.unit
def test_a_three_gene_repressor_ring_does_pick_up_elowitz():
    assert "elowitz2000" in citations.circuit_ode_step(*_ring(), "RK45", 400, 1600)["citations"]


@pytest.mark.unit
def test_the_shipped_preset_still_qualifies_as_a_ring():
    components, edges = CircuitSimulationEngine.create_preset_repressilator()
    assert is_repressor_ring(components, edges) is True
    assert (
        "elowitz2000"
        in citations.circuit_ode_step(components, edges, "RK45", 400, 1600)["citations"]
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("label", "builder"),
    [
        ("single repressed gene", lambda: (_nodes("A"), [CircuitEdge("A", "A", "repression")])),
        ("two-gene toggle", _toggle),
        (
            "ring with one activating edge",
            lambda: (
                _nodes("ABC"),
                [
                    CircuitEdge("A", "B", "repression"),
                    CircuitEdge("B", "C", "activation"),
                    CircuitEdge("C", "A", "repression"),
                ],
            ),
        ),
        (
            "two disjoint three-rings",
            lambda: (
                _nodes("ABCDEF"),
                [
                    CircuitEdge("A", "B", "repression"),
                    CircuitEdge("B", "C", "repression"),
                    CircuitEdge("C", "A", "repression"),
                    CircuitEdge("D", "E", "repression"),
                    CircuitEdge("E", "F", "repression"),
                    CircuitEdge("F", "D", "repression"),
                ],
            ),
        ),
    ],
)
def test_these_topologies_are_not_the_published_ring(label, builder):
    components, edges = builder()
    assert is_repressor_ring(components, edges) is False, label
    assert (
        "elowitz2000"
        not in citations.circuit_ode_step(components, edges, "RK45", 400, 1600)["citations"]
    ), label


# ── The provenance record carries the distinction ─────────────────────


@pytest.mark.unit
def test_the_model_provenance_separates_topology_from_dynamics():
    entry = MODEL_PROVENANCE["repressilator_topology"]
    assert entry.kind == "convention", "the reduced dynamics are our choice"
    assert entry.mechanism == ("elowitz2000",)
    assert "topology and not these" in entry.mechanism_claim
    assert "mRNA" in entry.mechanism_claim


@pytest.mark.unit
def test_the_provenance_claim_disowns_the_hopf_threshold():
    """The threshold and the preset's n are properties of the reduction.

    The figure moved from 2.1484 to 2.4514 when production was scaled by the
    degradation rate to fix the RPU x min unit error, so this asserts the
    current one. What must not drift is the disowning itself.
    """
    claim = MODEL_PROVENANCE["repressilator_topology"].mechanism_claim
    assert "2.4514" in claim, "the post-scaling threshold"
    assert "2.15" not in claim, "the pre-scaling figure must not linger"
    assert "3.5" in claim, "the preset's own n is not the paper's either"
    assert "does not support" in claim


@pytest.mark.unit
def test_the_preset_docstring_states_the_reduction():
    doc = CircuitSimulationEngine.create_preset_repressilator.__doc__ or ""
    assert "reduced, protein-only" in doc
    assert "six coupled equations" in doc or "mRNA species" in doc
    assert "dynamics are not theirs" in doc.lower()

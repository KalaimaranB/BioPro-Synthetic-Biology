"""Compile a designed DNA strand into a simulatable circuit topology.

The Design canvas produces an ordered list of ``BiologicalPart`` objects — the
physical construct. The simulators consume ``CircuitComponent`` nodes and
``CircuitEdge`` regulatory connections — the network. This module is the one
bridge between them, so the Design, Biological View, Circuit Simulation and
Simulate tabs all describe the same circuit.

Transcription-unit rule: a promoter governs every CDS / sgRNA that follows it
on the strand until the next promoter or terminator. Each such gene becomes one
node, taking its expression parameters from the governing promoter and its
decay from the part itself. A promoter's declared repressors / activators
become edges from whichever gene produces that molecule.
"""

from __future__ import annotations

from ..models.domain import CircuitComponent, CircuitEdge
from ..parts.base import BiologicalPart
from ..parts.components import CDS, Promoter, Terminator, sgRNA
from .kinetics import (
    DEFAULT_DEGRADATION_RATE,
    DEFAULT_K_D,
    DEFAULT_N,
    DEFAULT_Y_MAX,
    DEFAULT_Y_MIN,
)


def product_name(part: BiologicalPart) -> str:
    """The molecule a coding part expresses.

    Falls back to the part's name, then its id, so a part with no explicit
    product still participates in the network.
    """
    explicit = getattr(part, "product", "") or ""
    if explicit:
        return str(explicit)
    return str(part.name or part.id).replace(" ", "_")


def circuit_from_parts(
    parts: list[BiologicalPart],
) -> tuple[list[CircuitComponent], list[CircuitEdge]]:
    """Compile an ordered strand of parts into circuit nodes and edges.

    Args:
        parts: Parts in strand order, as placed on the Design canvas.

    Returns:
        ``(components, edges)``. Empty when the strand contains no coding part
        under a promoter — there is nothing to express.
    """
    components: list[CircuitComponent] = []
    edges: list[CircuitEdge] = []

    # product molecule -> ids of the nodes that express it
    producers: dict[str, list[str]] = {}
    # node id -> the promoter driving it
    governing: dict[str, Promoter] = {}

    current_promoter: Promoter | None = None

    for part in parts:
        if isinstance(part, Promoter):
            current_promoter = part
            continue

        if isinstance(part, Terminator):
            # Transcription stops here; the next gene needs its own promoter.
            current_promoter = None
            continue

        if not isinstance(part, CDS | sgRNA) or current_promoter is None:
            continue

        product = product_name(part)
        node_id = part.id or product

        components.append(
            CircuitComponent(
                id=node_id,
                name=product,
                component_type=part.part_type,
                y_min=_or_default(current_promoter.y_min, DEFAULT_Y_MIN),
                y_max=_or_default(current_promoter.y_max, DEFAULT_Y_MAX),
                K_d=_or_default(current_promoter.K_d, DEFAULT_K_D),
                n=_or_default(current_promoter.n, DEFAULT_N),
                degradation_rate=_or_default(
                    getattr(part, "degradation_rate", None), DEFAULT_DEGRADATION_RATE
                ),
                translation_rate=_or_default(getattr(part, "translation_rate", None), 1.0),
                initial_concentration=0.0,
                source_organism=str(getattr(part, "source_organism", "") or ""),
            )
        )
        producers.setdefault(product, []).append(node_id)
        governing[node_id] = current_promoter

    # Wire regulation now that every producer is known: a promoter's repressor
    # may be expressed further down the strand than the gene it represses.
    for node_id, promoter in governing.items():
        for molecule in getattr(promoter, "repressors", []) or []:
            edges.extend(_edges_for(molecule, node_id, "repression", producers))
        for molecule in getattr(promoter, "activators", []) or []:
            edges.extend(_edges_for(molecule, node_id, "activation", producers))

    _seed_initial_conditions(components, edges)
    return components, edges


def _or_default(value: float | None, default: float) -> float:
    return float(value) if value is not None else default


def _edges_for(
    molecule: str,
    target_id: str,
    interaction_type: str,
    producers: dict[str, list[str]],
) -> list[CircuitEdge]:
    """Edges from every node expressing ``molecule`` to ``target_id``."""
    return [
        CircuitEdge(
            source_id=source_id,
            target_id=target_id,
            interaction_type=interaction_type,
        )
        for source_id in producers.get(molecule, [])
        if source_id != target_id
    ]


def _seed_initial_conditions(
    components: list[CircuitComponent],
    edges: list[CircuitEdge],
) -> None:
    """Break the symmetry of a fully repressed ring so it can oscillate.

    Every node starting at zero is a fixed point for a repressor ring: nothing
    ever moves. Seeding one repressor in each cycle reproduces the standard
    repressilator initial condition instead of a flat line.
    """
    if not components or not edges:
        return

    repressed = {e.target_id for e in edges if e.interaction_type.lower() == "repression"}
    if not repressed:
        return

    by_id = {c.id: c for c in components}
    for node_id in sorted(repressed):
        comp = by_id.get(node_id)
        if comp is not None:
            comp.initial_concentration = comp.y_max / 2.0
            return

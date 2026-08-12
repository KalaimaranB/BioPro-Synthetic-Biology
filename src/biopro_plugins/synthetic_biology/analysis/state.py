"""Synthetic Biology workspace state container.

``SynBioState`` is the single source of truth (Centralized State Management)
for the entire design and simulation session. It follows the layered pattern
split into domain-model state (``CircuitState``) and UI-presentation state
(``ViewState``), with ``to_dict`` / ``from_dict`` for snapshotting and event
notification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from biopro_sdk.plugin import PluginState, get_logger

from . import events  # noqa: F401
from .models.domain import (
    PlasmidVector,
    SimulationResult,
    gRNACandidate,
)

logger = get_logger(__name__, "synthetic_biology")


@dataclass
class CircuitState:
    """Domain model state layer.

    Holds standard parts, vector constructs, CRISPR guide targets,
    circuit topology, and simulation results for the session.
    """

    parts: List[Dict[str, Any]] = field(default_factory=list)
    connections: List[Dict[str, Any]] = field(default_factory=list)
    simulation_results: Dict[str, Any] = field(default_factory=dict)
    active_plasmid: Optional[Dict[str, Any]] = field(default_factory=dict)
    grna_candidates: List[Dict[str, Any]] = field(default_factory=list)
    circuit_nodes: List[Dict[str, Any]] = field(default_factory=list)
    circuit_edges: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "parts": self.parts,
            "connections": self.connections,
            "simulation_results": self.simulation_results,
            "active_plasmid": self.active_plasmid,
            "grna_candidates": self.grna_candidates,
            "circuit_nodes": self.circuit_nodes,
            "circuit_edges": self.circuit_edges,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CircuitState:
        state = cls()
        state.parts = data.get("parts", [])
        state.connections = data.get("connections", [])
        state.simulation_results = data.get("simulation_results", {})
        state.active_plasmid = data.get("active_plasmid", {})
        state.grna_candidates = data.get("grna_candidates", [])
        state.circuit_nodes = data.get("circuit_nodes", [])
        state.circuit_edges = data.get("circuit_edges", [])
        return state


@dataclass
class ViewState:
    """UI and presentation state layer."""

    active_tab: int = 0
    selected_part_id: Optional[str] = None
    selected_connection_id: Optional[str] = None
    selected_grna_id: Optional[str] = None
    zoom_level: float = 1.0
    canvas_offset_x: float = 0.0
    canvas_offset_y: float = 0.0

    def to_dict(self) -> dict:
        return {
            "active_tab": self.active_tab,
            "selected_part_id": self.selected_part_id,
            "selected_connection_id": self.selected_connection_id,
            "selected_grna_id": self.selected_grna_id,
            "zoom_level": self.zoom_level,
            "canvas_offset_x": self.canvas_offset_x,
            "canvas_offset_y": self.canvas_offset_y,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ViewState:
        state = cls()
        state.active_tab = data.get("active_tab", 0)
        state.selected_part_id = data.get("selected_part_id")
        state.selected_connection_id = data.get("selected_connection_id")
        state.selected_grna_id = data.get("selected_grna_id")
        state.zoom_level = data.get("zoom_level", 1.0)
        state.canvas_offset_x = data.get("canvas_offset_x", 0.0)
        state.canvas_offset_y = data.get("canvas_offset_y", 0.0)
        return state


@dataclass
class SynBioState(PluginState):
    """Mutable state for one synthetic biology design session.

    Acts as the Single Source of Truth for all tools (Assembly, CRISPR, Simulation).
    """

    data: CircuitState = field(default_factory=CircuitState)
    view: ViewState = field(default_factory=ViewState)

    def set_active_plasmid(self, plasmid: PlasmidVector) -> None:
        """Centralized update for current active plasmid vector."""
        self.data.active_plasmid = plasmid.to_dict()
        logger.info(
            f"SynBioState updated active plasmid: {plasmid.name} ({plasmid.length} bp)"
        )

    def get_active_plasmid(self) -> Optional[PlasmidVector]:
        """Retrieve current plasmid vector model."""
        if not self.data.active_plasmid:
            return None
        return PlasmidVector.from_dict(self.data.active_plasmid)

    def set_grna_candidates(self, candidates: List[gRNACandidate]) -> None:
        """Centralized update for CRISPR guide RNA candidate results."""
        self.data.grna_candidates = [c.to_dict() for c in candidates]
        logger.info(f"SynBioState updated {len(candidates)} gRNA candidates.")

    def get_grna_candidates(self) -> List[gRNACandidate]:
        """Retrieve list of current gRNA candidates."""
        return [gRNACandidate.from_dict(c) for c in self.data.grna_candidates]

    def set_simulation_result(self, result: SimulationResult) -> None:
        """Centralized update for kinetic circuit simulation output."""
        self.data.simulation_results = result.to_dict()
        logger.info(
            f"SynBioState updated simulation result: {len(result.time_points)} points."
        )

    def get_simulation_result(self) -> Optional[SimulationResult]:
        """Retrieve latest simulation result."""
        if not self.data.simulation_results:
            return None
        return SimulationResult.from_dict(self.data.simulation_results)

    def to_dict(self) -> dict:
        """Standard serialization for undo history snapshots."""
        return {
            "data": self.data.to_dict(),
            "view": self.view.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SynBioState:
        """Reconstruct nested state objects."""
        state = cls()
        if "data" in data:
            state.data = CircuitState.from_dict(data["data"])
        if "view" in data:
            state.view = ViewState.from_dict(data["view"])
        return state

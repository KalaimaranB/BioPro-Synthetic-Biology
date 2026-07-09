"""Synthetic Biology workspace state container.

``SynBioState`` is the single source of truth for the entire analysis
session.  It follows the same layered pattern as the Flow Cytometry
``FlowState``: a plain dataclass split into domain-model state
(``CircuitState``) and UI-presentation state (``ViewState``), with
``to_dict`` / ``from_dict`` for serialization.

The state is intentionally kept separate from both the UI and the
analysis engines so that:
- Undo/Redo can snapshot it cheaply via ``export_state`` / ``load_state``.
- It can be serialized to disk independently of the GUI.
- Tests can inspect it without importing PyQt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from biopro_sdk.plugin import PluginState, get_logger

from . import events  # noqa: F401

logger = get_logger(__name__, "synthetic_biology")


@dataclass
class CircuitState:
    """Domain model state layer.

    Holds all biological parts, wiring connections, and simulation
    results for the current circuit design session.
    """

    parts: list[dict[str, Any]] = field(default_factory=list)
    connections: list[dict[str, Any]] = field(default_factory=list)
    simulation_results: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "parts": self.parts,
            "connections": self.connections,
            "simulation_results": self.simulation_results,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CircuitState:
        state = cls()
        state.parts = data.get("parts", [])
        state.connections = data.get("connections", [])
        state.simulation_results = data.get("simulation_results", {})
        return state


@dataclass
class ViewState:
    """UI and presentation state layer."""

    active_tab: int = 0
    selected_part_id: str | None = None
    selected_connection_id: str | None = None
    zoom_level: float = 1.0
    canvas_offset_x: float = 0.0
    canvas_offset_y: float = 0.0

    def to_dict(self) -> dict:
        return {
            "active_tab": self.active_tab,
            "selected_part_id": self.selected_part_id,
            "selected_connection_id": self.selected_connection_id,
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
        state.zoom_level = data.get("zoom_level", 1.0)
        state.canvas_offset_x = data.get("canvas_offset_x", 0.0)
        state.canvas_offset_y = data.get("canvas_offset_y", 0.0)
        return state


@dataclass
class SynBioState(PluginState):
    """Mutable state for one synthetic biology design session.

    Layered into 'data' (CircuitState) and 'view' (ViewState),
    following the same architecture as FlowState.
    """

    # ── Layers ────────────────────────────────────────────────────────
    data: CircuitState = field(default_factory=CircuitState)
    view: ViewState = field(default_factory=ViewState)

    def to_dict(self) -> dict:
        """Standard serialization for undo history snapshots."""
        return {
            "data": self.data.to_dict(),
            "view": self.view.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> SynBioState:
        """Reconstruct the nested state objects properly from dict for Undo/Redo."""
        state = cls()
        if "data" in data:
            state.data = CircuitState.from_dict(data["data"])
        if "view" in data:
            state.view = ViewState.from_dict(data["view"])
        return state

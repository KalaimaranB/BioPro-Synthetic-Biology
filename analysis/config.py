"""Configuration defaults for the Synthetic Biology plugin.

Centralizes user-configurable parameters such as simulation timestep,
default part libraries, and rendering preferences.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SimulationConfig:
    """Parameters governing the ODE kinetic simulation engine."""

    timestep: float = 0.1
    max_time: float = 100.0
    solver: str = "odeint"  # 'odeint' or 'tellurium'
    show_basal_leakiness: bool = True

    def to_dict(self) -> dict:
        return {
            "timestep": self.timestep,
            "max_time": self.max_time,
            "solver": self.solver,
            "show_basal_leakiness": self.show_basal_leakiness,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SimulationConfig:
        return cls(
            timestep=data.get("timestep", 0.1),
            max_time=data.get("max_time", 100.0),
            solver=data.get("solver", "odeint"),
            show_basal_leakiness=data.get("show_basal_leakiness", True),
        )


@dataclass
class SynBioConfig:
    """Top-level configuration for the Synthetic Biology workspace."""

    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    default_part_library: str = "igem"  # 'igem' or 'synbiohub'
    auto_orthogonality_check: bool = True

    def to_dict(self) -> dict:
        return {
            "simulation": self.simulation.to_dict(),
            "default_part_library": self.default_part_library,
            "auto_orthogonality_check": self.auto_orthogonality_check,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SynBioConfig:
        config = cls()
        if "simulation" in data:
            config.simulation = SimulationConfig.from_dict(data["simulation"])
        config.default_part_library = data.get("default_part_library", "igem")
        config.auto_orthogonality_check = data.get("auto_orthogonality_check", True)
        return config

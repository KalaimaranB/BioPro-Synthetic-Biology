"""Vector assembly, sequence parsing, and bench protocol engine module."""

from .protocol_engine import (
    AssemblyProtocolError,
    BenchProtocol,
    FragmentPipettingSpec,
    MasterMixResult,
    PipettingVolumeError,
    ProtocolEngine,
    ReactionRatioResult,
    ThermalCyclerStep,
)
from .vector_builder import VectorAssemblyEngine

try:
    from .async_worker import AssemblyWorker
except ImportError:
    AssemblyWorker = None  # PyQt6 not available in head-less / test environment

__all__ = [
    "VectorAssemblyEngine",
    "AssemblyWorker",
    "ProtocolEngine",
    "PipettingVolumeError",
    "AssemblyProtocolError",
    "MasterMixResult",
    "ReactionRatioResult",
    "FragmentPipettingSpec",
    "ThermalCyclerStep",
    "BenchProtocol",
]

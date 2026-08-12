"""Domain data models for Synthetic Biology Design Phase (Phase 1).

Includes strictly typed dataclasses for Plasmid assembly, CRISPR guide RNA,
and kinetic circuit simulation parameters/results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class GeneticFeature:
    """Represents a discrete annotated feature within a DNA construct
    (e.g. Promoter, CDS).
    """

    id: str
    name: str
    feature_type: (
        str  # e.g., 'promoter', 'cds', 'terminator', 'rbs', 'origin', 'resistance'
    )
    start: int  # 0-indexed start position
    end: int  # 0-indexed end position (exclusive)
    strand: int = 1  # 1 for forward strand, -1 for reverse strand
    sequence: str = ""
    color: str = "#3B82F6"  # Visual accent hex code
    qualifiers: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "feature_type": self.feature_type,
            "start": self.start,
            "end": self.end,
            "strand": self.strand,
            "sequence": self.sequence,
            "color": self.color,
            "qualifiers": self.qualifiers,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GeneticFeature:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            feature_type=data.get("feature_type", "misc_feature"),
            start=data.get("start", 0),
            end=data.get("end", 0),
            strand=data.get("strand", 1),
            sequence=data.get("sequence", ""),
            color=data.get("color", "#3B82F6"),
            qualifiers=data.get("qualifiers", {}),
        )


@dataclass
class Primer:
    """Represents a synthetic oligonucleotide primer for PCR amplification
    or assembly.
    """

    id: str
    name: str
    sequence: str
    direction: str  # 'FWD' or 'REV'
    target_tm: float
    calculated_tm: float
    gc_content: float
    length: int
    overhang: str = ""
    target_region: Optional[Tuple[int, int]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "sequence": self.sequence,
            "direction": self.direction,
            "target_tm": self.target_tm,
            "calculated_tm": self.calculated_tm,
            "gc_content": self.gc_content,
            "length": self.length,
            "overhang": self.overhang,
            "target_region": self.target_region,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Primer:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            sequence=data.get("sequence", ""),
            direction=data.get("direction", "FWD"),
            target_tm=data.get("target_tm", 60.0),
            calculated_tm=data.get("calculated_tm", 60.0),
            gc_content=data.get("gc_content", 50.0),
            length=data.get("length", len(data.get("sequence", ""))),
            overhang=data.get("overhang", ""),
            target_region=tuple(data["target_region"])
            if data.get("target_region")
            else None,
        )


@dataclass
class PlasmidVector:
    """Represents a complete circular or linear DNA vector construct."""

    id: str
    name: str
    description: str = ""
    sequence: str = ""
    is_circular: bool = True
    features: List[GeneticFeature] = field(default_factory=list)
    primers: List[Primer] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.sequence)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sequence": self.sequence,
            "is_circular": self.is_circular,
            "length": self.length,
            "features": [f.to_dict() for f in self.features],
            "primers": [p.to_dict() for p in self.primers],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlasmidVector:
        features = [GeneticFeature.from_dict(f) for f in data.get("features", [])]
        primers = [Primer.from_dict(p) for p in data.get("primers", [])]
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            sequence=data.get("sequence", ""),
            is_circular=data.get("is_circular", True),
            features=features,
            primers=primers,
        )


@dataclass
class gRNACandidate:
    """Represents a single guide RNA candidate targeting a CRISPR/Cas9 site."""

    id: str
    target_id: str
    protospacer: str  # 20bp guide sequence
    pam: str  # e.g., 'NGG'
    strand: int  # 1 or -1
    start: int
    end: int
    gc_content: float
    efficiency_score: float  # Doench/Rule 2 efficiency (0-100%)
    off_target_score: float  # CFD score (0-100%, 100 = minimal off-target activity)
    off_target_hits: List[Dict[str, Any]] = field(default_factory=list)
    has_poly_t_term: bool = False  # True if sequence contains >3 consecutive Ts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "target_id": self.target_id,
            "protospacer": self.protospacer,
            "pam": self.pam,
            "strand": self.strand,
            "start": self.start,
            "end": self.end,
            "gc_content": self.gc_content,
            "efficiency_score": self.efficiency_score,
            "off_target_score": self.off_target_score,
            "off_target_hits": self.off_target_hits,
            "has_poly_t_term": self.has_poly_t_term,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> gRNACandidate:
        return cls(
            id=data.get("id", ""),
            target_id=data.get("target_id", ""),
            protospacer=data.get("protospacer", ""),
            pam=data.get("pam", "NGG"),
            strand=data.get("strand", 1),
            start=data.get("start", 0),
            end=data.get("end", 0),
            gc_content=data.get("gc_content", 50.0),
            efficiency_score=data.get("efficiency_score", 0.0),
            off_target_score=data.get("off_target_score", 100.0),
            off_target_hits=data.get("off_target_hits", []),
            has_poly_t_term=data.get("has_poly_t_term", False),
        )


@dataclass
class CircuitComponent:
    """Represents a node in a genetic logic circuit topology."""

    id: str
    name: str
    component_type: str  # 'promoter', 'cds', 'inducer', 'repressor', 'reporter'
    y_min: float = 0.001  # Basal leakiness (RPU)
    y_max: float = 5.0  # Max expression level (RPU)
    K_d: float = 1.0  # Dissociation constant / threshold
    n: float = 2.0  # Hill coefficient
    degradation_rate: float = 0.1  # Protein/RNA degradation rate (1/min)
    translation_rate: float = 1.0  # Protein translation rate (RPU/min)
    initial_concentration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "component_type": self.component_type,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "K_d": self.K_d,
            "n": self.n,
            "degradation_rate": self.degradation_rate,
            "translation_rate": self.translation_rate,
            "initial_concentration": self.initial_concentration,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CircuitComponent:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            component_type=data.get("component_type", "cds"),
            y_min=data.get("y_min", 0.001),
            y_max=data.get("y_max", 5.0),
            K_d=data.get("K_d", 1.0),
            n=data.get("n", 2.0),
            degradation_rate=data.get("degradation_rate", 0.1),
            translation_rate=data.get("translation_rate", 1.0),
            initial_concentration=data.get("initial_concentration", 0.0),
        )


@dataclass
class CircuitEdge:
    """Represents a regulatory connection (activation or repression)
    between two nodes.
    """

    source_id: str
    target_id: str
    interaction_type: str  # 'activation' or 'repression'
    strength: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "interaction_type": self.interaction_type,
            "strength": self.strength,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CircuitEdge:
        return cls(
            source_id=data.get("source_id", ""),
            target_id=data.get("target_id", ""),
            interaction_type=data.get("interaction_type", "repression"),
            strength=data.get("strength", 1.0),
        )


@dataclass
class SimulationParameters:
    """Configuration parameters for ODE numerical solver."""

    t_start: float = 0.0
    t_end: float = 100.0
    num_points: int = 500
    solver_method: str = "RK45"  # 'RK45', 'Radau', 'BDF', 'LSODA'
    rtol: float = 1e-6
    atol: float = 1e-9

    def to_dict(self) -> Dict[str, Any]:
        return {
            "t_start": self.t_start,
            "t_end": self.t_end,
            "num_points": self.num_points,
            "solver_method": self.solver_method,
            "rtol": self.rtol,
            "atol": self.atol,
        }


@dataclass
class SimulationResult:
    """Results container holding time-series expression data from SciPy solve_ivp."""

    time_points: List[float] = field(default_factory=list)
    species_concentrations: Dict[str, List[float]] = field(default_factory=dict)
    status_message: str = "Success"
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_points": self.time_points,
            "species_concentrations": self.species_concentrations,
            "status_message": self.status_message,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SimulationResult:
        return cls(
            time_points=data.get("time_points", []),
            species_concentrations=data.get("species_concentrations", {}),
            status_message=data.get("status_message", "Success"),
            success=data.get("success", True),
        )

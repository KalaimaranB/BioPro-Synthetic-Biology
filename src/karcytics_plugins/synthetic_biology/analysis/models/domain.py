"""Domain data models for Synthetic Biology Design Phase (Phase 1).

Includes strictly typed dataclasses for Plasmid assembly, CRISPR guide RNA,
and kinetic circuit simulation parameters/results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..units import OUTPUT_UNIT


@dataclass
class GeneticFeature:
    """Represents a discrete annotated feature within a DNA construct
    (e.g. Promoter, CDS).
    """

    id: str
    name: str
    feature_type: str  # e.g., 'promoter', 'cds', 'terminator', 'rbs', 'origin', 'resistance'
    start: int  # 0-indexed start position
    end: int  # 0-indexed end position (exclusive)
    strand: int = 1  # 1 for forward strand, -1 for reverse strand
    sequence: str = ""
    color: str = "#3B82F6"  # Visual accent hex code
    qualifiers: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> GeneticFeature:
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
    #: GC % of the **annealing region** only. A 5' restriction tail is excluded,
    #: because it does not anneal on the first cycle and including it skews the
    #: figure the rubric judges. Tail composition is `overhang_gc_content`.
    gc_content: float
    length: int
    overhang: str = ""
    target_region: tuple[int, int] | None = None

    # ── Screening results (populated by analysis.assembly.primer_screen) ──
    #: GC % of the 5' tail alone, or None when there is no tail. Reported
    #: beside `gc_content`, never folded into it.
    overhang_gc_content: float | None = None
    #: Length of the annealing region, i.e. `length` minus the tail.
    annealing_length: int = 0
    #: Most stable hairpin / self-dimer ΔG°37, kcal/mol. None when not screened.
    hairpin_dg: float | None = None
    self_dimer_dg: float | None = None
    #: Serialised `RubricCheck`s. Stored as plain dicts so persistence stays
    #: JSON-safe and does not import the screening layer.
    rubric_checks: list[dict[str, Any]] = field(default_factory=list)
    #: "pass" / "fail" / "incomplete", or "" when the primer was never screened.
    rubric_verdict: str = ""
    #: Which rubric judged it, so a saved workspace records the standard applied.
    rubric_name: str = ""

    def to_dict(self) -> dict[str, Any]:
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
            "overhang_gc_content": self.overhang_gc_content,
            "annealing_length": self.annealing_length,
            "hairpin_dg": self.hairpin_dg,
            "self_dimer_dg": self.self_dimer_dg,
            "rubric_checks": [dict(c) for c in self.rubric_checks],
            "rubric_verdict": self.rubric_verdict,
            "rubric_name": self.rubric_name,
        }

    @property
    def tm(self) -> float:
        """Alias for calculated_tm for backward compatibility."""
        return self.calculated_tm

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Primer:
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
            target_region=tuple(data["target_region"]) if data.get("target_region") else None,
            # Screening fields default to "not screened" so a workspace saved
            # before they existed still loads, rather than reading as a pass.
            overhang_gc_content=data.get("overhang_gc_content"),
            annealing_length=data.get(
                "annealing_length",
                len(data.get("sequence", "")) - len(data.get("overhang", "")),
            ),
            hairpin_dg=data.get("hairpin_dg"),
            self_dimer_dg=data.get("self_dimer_dg"),
            rubric_checks=list(data.get("rubric_checks") or []),
            rubric_verdict=data.get("rubric_verdict", ""),
            rubric_name=data.get("rubric_name", ""),
        )


@dataclass
class PlasmidVector:
    """Represents a complete circular or linear DNA vector construct."""

    id: str
    name: str
    description: str = ""
    sequence: str = ""
    is_circular: bool = True
    features: list[GeneticFeature] = field(default_factory=list)
    primers: list[Primer] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.sequence)

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> PlasmidVector:
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
class gRNACandidate:  # noqa: N801 — standard molecular-biology nomenclature (guide RNA)
    """Represents a single guide RNA candidate targeting a CRISPR/Cas9 site."""

    id: str
    target_id: str
    protospacer: str  # 20bp guide sequence
    pam: str  # e.g., 'NGG'
    strand: int  # 1 or -1
    start: int
    end: int
    gc_content: float
    efficiency_score: float  # Rule-based heuristic score (0-100%); not Doench 2016
    off_target_score: float  # Heuristic off-target score (0-100%, 100 = fewest hits); not CFD
    off_target_hits: list[dict[str, Any]] = field(default_factory=list)
    has_poly_t_term: bool = False  # True if sequence contains >3 consecutive Ts

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> gRNACandidate:
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
    # Where the gene comes from, e.g. 'E. coli lac operon', 'phage lambda',
    # 'Tn10'. Shown beside the protein name on plots so a trace says which
    # organism the part was taken from, not just what it expresses.
    source_organism: str = ""

    @property
    def display_label(self) -> str:
        """How this node is named on a plot legend or species filter.

        Both simulators label their traces with this, so the same design reads
        the same way in every tab.
        """
        if self.source_organism:
            return f"{self.name} ({self.source_organism})"
        return self.name

    def to_dict(self) -> dict[str, Any]:
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
            "source_organism": self.source_organism,
        }

    @classmethod
    def from_dict(cls, data: Any) -> CircuitComponent:
        if isinstance(data, CircuitComponent):
            return data
        if not isinstance(data, dict):
            return cls(id="", name="", component_type="cds")
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
            source_organism=data.get("source_organism", ""),
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
    K_d: float | None = None  # Regulatory edge dissociation constant
    n: float | None = None  # Regulatory edge Hill coefficient

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "interaction_type": self.interaction_type,
            "strength": self.strength,
            "K_d": self.K_d,
            "n": self.n,
        }

    @classmethod
    def from_dict(cls, data: Any) -> CircuitEdge:
        if isinstance(data, CircuitEdge):
            return data
        if not isinstance(data, dict):
            return cls(source_id="", target_id="", interaction_type="repression")
        return cls(
            source_id=data.get("source_id", ""),
            target_id=data.get("target_id", ""),
            interaction_type=data.get("interaction_type", "repression"),
            strength=data.get("strength", 1.0),
            K_d=data.get("K_d"),
            n=data.get("n"),
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

    def to_dict(self) -> dict[str, Any]:
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

    time_points: list[float] = field(default_factory=list)
    species_concentrations: dict[str, list[float]] = field(default_factory=dict)
    status_message: str = "Success"
    success: bool = True
    #: The unit the concentrations are in. Travels with the result so a view
    #: labels its axis from what it was handed rather than from a constant it
    #: hopes still applies -- which is how four axes came to read RPU while
    #: the engine was returning RPU x min.
    unit: str = OUTPUT_UNIT

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_points": self.time_points,
            "species_concentrations": self.species_concentrations,
            "status_message": self.status_message,
            "success": self.success,
            "unit": self.unit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SimulationResult:
        return cls(
            time_points=data.get("time_points", []),
            species_concentrations=data.get("species_concentrations", {}),
            status_message=data.get("status_message", "Success"),
            success=data.get("success", True),
            # Default rather than "" so a payload from an older build is read
            # as RPU instead of as a trace with no unit at all.
            unit=data.get("unit", OUTPUT_UNIT),
        )

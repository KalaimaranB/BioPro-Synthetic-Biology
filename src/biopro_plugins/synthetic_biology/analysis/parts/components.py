"""Concrete biological part implementations (Promoter, CDS, Terminator, RBS)."""

from dataclasses import dataclass, field
from typing import Optional

from .base import BiologicalPart


@dataclass
class Promoter(BiologicalPart):
    """A promoter sequence that initiates transcription."""

    y_min: Optional[float] = None  # Leakiness (RPU)
    y_max: Optional[float] = None  # Max output (RPU)
    K_d: Optional[float] = None  # Activation/Repression threshold
    n: Optional[float] = None  # Hill coefficient (steepness)
    repressors: list[str] = field(
        default_factory=list
    )  # Molecules that repress this promoter
    activators: list[str] = field(
        default_factory=list
    )  # Molecules that activate this promoter

    @property
    def part_type(self) -> str:
        return "promoter"

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(
            {
                "y_min": self.y_min,
                "y_max": self.y_max,
                "K_d": self.K_d,
                "n": self.n,
                "repressors": self.repressors,
                "activators": self.activators,
            }
        )
        return data


@dataclass
class CDS(BiologicalPart):
    """Coding Sequence (Gene/Reporter) that is translated into a protein."""

    translation_rate: Optional[float] = None  # Translation rate (au/time)
    degradation_rate: Optional[float] = None  # Protein degradation rate
    product: str = ""  # The specific protein molecule produced (e.g., 'TetR', 'GFP')

    @property
    def part_type(self) -> str:
        return "cds"

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(
            {
                "translation_rate": self.translation_rate,
                "degradation_rate": self.degradation_rate,
                "product": self.product,
            }
        )
        return data


@dataclass
class Terminator(BiologicalPart):
    """A terminator sequence that stops transcription."""

    termination_efficiency: Optional[float] = None  # Efficiency (0-1)

    @property
    def part_type(self) -> str:
        return "terminator"

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["termination_efficiency"] = self.termination_efficiency
        return data


@dataclass
class RBS(BiologicalPart):
    """Ribosome Binding Site that initiates translation."""

    translation_initiation_rate: Optional[float] = None  # Translation efficiency

    @property
    def part_type(self) -> str:
        return "rbs"

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["translation_initiation_rate"] = self.translation_initiation_rate
        return data


@dataclass
class Insulator(BiologicalPart):
    """An insulator sequence (e.g., Ribozyme) that decouples transcription from translation."""

    cleavage_efficiency: Optional[float] = None

    @property
    def part_type(self) -> str:
        return "insulator"

    def to_dict(self) -> dict:
        data = super().to_dict()
        data["cleavage_efficiency"] = self.cleavage_efficiency
        return data


@dataclass
class sgRNA(BiologicalPart):
    """A single guide RNA sequence used for CRISPR-based logic gates."""

    transcription_rate: Optional[float] = None
    degradation_rate: Optional[float] = None
    target_promoter: str = ""

    @property
    def part_type(self) -> str:
        return "sgrna"

    def to_dict(self) -> dict:
        data = super().to_dict()
        data.update(
            {
                "transcription_rate": self.transcription_rate,
                "degradation_rate": self.degradation_rate,
                "target_promoter": self.target_promoter,
            }
        )
        return data

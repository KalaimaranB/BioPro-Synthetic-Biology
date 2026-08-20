"""Base class for all biological parts."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BiologicalPart(ABC):
    """Abstract base class representing a standard biological part."""

    id: str
    name: str
    description: str = ""
    sequence: str = ""
    is_custom: bool = True
    properties: dict[str, Any] = field(default_factory=dict)

    @property
    @abstractmethod
    def part_type(self) -> str:
        """String identifier for the part type (e.g., 'promoter', 'cds')."""
        pass

    def to_dict(self) -> dict:
        """Serialize part to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sequence": self.sequence,
            "is_custom": self.is_custom,
            "part_type": self.part_type,
            "properties": self.properties,
        }

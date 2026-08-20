import json
import os
from pathlib import Path
from typing import List, Optional, Protocol

from ..parts.base import BiologicalPart
from ..parts.components import CDS, RBS, Insulator, Promoter, Terminator, sgRNA


class PartRepository(Protocol):
    """Protocol defining the interface for a parts catalogue repository.

    Adheres to the Dependency Inversion Principle (DIP) and
    Interface Segregation Principle (ISP).
    """

    def save(self, part: BiologicalPart) -> None:
        """Save or update a part."""
        ...

    def get(self, part_id: str) -> BiologicalPart | None:
        """Retrieve a part by its ID."""
        ...

    def get_all(self) -> list[BiologicalPart]:
        """Retrieve all parts in the repository."""
        ...

    def delete(self, part_id: str) -> None:
        """Delete a part by its ID."""
        ...


class JsonPartRepository:
    """A JSON-file backed implementation of PartRepository.

    Adheres to the Single Responsibility Principle (SRP) by solely
    managing serialization and persistence of parts.
    """

    def __init__(self, file_path: str | Path | None = None):
        if file_path is None:
            plugin_dir = Path(__file__).resolve().parents[2]
            file_path = plugin_dir / "catalogue.json"
        else:
            file_path = Path(file_path)
            if not file_path.is_absolute():
                plugin_dir = Path(__file__).resolve().parents[2]
                file_path = plugin_dir / file_path

        self.file_path = str(file_path)
        self._cache: dict[str, BiologicalPart] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            self._cache = {}
            return

        try:
            with open(self.file_path, encoding="utf-8") as f:
                data = json.load(f)

            self._cache = {}
            for part_dict in data:
                part = self._deserialize_part(part_dict)
                if part:
                    self._cache[part.id] = part
        except Exception:
            self._cache = {}

    def _save_to_disk(self) -> None:
        data = [part.to_dict() for part in self._cache.values()]
        # ensure dir exists
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _deserialize_part(self, data: dict) -> BiologicalPart | None:  # noqa: PLR0911
        part_type = data.pop("part_type", "").lower()
        if part_type == "promoter":
            return Promoter(**data)
        if part_type == "cds":
            return CDS(**data)
        if part_type == "terminator":
            return Terminator(**data)
        if part_type == "rbs":
            return RBS(**data)
        if part_type == "insulator":
            return Insulator(**data)
        if part_type == "sgrna":
            return sgRNA(**data)
        return None

    def save(self, part: BiologicalPart) -> None:
        self._cache[part.id] = part
        self._save_to_disk()

    def get(self, part_id: str) -> BiologicalPart | None:
        return self._cache.get(part_id)

    def get_all(self) -> list[BiologicalPart]:
        return list(self._cache.values())

    def delete(self, part_id: str) -> None:
        if part_id in self._cache:
            del self._cache[part_id]
            self._save_to_disk()

"""Inventory and Oligo Tracking backend data models for LIMS (Phase 2).

Provides strictly typed, production-ready dataclasses for reagents, purchase-ready
oligonucleotides (parsed from Phase 1 thermodynamic primer outputs), hierarchical
storage location barcoding, and UUID-based barcode generation for synthesized plasmids.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def generate_plasmid_barcode(prefix: str = "PLSM") -> str:
    """Generates a unique, UUIDv4-based barcode identifier for newly synthesized
    plasmids.

    Args:
        prefix: Standardized prefix code for the barcode (default: 'PLSM').

    Returns:
        A formatted barcode string, e.g., 'PLSM-8F2A9C1D-3E4F'.
    """
    raw_uuid = uuid.uuid4().hex.upper()
    return f"{prefix}-{raw_uuid[:8]}-{raw_uuid[8:12]}"


@dataclass
class StorageLocation:
    """Represents a physical storage location using a hierarchical barcoding
    architecture.

    Hierarchy: Freezer -> Rack -> Box -> Well.

    Example canonical barcode:
        FZ:Freezer-01/RK:Rack-A/BX:Box-10/WL:A01
    """

    freezer: str
    rack: str
    box: str
    well: str

    def __post_init__(self) -> None:
        """Validates hierarchy components upon instantiation."""
        if not self.freezer.strip():
            raise ValueError("Freezer identifier cannot be empty.")
        if not self.rack.strip():
            raise ValueError("Rack identifier cannot be empty.")
        if not self.box.strip():
            raise ValueError("Box identifier cannot be empty.")
        if not self.well.strip():
            raise ValueError("Well identifier cannot be empty.")

    @property
    def barcode(self) -> str:
        """Returns the canonical hierarchical barcode string representation."""
        return (
            f"FZ:{self.freezer.strip()}/"
            f"RK:{self.rack.strip()}/"
            f"BX:{self.box.strip()}/"
            f"WL:{self.well.strip().upper()}"
        )

    @classmethod
    def from_barcode(cls, barcode_str: str) -> StorageLocation:
        """Parses a canonical hierarchical barcode string back into a StorageLocation
        instance.

        Args:
            barcode_str: A string formatted as 'FZ:.../RK:.../BX:.../WL:...'.

        Returns:
            A new StorageLocation instance.

        Raises:
            ValueError: If the barcode string format is invalid.
        """
        pattern = (
            r"^FZ:(?P<freezer>[^/]+)/RK:(?P<rack>[^/]+)/"
            r"BX:(?P<box>[^/]+)/WL:(?P<well>[^/]+)$"
        )
        match = re.match(pattern, barcode_str.strip())
        if not match:
            raise ValueError(
                f"Invalid StorageLocation barcode format: '{barcode_str}'. "
                "Expected format: 'FZ:<freezer>/RK:<rack>/BX:<box>/WL:<well>'"
            )
        gd = match.groupdict()
        return cls(
            freezer=gd["freezer"],
            rack=gd["rack"],
            box=gd["box"],
            well=gd["well"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the StorageLocation into a dictionary payload."""
        return {
            "freezer": self.freezer,
            "rack": self.rack,
            "box": self.box,
            "well": self.well,
            "barcode": self.barcode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StorageLocation:
        """Deserializes a dictionary payload into a StorageLocation instance."""
        return cls(
            freezer=str(data.get("freezer", "")),
            rack=str(data.get("rack", "")),
            box=str(data.get("box", "")),
            well=str(data.get("well", "")),
        )


@dataclass
class Reagent:
    """Tracks laboratory inventory reagents including lot numbers, concentration,
    and storage volume.
    """

    id: str
    name: str
    lot_number: str
    concentration: float
    volume_ul: float
    concentration_unit: str = "uM"
    storage_location: StorageLocation | None = None
    barcode: str | None = None
    expiration_date: str | None = None
    supplier: str | None = None
    catalog_number: str | None = None

    def __post_init__(self) -> None:
        """Validates reagent numerical properties and assigns barcode if absent."""
        if self.concentration < 0:
            raise ValueError(
                f"Reagent concentration cannot be negative (got {self.concentration})."
            )
        if self.volume_ul < 0:
            raise ValueError(f"Reagent volume_ul cannot be negative (got {self.volume_ul}).")
        if not self.barcode and self.storage_location:
            self.barcode = f"RGT-{self.id}-{self.storage_location.well.upper()}"

    def to_dict(self) -> dict[str, Any]:
        """Serializes the Reagent model to a dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "lot_number": self.lot_number,
            "concentration": self.concentration,
            "concentration_unit": self.concentration_unit,
            "volume_ul": self.volume_ul,
            "storage_location": (
                self.storage_location.to_dict() if self.storage_location else None
            ),
            "barcode": self.barcode,
            "expiration_date": self.expiration_date,
            "supplier": self.supplier,
            "catalog_number": self.catalog_number,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Reagent:
        """Deserializes dictionary data into a Reagent model instance."""
        storage_loc = None
        if data.get("storage_location"):
            storage_loc = StorageLocation.from_dict(data["storage_location"])
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            lot_number=str(data.get("lot_number", "")),
            concentration=float(data.get("concentration") or 0.0),
            volume_ul=float(data.get("volume_ul") or 0.0),
            concentration_unit=str(data.get("concentration_unit", "uM")),
            storage_location=storage_loc,
            barcode=data.get("barcode"),
            expiration_date=data.get("expiration_date"),
            supplier=data.get("supplier"),
            catalog_number=data.get("catalog_number"),
        )


@dataclass
class Oligo:
    """Represents a purchase-ready oligonucleotide primer with thermodynamic
    annotations, plate location metadata, and vendor ordering options.
    """

    id: str
    name: str
    sequence: str
    tm: float
    gc_content: float
    plate_id: str
    well_position: str
    scale: str = "25nm"
    purification: str = "Standard Desalt"
    modifications_5prime: str = ""
    modifications_3prime: str = ""
    storage_location: StorageLocation | None = None
    barcode: str | None = None

    def __post_init__(self) -> None:
        """Normalizes and validates oligonucleotide sequence data."""
        self.sequence = self.sequence.strip().upper()
        if not self.sequence:
            raise ValueError("Oligonucleotide sequence cannot be empty.")
        if not self.barcode and self.plate_id and self.well_position:
            self.barcode = f"OLG-{self.plate_id}-{self.well_position.upper()}"

    @property
    def length(self) -> int:
        """Returns the nucleotide length of the oligonucleotide sequence."""
        return len(self.sequence)

    @classmethod
    def from_phase1_primer(  # noqa: PLR0913, PLR0917
        cls,
        primer: Any,
        plate_id: str = "PLATE-01",
        well_position: str = "A01",
        scale: str = "25nm",
        purification: str = "Standard Desalt",
        modifications_5prime: str = "",
        modifications_3prime: str = "",
        storage_location: StorageLocation | None = None,
    ) -> Oligo:
        """Parses thermodynamic primer outputs from Phase 1 into a purchase-ready
        Oligo instance.

        Args:
            primer: A Phase 1 `Primer` dataclass instance or dict containing
                primer output fields (`id`, `name`, `sequence`, `calculated_tm`,
                `gc_content`, `overhang`).
            plate_id: Destination plate barcode/identifier.
            well_position: Well position on plate (e.g., 'A01').
            scale: Vendor synthesis scale (e.g., '25nm', '100nm').
            purification: Purification grade (e.g., 'Standard Desalt', 'HPLC').
            modifications_5prime: Optional 5' end modification.
            modifications_3prime: Optional 3' end modification.
            storage_location: Optional StorageLocation metadata object.

        Returns:
            A purchase-ready Oligo data model instance.
        """
        if isinstance(primer, dict):
            p_id = str(primer.get("id", f"OLG-{uuid.uuid4().hex[:6].upper()}"))
            p_name = str(primer.get("name", "Unnamed_Primer"))
            seq = str(primer.get("sequence", ""))
            overhang = str(primer.get("overhang", ""))
            tm = float(primer.get("calculated_tm") or primer.get("target_tm") or 60.0)
            gc = float(primer.get("gc_content") or 50.0)
        else:
            p_id = getattr(primer, "id", f"OLG-{uuid.uuid4().hex[:6].upper()}")
            p_name = getattr(primer, "name", "Unnamed_Primer")
            seq = getattr(primer, "sequence", "")
            overhang = getattr(primer, "overhang", "")
            tm = float(
                getattr(
                    primer,
                    "calculated_tm",
                    getattr(primer, "target_tm", 60.0),
                )
            )
            gc = float(getattr(primer, "gc_content", None) or 50.0)

        full_sequence = f"{overhang}{seq}".strip().upper()

        return cls(
            id=p_id,
            name=p_name,
            sequence=full_sequence,
            tm=round(tm, 2),
            gc_content=round(gc, 2),
            plate_id=plate_id,
            well_position=well_position,
            scale=scale,
            purification=purification,
            modifications_5prime=modifications_5prime,
            modifications_3prime=modifications_3prime,
            storage_location=storage_location,
        )

    def to_vendor_order_format(self) -> dict[str, str]:
        """Formats oligonucleotide specifications into standard vendor ordering
        parameters (e.g., IDT, Eurofins bulk upload format).
        """
        return {
            "Name": self.name,
            "Sequence": self.sequence,
            "Scale": self.scale,
            "Purification": self.purification,
            "5' Modification": self.modifications_5prime or "None",
            "3' Modification": self.modifications_3prime or "None",
            "Plate ID": self.plate_id,
            "Well": self.well_position,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serializes the Oligo model instance into a dictionary payload."""
        return {
            "id": self.id,
            "name": self.name,
            "sequence": self.sequence,
            "length": self.length,
            "tm": self.tm,
            "gc_content": self.gc_content,
            "plate_id": self.plate_id,
            "well_position": self.well_position,
            "scale": self.scale,
            "purification": self.purification,
            "modifications_5prime": self.modifications_5prime,
            "modifications_3prime": self.modifications_3prime,
            "storage_location": (
                self.storage_location.to_dict() if self.storage_location else None
            ),
            "barcode": self.barcode,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Oligo:
        """Deserializes a dictionary payload into an Oligo model instance."""
        storage_loc = None
        if data.get("storage_location"):
            storage_loc = StorageLocation.from_dict(data["storage_location"])
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            sequence=str(data.get("sequence", "")),
            tm=float(data.get("tm") or 0.0),
            gc_content=float(data.get("gc_content") or 0.0),
            plate_id=str(data.get("plate_id", "")),
            well_position=str(data.get("well_position", "")),
            scale=str(data.get("scale", "25nm")),
            purification=str(data.get("purification", "Standard Desalt")),
            modifications_5prime=str(data.get("modifications_5prime", "")),
            modifications_3prime=str(data.get("modifications_3prime", "")),
            storage_location=storage_loc,
            barcode=data.get("barcode"),
        )


@dataclass
class PlasmidInventoryItem:
    """Represents a physical synthesized plasmid item in LIMS inventory, equipped with
    a unique UUID-generated barcode and storage location metadata.
    """

    id: str
    name: str
    sequence: str
    vector_backbone: str
    lot_number: str
    barcode: str = field(default_factory=generate_plasmid_barcode)
    storage_location: StorageLocation | None = None
    concentration_ng_ul: float | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        """Ensures sequence is normalized and valid barcode is present."""
        self.sequence = self.sequence.strip().upper()
        if not self.barcode:
            self.barcode = generate_plasmid_barcode()

    def to_dict(self) -> dict[str, Any]:
        """Serializes the PlasmidInventoryItem into a dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "sequence": self.sequence,
            "vector_backbone": self.vector_backbone,
            "lot_number": self.lot_number,
            "barcode": self.barcode,
            "storage_location": (
                self.storage_location.to_dict() if self.storage_location else None
            ),
            "concentration_ng_ul": self.concentration_ng_ul,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlasmidInventoryItem:
        """Deserializes dictionary payload into a PlasmidInventoryItem instance."""
        storage_loc = None
        if data.get("storage_location"):
            storage_loc = StorageLocation.from_dict(data["storage_location"])
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            sequence=str(data.get("sequence", "")),
            vector_backbone=str(data.get("vector_backbone", "")),
            lot_number=str(data.get("lot_number", "")),
            barcode=str(data.get("barcode", generate_plasmid_barcode())),
            storage_location=storage_loc,
            concentration_ng_ul=(
                float(data["concentration_ng_ul"])
                if data.get("concentration_ng_ul") is not None
                else None
            ),
            created_at=str(data.get("created_at", datetime.now(UTC).isoformat())),
        )

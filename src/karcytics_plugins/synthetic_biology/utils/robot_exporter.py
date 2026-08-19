"""Robot Worklist Exporter for Liquid Handling Automation.

Translates computational DNA assembly designs and ProtocolEngine reaction
volume calculations into physical worklist instructions for automated
liquid handlers (e.g., Tecan, Hamilton, Echo).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple, Union


class RobotExportError(IOError):
    """Custom exception raised when exporting robotic worklist files fails due to
    file permissions, OS IO errors, or plate layout errors.
    """

    pass


@dataclass
class TransferInstruction:
    """Represents a single liquid handling transfer step."""

    source_plate: str
    source_well: str
    destination_plate: str
    destination_well: str
    volume_ul: float
    liquid_class: str = "Water_FreeSingle"

    def to_dict(self) -> Dict[str, str]:
        """Formats the transfer instruction for Tecan CSV row writing."""
        return {
            "Source_Plate": self.source_plate,
            "Source_Well": self.source_well,
            "Destination_Plate": self.destination_plate,
            "Destination_Well": self.destination_well,
            "Volume_uL": f"{self.volume_ul:.3f}",
            "Liquid_Class": self.liquid_class,
        }


class WorklistGenerator:
    """Translates assembly protocol calculations into liquid handling robot worklists.

    Supports Tecan GWL/CSV format with 96-well plate indexing and intelligent
    well mapping.
    """

    TECAN_COLUMNS: List[str] = [
        "Source_Plate",
        "Source_Well",
        "Destination_Plate",
        "Destination_Well",
        "Volume_uL",
        "Liquid_Class",
    ]

    @staticmethod
    def index_to_well(
        index: int,
        zero_padded: bool = False,
        order: str = "column_first",
        num_rows: int = 8,
        num_cols: int = 12,
    ) -> str:
        """Converts a 0-indexed integer position into 96-well plate coordinates
        (e.g., 0 -> A1, 1 -> B1).

        Args:
            index: 0-based well index (0 to 95 for standard 96-well plate).
            zero_padded: If True, pads single digit columns ('A01' vs 'A1').
            order: 'column_first' (A1, B1... H1, A2...) or 'row_first' (A1, A2...).
            num_rows: Number of plate rows (default 8 for A-H).
            num_cols: Number of plate columns (default 12 for 1-12).

        Returns:
            Well coordinate string, e.g. 'A1' or 'H12'.

        Raises:
            ValueError: If index is outside valid plate grid limits.
        """
        capacity = num_rows * num_cols
        plate_idx = index % capacity

        if order == "row_first":
            row_idx = plate_idx // num_cols
            col_num = (plate_idx % num_cols) + 1
        else:  # column_first (standard liquid handler column-by-column dispensing)
            row_idx = plate_idx % num_rows
            col_num = (plate_idx // num_rows) + 1

        if row_idx >= 26:
            raise ValueError(
                f"Plate row index {row_idx} exceeds alphabet limits (A-Z)."
            )

        row_letter = chr(ord("A") + row_idx)
        col_str = f"{col_num:02d}" if zero_padded else f"{col_num}"

        return f"{row_letter}{col_str}"

    @classmethod
    def export_transfers_to_tecan_csv(
        cls,
        transfers: List[TransferInstruction],
        filepath: Union[str, Path],
    ) -> Path:
        """Exports a list of TransferInstruction objects to a Tecan-compatible CSV file.

        Args:
            transfers: List of TransferInstruction instances.
            filepath: Target file path for the CSV output.

        Returns:
            Path object pointing to the written CSV file.

        Raises:
            RobotExportError: If file writing fails due to OS permission or IO errors.
        """
        out_path = Path(filepath)

        try:
            # Ensure parent directories exist
            out_path.parent.mkdir(parents=True, exist_ok=True)

            with out_path.open(mode="w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=cls.TECAN_COLUMNS)
                writer.writeheader()
                for transfer in transfers:
                    writer.writerow(transfer.to_dict())

            return out_path

        except (PermissionError, OSError, IOError) as e:
            raise RobotExportError(
                f"Failed to export Tecan CSV worklist to '{out_path}': {e}"
            ) from e

    @classmethod
    def export_to_tecan_csv(
        cls,
        reactions_list: Sequence[Union[Dict[str, Any], Any]],
        filepath: Union[str, Path],
        source_plate_map: Mapping[str, Union[str, Tuple[str, str]]] | None = None,
        default_dest_plate: str = "DEST_PLATE_1",
        default_liquid_class: str = "Water_FreeSingle",
        zero_padded_wells: bool = False,
    ) -> Path:
        """Translates a list of reaction specs (or ProtocolEngine outputs) into a
        Tecan CSV worklist. Auto-increments destination wells across standard 96-well
        plate format (A1, B1, C1... H1, A2...).

        Args:
            reactions_list: List of reaction specifications or ReactionRatioResult.
            filepath: Destination file path for Tecan CSV.
            source_plate_map: Optional dict mapping component names (e.g. 'Master_Mix')
                to (Source_Plate, Source_Well) tuples or string identifiers.
            default_dest_plate: Default destination plate barcode/name.
            default_liquid_class: Default liquid class for transfers.
            zero_padded_wells: If True, uses 'A01' format instead of 'A1'.

        Returns:
            Path to the written Tecan CSV file.

        Raises:
            RobotExportError: If export fails due to file permissions or invalid data.
        """
        transfers: List[TransferInstruction] = []
        plate_map = source_plate_map or {}

        for rxn_idx, rxn in enumerate(reactions_list):
            # Calculate destination well (A1, B1... auto-incrementing across grid)
            dest_well = cls.index_to_well(rxn_idx, zero_padded=zero_padded_wells)
            dest_plate_num = (rxn_idx // 96) + 1
            dest_plate = (
                default_dest_plate
                if dest_plate_num == 1
                else f"DEST_PLATE_{dest_plate_num}"
            )

            # Standardize input reaction structure
            if hasattr(rxn, "to_dict"):
                rxn_data = rxn.to_dict()
            elif isinstance(rxn, dict):
                rxn_data = rxn
            else:
                raise RobotExportError(
                    f"Reaction item at index {rxn_idx} must be a dict "
                    "or object with to_dict() method."
                )

            # 1. Master Mix Transfer
            mm_vol = rxn_data.get("master_mix_volume_ul", 0.0)
            if mm_vol > 0:
                src_p, src_w = cls._resolve_source(
                    "Master_Mix",
                    plate_map,
                    default_plate="REAGENT_PLATE_1",
                    default_well="A1",
                )
                transfers.append(
                    TransferInstruction(
                        source_plate=src_p,
                        source_well=src_w,
                        destination_plate=dest_plate,
                        destination_well=dest_well,
                        volume_ul=mm_vol,
                        liquid_class="MasterMix_Viscous"
                        if "MasterMix" not in default_liquid_class
                        else default_liquid_class,
                    )
                )

            # 2. Water Transfer
            water_vol = rxn_data.get("water_volume_ul", 0.0)
            if water_vol > 0:
                src_p, src_w = cls._resolve_source(
                    "Water",
                    plate_map,
                    default_plate="REAGENT_PLATE_1",
                    default_well="B1",
                )
                transfers.append(
                    TransferInstruction(
                        source_plate=src_p,
                        source_well=src_w,
                        destination_plate=dest_plate,
                        destination_well=dest_well,
                        volume_ul=water_vol,
                        liquid_class="Water_FreeSingle",
                    )
                )

            # 3. Vector DNA Transfer
            vector_spec = rxn_data.get("vector_spec")
            if isinstance(vector_spec, dict):
                v_name = vector_spec.get("name", "Vector")
                v_vol = vector_spec.get("volume_ul", 0.0)
                if v_vol > 0:
                    src_p, src_w = cls._resolve_source(
                        v_name,
                        plate_map,
                        default_plate="VECTOR_PLATE_1",
                        default_well="A1",
                    )
                    transfers.append(
                        TransferInstruction(
                            source_plate=src_p,
                            source_well=src_w,
                            destination_plate=dest_plate,
                            destination_well=dest_well,
                            volume_ul=v_vol,
                            liquid_class="DNA_LowVolume",
                        )
                    )

            # 4. Insert DNA Transfer(s)
            insert_specs = rxn_data.get("insert_specs", [])
            if isinstance(insert_specs, list):
                for ins_idx, ins_spec in enumerate(insert_specs):
                    if isinstance(ins_spec, dict):
                        ins_name = ins_spec.get("name", f"Insert_{ins_idx + 1}")
                        ins_vol = ins_spec.get("volume_ul", 0.0)
                        if ins_vol > 0:
                            default_w = cls.index_to_well(
                                ins_idx, zero_padded=zero_padded_wells
                            )
                            src_p, src_w = cls._resolve_source(
                                ins_name,
                                plate_map,
                                default_plate="INSERT_PLATE_1",
                                default_well=default_w,
                            )
                            transfers.append(
                                TransferInstruction(
                                    source_plate=src_p,
                                    source_well=src_w,
                                    destination_plate=dest_plate,
                                    destination_well=dest_well,
                                    volume_ul=ins_vol,
                                    liquid_class="DNA_LowVolume",
                                )
                            )

            # Generic components fallback (if raw transfer dicts provided)
            if not (mm_vol or water_vol or vector_spec or insert_specs):
                vol = rxn_data.get("volume_ul", 0.0)
                if vol > 0:
                    src_p = rxn_data.get("source_plate", "SOURCE_PLATE_1")
                    src_w = rxn_data.get("source_well", "A1")
                    l_class = rxn_data.get("liquid_class", default_liquid_class)
                    transfers.append(
                        TransferInstruction(
                            source_plate=src_p,
                            source_well=src_w,
                            destination_plate=dest_plate,
                            destination_well=dest_well,
                            volume_ul=vol,
                            liquid_class=l_class,
                        )
                    )

        return cls.export_transfers_to_tecan_csv(transfers, filepath)

    @staticmethod
    def _resolve_source(
        component_name: str,
        plate_map: Mapping[str, Union[str, Tuple[str, str]]],
        default_plate: str,
        default_well: str,
    ) -> Tuple[str, str]:
        """Resolves source plate and well for a given component name from plate map."""
        if component_name in plate_map:
            val = plate_map[component_name]
            if isinstance(val, (tuple, list)) and len(val) >= 2:
                return str(val[0]), str(val[1])
            elif isinstance(val, str):
                return default_plate, val

        return default_plate, default_well

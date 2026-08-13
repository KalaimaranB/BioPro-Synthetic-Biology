"""Unit tests for WorklistGenerator and Tecan CSV robot exporter."""

import csv
import tempfile
import unittest
from pathlib import Path

from biopro_plugins.synthetic_biology.analysis.assembly.protocol_engine import (
    ProtocolEngine,
)
from biopro_plugins.synthetic_biology.utils.robot_exporter import (
    RobotExportError,
    TransferInstruction,
    WorklistGenerator,
)


class TestRobotExporter(unittest.TestCase):
    def test_well_indexing_column_first(self):
        # 0 -> A1, 1 -> B1 ... 7 -> H1, 8 -> A2, 95 -> H12
        self.assertEqual(WorklistGenerator.index_to_well(0), "A1")
        self.assertEqual(WorklistGenerator.index_to_well(1), "B1")
        self.assertEqual(WorklistGenerator.index_to_well(7), "H1")
        self.assertEqual(WorklistGenerator.index_to_well(8), "A2")
        self.assertEqual(WorklistGenerator.index_to_well(95), "H12")

        # Zero padded
        self.assertEqual(WorklistGenerator.index_to_well(0, zero_padded=True), "A01")
        self.assertEqual(WorklistGenerator.index_to_well(8, zero_padded=True), "A02")

    def test_well_indexing_row_first(self):
        # 0 -> A1, 1 -> A2 ... 11 -> A12, 12 -> B1
        self.assertEqual(WorklistGenerator.index_to_well(0, order="row_first"), "A1")
        self.assertEqual(WorklistGenerator.index_to_well(1, order="row_first"), "A2")
        self.assertEqual(WorklistGenerator.index_to_well(11, order="row_first"), "A12")
        self.assertEqual(WorklistGenerator.index_to_well(12, order="row_first"), "B1")

    def test_export_transfers_to_tecan_csv(self):
        transfers = [
            TransferInstruction(
                source_plate="SRC_1",
                source_well="A1",
                destination_plate="DEST_1",
                destination_well="A1",
                volume_ul=10.0,
                liquid_class="MasterMix_Viscous",
            ),
            TransferInstruction(
                source_plate="SRC_2",
                source_well="B1",
                destination_plate="DEST_1",
                destination_well="A1",
                volume_ul=1.5,
                liquid_class="DNA_LowVolume",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "tecan_worklist.csv"
            result_path = WorklistGenerator.export_transfers_to_tecan_csv(
                transfers, csv_path
            )
            self.assertTrue(result_path.exists())

            # Read back CSV and verify exact columns and values
            with result_path.open(mode="r", encoding="utf-8") as f:
                reader = list(csv.DictReader(f))
                self.assertEqual(len(reader), 2)

                # Check columns
                self.assertEqual(
                    list(reader[0].keys()),
                    [
                        "Source_Plate",
                        "Source_Well",
                        "Destination_Plate",
                        "Destination_Well",
                        "Volume_uL",
                        "Liquid_Class",
                    ],
                )

                self.assertEqual(reader[0]["Source_Plate"], "SRC_1")
                self.assertEqual(reader[0]["Source_Well"], "A1")
                self.assertEqual(reader[0]["Destination_Plate"], "DEST_1")
                self.assertEqual(reader[0]["Destination_Well"], "A1")
                self.assertEqual(reader[0]["Volume_uL"], "10.000")
                self.assertEqual(reader[0]["Liquid_Class"], "MasterMix_Viscous")

    def test_export_to_tecan_csv_from_protocol_engine(self):
        engine = ProtocolEngine()
        inserts = [
            {
                "name": "Insert_GFP",
                "length_bp": 1000,
                "concentration_ng_ul": 30.0,
                "molar_ratio": 3.0,
            }
        ]
        ratio_result = engine.calculate_insert_to_vector_ratio(
            vector_bp=3000,
            vector_conc_ng_ul=50.0,
            inserts=inserts,
            vector_mass_ng=50.0,
            reaction_volume_ul=20.0,
            master_mix_volume_ul=10.0,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "protocol_tecan.csv"
            result_path = WorklistGenerator.export_to_tecan_csv(
                reactions_list=[ratio_result, ratio_result],
                filepath=csv_path,
            )

            self.assertTrue(result_path.exists())
            with result_path.open(mode="r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                # 2 reactions with MM, Water, Vector, Insert -> transfers generated
                self.assertGreater(len(rows), 0)

                # Rxn 0 goes to A1, Rxn 1 goes to B1
                dest_wells = {r["Destination_Well"] for r in rows}
                self.assertIn("A1", dest_wells)
                self.assertIn("B1", dest_wells)

    def test_export_file_permission_error(self):
        # Attempt to write to a non-existent root directory without creation permissions
        invalid_path = Path("/invalid_root_directory_12345/test.csv")
        with self.assertRaises(RobotExportError):
            WorklistGenerator.export_transfers_to_tecan_csv([], invalid_path)


if __name__ == "__main__":
    unittest.main()

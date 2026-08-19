"""Unit tests for Inventory & Oligo Tracking data models (Phase 2 LIMS)."""

import unittest

from karcytics_plugins.synthetic_biology.analysis.models.domain import Primer
from karcytics_plugins.synthetic_biology.models.inventory_models import (
    Oligo,
    PlasmidInventoryItem,
    Reagent,
    StorageLocation,
    generate_plasmid_barcode,
)


class TestInventoryModels(unittest.TestCase):
    def test_storage_location_barcode_generation(self):
        loc = StorageLocation(
            freezer="Freezer-80C",
            rack="Rack-01",
            box="Box-A",
            well="A01",
        )
        self.assertEqual(loc.barcode, "FZ:Freezer-80C/RK:Rack-01/BX:Box-A/WL:A01")

        # Test roundtrip from_barcode
        parsed = StorageLocation.from_barcode(loc.barcode)
        self.assertEqual(parsed.freezer, "Freezer-80C")
        self.assertEqual(parsed.rack, "Rack-01")
        self.assertEqual(parsed.box, "Box-A")
        self.assertEqual(parsed.well, "A01")

    def test_storage_location_invalid_barcode(self):
        with self.assertRaises(ValueError):
            StorageLocation.from_barcode("INVALID_BARCODE_STRING")

    def test_reagent_model(self):
        loc = StorageLocation("FZ1", "RK1", "BX1", "B02")
        reagent = Reagent(
            id="RGT-001",
            name="T4 DNA Ligase",
            lot_number="LOT-20260812",
            concentration=400.0,
            concentration_unit="U/uL",
            volume_ul=50.0,
            storage_location=loc,
            supplier="NEB",
            catalog_number="M0202S",
        )
        self.assertEqual(reagent.barcode, "RGT-RGT-001-B02")
        d = reagent.to_dict()
        reconstructed = Reagent.from_dict(d)
        self.assertEqual(reconstructed.name, "T4 DNA Ligase")
        self.assertEqual(reconstructed.storage_location.well, "B02")

    def test_oligo_parsing_from_phase1_primer(self):
        phase1_primer = Primer(
            id="PRM-101",
            name="pUC19_FWD",
            sequence="CGCCAGGGTTTTCCCAGTCACGAC",
            direction="FWD",
            target_tm=62.5,
            calculated_tm=63.1,
            gc_content=58.33,
            length=24,
            overhang="GAATTC",
        )

        loc = StorageLocation("FZ1", "RK1", "BX1", "C03")
        oligo = Oligo.from_phase1_primer(
            primer=phase1_primer,
            plate_id="PLATE-2026-01",
            well_position="C03",
            scale="100nm",
            purification="HPLC",
            storage_location=loc,
        )

        # Overhang 'GAATTC' + sequence 'CGCCAGGGTTTTCCCAGTCACGAC'
        self.assertEqual(oligo.sequence, "GAATTCCGCCAGGGTTTTCCCAGTCACGAC")
        self.assertEqual(oligo.length, 30)
        self.assertEqual(oligo.tm, 63.1)
        self.assertEqual(oligo.plate_id, "PLATE-2026-01")
        self.assertEqual(oligo.well_position, "C03")
        self.assertEqual(oligo.scale, "100nm")
        self.assertEqual(oligo.purification, "HPLC")

        vendor_fmt = oligo.to_vendor_order_format()
        self.assertEqual(vendor_fmt["Name"], "pUC19_FWD")
        self.assertEqual(vendor_fmt["Sequence"], "GAATTCCGCCAGGGTTTTCCCAGTCACGAC")
        self.assertEqual(vendor_fmt["Scale"], "100nm")

        # Test roundtrip dict
        d = oligo.to_dict()
        reconstructed = Oligo.from_dict(d)
        self.assertEqual(reconstructed.sequence, oligo.sequence)
        self.assertEqual(reconstructed.storage_location.barcode, loc.barcode)

    def test_oligo_parsing_from_dict(self):
        primer_dict = {
            "id": "PRM-102",
            "name": "pUC19_REV",
            "sequence": "AGCGGATAACAATTTCACACAGGA",
            "target_tm": 60.0,
            "calculated_tm": 60.5,
            "gc_content": 45.0,
            "overhang": "",
        }
        oligo = Oligo.from_phase1_primer(primer_dict, plate_id="P1", well_position="H12")
        self.assertEqual(oligo.name, "pUC19_REV")
        self.assertEqual(oligo.tm, 60.5)
        self.assertEqual(oligo.well_position, "H12")

    def test_plasmid_uuid_barcode_generation(self):
        barcode = generate_plasmid_barcode()
        self.assertTrue(barcode.startswith("PLSM-"))
        self.assertEqual(len(barcode), 18)  # PLSM-8HEX-4HEX

        loc = StorageLocation("FZ1", "RK1", "BX1", "A01")
        plasmid = PlasmidInventoryItem(
            id="PL-001",
            name="pET28a-GFP",
            sequence="ATGCGT...",
            vector_backbone="pET28a",
            lot_number="LOT-PL-99",
            storage_location=loc,
            concentration_ng_ul=250.0,
        )
        self.assertTrue(plasmid.barcode.startswith("PLSM-"))
        self.assertEqual(plasmid.storage_location.well, "A01")

        d = plasmid.to_dict()
        reconstructed = PlasmidInventoryItem.from_dict(d)
        self.assertEqual(reconstructed.name, "pET28a-GFP")
        self.assertEqual(reconstructed.barcode, plasmid.barcode)


if __name__ == "__main__":
    unittest.main()

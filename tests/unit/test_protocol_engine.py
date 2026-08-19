"""Unit tests for ProtocolEngine (Phase 2 Build Assembly Protocol Engine)."""

import unittest

from karcytics_plugins.synthetic_biology.analysis.assembly.protocol_engine import (
    AssemblyProtocolError,
    BenchProtocol,
    MasterMixResult,
    PipettingVolumeError,
    ProtocolEngine,
    ReactionRatioResult,
)


class TestProtocolEngine(unittest.TestCase):
    def setUp(self):
        self.engine = ProtocolEngine(min_pipetting_ul=0.5)

    def test_calculate_master_mix_gibson(self):
        # 5 reactions, 10% overage -> multiplier = 5.5
        result = self.engine.calculate_master_mix(
            num_reactions=5,
            overage_pct=10.0,
            assembly_type="Gibson",
            reaction_volume_ul=20.0,
        )
        self.assertIsInstance(result, MasterMixResult)
        self.assertEqual(result.assembly_type, "Gibson Assembly")
        self.assertEqual(result.num_reactions, 5)
        self.assertAlmostEqual(result.multiplier, 5.5)
        # Gibson default per rxn is 10.0 uL Master Mix -> total = 55.0 uL
        self.assertIn("Gibson Assembly 2X Master Mix", result.master_mix_volumes_total)
        self.assertAlmostEqual(
            result.master_mix_volumes_total["Gibson Assembly 2X Master Mix"], 55.0
        )
        d = result.to_dict()
        self.assertEqual(d["num_reactions"], 5)
        self.assertEqual(d["total_master_mix_volume_ul"], 55.0)

    def test_calculate_master_mix_golden_gate(self):
        result = self.engine.calculate_master_mix(
            num_reactions=10,
            overage_pct=15.0,
            assembly_type="GoldenGate",
            reaction_volume_ul=20.0,
        )
        self.assertEqual(result.assembly_type, "Golden Gate Assembly")
        self.assertAlmostEqual(result.multiplier, 11.5)
        # Buffer per rxn is 2.0 uL -> total 2.0 * 11.5 = 23.0 uL
        self.assertAlmostEqual(result.master_mix_volumes_total["10X T4 DNA Ligase Buffer"], 23.0)

    def test_calculate_master_mix_invalid_inputs(self):
        with self.assertRaises(AssemblyProtocolError):
            self.engine.calculate_master_mix(num_reactions=0)
        with self.assertRaises(AssemblyProtocolError):
            self.engine.calculate_master_mix(num_reactions=5, overage_pct=-5.0)

    def test_insert_to_vector_ratio_molar_calculation(self):
        # Vector: 3000 bp, 50 ng/uL stock, target mass 50 ng -> volume = 1.0 uL
        # Insert 1: 1000 bp, 30 ng/uL stock, 3:1 molar ratio
        # mass_insert = 3 * 50 * (1000/3000) = 50 ng -> volume = 50 / 30 = 1.667 uL
        inserts = [
            {
                "name": "GFP_Insert",
                "length_bp": 1000,
                "concentration_ng_ul": 30.0,
                "molar_ratio": 3.0,
            }
        ]

        result = self.engine.calculate_insert_to_vector_ratio(
            vector_bp=3000,
            vector_conc_ng_ul=50.0,
            inserts=inserts,
            vector_mass_ng=50.0,
            reaction_volume_ul=20.0,
            master_mix_volume_ul=10.0,
        )

        self.assertIsInstance(result, ReactionRatioResult)
        self.assertAlmostEqual(result.vector_spec.volume_ul, 1.0)
        self.assertEqual(len(result.insert_specs), 1)

        ins_spec = result.insert_specs[0]
        self.assertEqual(ins_spec.name, "GFP_Insert")
        self.assertAlmostEqual(ins_spec.target_mass_ng, 50.0)
        self.assertAlmostEqual(ins_spec.volume_ul, 50.0 / 30.0)

        # total_dna = 1.0 + 1.6667 = 2.6667 uL
        self.assertAlmostEqual(result.total_dna_volume_ul, 1.0 + (50.0 / 30.0))
        # available = 20.0 - 10.0 = 10.0 uL -> water = 10.0 - 2.6667 = 7.3333 uL
        self.assertAlmostEqual(result.water_volume_ul, 10.0 - (1.0 + (50.0 / 30.0)))

        d = result.to_dict()
        self.assertIn("vector_spec", d)
        self.assertIn("insert_specs", d)

    def test_pipetting_volume_error_low_volume(self):
        # High concentration vector (500 ng/uL) with 50 ng target mass -> 0.1 uL
        inserts = [
            {
                "name": "Ins",
                "length_bp": 1000,
                "concentration_ng_ul": 50.0,
                "molar_ratio": 3.0,
            }
        ]
        with self.assertRaises(PipettingVolumeError) as cm:
            self.engine.calculate_insert_to_vector_ratio(
                vector_bp=3000,
                vector_conc_ng_ul=500.0,  # 50 ng / 500 ng/uL = 0.1 uL -> Error!
                inserts=inserts,
            )
        self.assertIn("Vector", str(cm.exception))
        self.assertIn("minimum manual pipetting threshold", str(cm.exception))

    def test_dna_volume_capacity_overflow_error(self):
        # Dilute insert concentration (1 ng/uL) requiring huge volume (> 10 uL)
        inserts = [
            {
                "name": "Dilute_Ins",
                "length_bp": 2000,
                "concentration_ng_ul": 1.0,
                "molar_ratio": 5.0,
            }
        ]
        with self.assertRaises(AssemblyProtocolError) as cm:
            self.engine.calculate_insert_to_vector_ratio(
                vector_bp=3000,
                vector_conc_ng_ul=50.0,
                inserts=inserts,
                reaction_volume_ul=20.0,
                master_mix_volume_ul=10.0,
            )
        self.assertIn("exceeds reaction capacity", str(cm.exception))

    def test_generate_bench_protocol(self):
        inserts = [
            {
                "name": "RFP",
                "length_bp": 750,
                "concentration_ng_ul": 25.0,
                "molar_ratio": 3.0,
            }
        ]
        protocol = self.engine.generate_bench_protocol(
            num_reactions=4,
            vector_bp=4000,
            vector_conc_ng_ul=40.0,
            inserts=inserts,
            assembly_type="Gibson",
        )
        self.assertIsInstance(protocol, BenchProtocol)
        self.assertEqual(protocol.assembly_type, "Gibson Assembly")
        self.assertGreater(len(protocol.thermal_program), 0)
        self.assertGreater(len(protocol.instructions), 0)

        d = protocol.to_dict()
        self.assertIn("master_mix", d)
        self.assertIn("reaction_ratio", d)
        self.assertIn("thermal_program", d)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for LaboratoryExecutionView and ProtocolWorker QThread."""

import unittest

try:
    import PySide6.QtCore  # noqa: F401

    from karcytics_plugins.synthetic_biology.ui.views.laboratory_execution_view import (
        LaboratoryExecutionView,
        ProtocolWorker,
    )

    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, "PySide6 not installed in current environment")
class TestLaboratoryExecutionWorker(unittest.TestCase):
    def test_protocol_worker_execution(self):
        inserts = [
            {
                "name": "Insert_GFP",
                "length_bp": 1000,
                "concentration_ng_ul": 30.0,
                "molar_ratio": 3.0,
            }
        ]

        worker = ProtocolWorker(
            num_reactions=4,
            vector_bp=3000,
            vector_conc_ng_ul=50.0,
            inserts=inserts,
            assembly_type="Gibson",
            overage_pct=10.0,
            vector_mass_ng=50.0,
            default_molar_ratio=3.0,
            reaction_volume_ul=20.0,
        )

        received_protocol = []
        received_error = []

        def on_finished(protocol):
            received_protocol.append(protocol)

        def on_error(err_str):
            received_error.append(err_str)

        worker.finished_ok.connect(on_finished)
        worker.finished_err.connect(on_error)

        # Execute worker run directly in test
        worker.run()

        self.assertEqual(len(received_error), 0)
        self.assertEqual(len(received_protocol), 1)
        protocol = received_protocol[0]
        self.assertIsInstance(protocol, dict)
        self.assertEqual(protocol["num_reactions"], 4)
        self.assertEqual(protocol["assembly_type"], "Gibson Assembly")

    def test_protocol_worker_error_signal(self):
        # Trigger PipettingVolumeError (volume < 0.01 uL) via high concentration
        inserts = [
            {
                "name": "Insert_Low",
                "length_bp": 1000,
                "concentration_ng_ul": 30.0,
                "molar_ratio": 3.0,
            }
        ]

        worker = ProtocolWorker(
            num_reactions=4,
            vector_bp=3000,
            vector_conc_ng_ul=10000.0,  # 50 ng / 10000 ng/uL = 0.005 uL -> Error!
            inserts=inserts,
        )

        received_protocol = []
        received_error = []

        worker.finished_ok.connect(lambda p: received_protocol.append(p))
        worker.finished_err.connect(lambda e: received_error.append(e))

        worker.run()

        self.assertEqual(len(received_protocol), 0)
        self.assertEqual(len(received_error), 1)
        self.assertIn("minimum manual pipetting threshold", received_error[0])

    def test_view_populates_from_dict_payload(self):
        view = LaboratoryExecutionView()
        dict_payload = {
            "protocol_name": "Gibson Assembly Bench Protocol",
            "assembly_type": "Gibson Assembly",
            "num_reactions": 2,
            "master_mix": {
                "assembly_type": "Gibson Assembly",
                "num_reactions": 2,
                "overage_pct": 10.0,
                "multiplier": 2.2,
                "reaction_volume_ul": 20.0,
                "component_volumes_per_rxn": {"Gibson Master Mix": 10.0},
                "master_mix_volumes_total": {"Gibson Master Mix": 22.0},
                "total_master_mix_volume_ul": 22.0,
                "pipetting_warnings": [],
            },
            "reaction_ratio": {
                "assembly_type": "Gibson Assembly",
                "vector_spec": {
                    "name": "pUC19",
                    "role": "vector",
                    "length_bp": 2686,
                    "concentration_ng_ul": 50.0,
                    "molar_ratio": 1.0,
                    "target_mass_ng": 50.0,
                    "volume_ul": 1.0,
                },
                "insert_specs": [
                    {
                        "name": "GFP",
                        "role": "insert",
                        "length_bp": 720,
                        "concentration_ng_ul": 25.0,
                        "molar_ratio": 3.0,
                        "target_mass_ng": 40.2,
                        "volume_ul": 1.608,
                    }
                ],
                "total_dna_volume_ul": 2.608,
                "master_mix_volume_ul": 10.0,
                "water_volume_ul": 7.392,
                "total_reaction_volume_ul": 20.0,
                "pipetting_warnings": [],
            },
            "thermal_program": [],
            "instructions": [],
        }

        view._populate_results_tables(dict_payload)
        view._populate_worklist_table(dict_payload)

        # Master mix table populated
        self.assertEqual(view.table_master_mix.rowCount(), 1)
        self.assertEqual(view.table_master_mix.item(0, 0).text(), "Gibson Master Mix")

        # Pipetting table populated (Vector + 1 Insert + Water = 3 rows)
        self.assertEqual(view.table_pipetting.rowCount(), 3)
        self.assertEqual(view.table_pipetting.item(0, 0).text(), "pUC19")
        self.assertEqual(view.table_pipetting.item(1, 0).text(), "GFP")
        self.assertEqual(view.table_pipetting.item(2, 0).text(), "Nuclease-Free Water")

        # Worklist table populated (2 reactions * 4 transfers = 8 rows)
        self.assertEqual(view.table_worklist.rowCount(), 8)


if __name__ == "__main__":
    unittest.main()

"""Unit tests for LaboratoryExecutionView and ProtocolWorker QThread."""

import unittest

try:
    import PyQt6.QtCore  # noqa: F401

    from karcytics_plugins.synthetic_biology.analysis.assembly.protocol_engine import (
        BenchProtocol,
    )
    from karcytics_plugins.synthetic_biology.ui.views.laboratory_execution_view import (
        ProtocolWorker,
    )

    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False


@unittest.skipUnless(HAS_PYQT6, "PyQt6 not installed in current environment")
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

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)

        # Execute worker run directly in test
        worker.run()

        self.assertEqual(len(received_error), 0)
        self.assertEqual(len(received_protocol), 1)
        protocol = received_protocol[0]
        self.assertIsInstance(protocol, BenchProtocol)
        self.assertEqual(protocol.num_reactions, 4)
        self.assertEqual(protocol.assembly_type, "Gibson Assembly")

    def test_protocol_worker_error_signal(self):
        # Trigger PipettingVolumeError (volume < 0.5 uL) via high concentration
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
            vector_conc_ng_ul=1000.0,  # 50 ng / 1000 ng/uL = 0.05 uL -> Error!
            inserts=inserts,
        )

        received_protocol = []
        received_error = []

        worker.finished.connect(lambda p: received_protocol.append(p))
        worker.error.connect(lambda e: received_error.append(e))

        worker.run()

        self.assertEqual(len(received_protocol), 0)
        self.assertEqual(len(received_error), 1)
        self.assertIn("minimum manual pipetting threshold", received_error[0])


if __name__ == "__main__":
    unittest.main()

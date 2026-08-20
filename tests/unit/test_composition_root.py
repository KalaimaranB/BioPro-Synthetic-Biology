from pathlib import Path

import karcytics_plugins.synthetic_biology.ui.composition_root as comp_root

# pyrefly: ignore [missing-import]
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.composition_root import ServiceFactory


def test_service_factory_build_all_handles_explicit_path(tmp_path):
    factory = ServiceFactory(SynBioState())
    test_cat_path = tmp_path / "catalogue.json"
    factory.build_all(catalogue_path=str(test_cat_path))

    service = factory.get("parts_catalogue")
    assert service is not None
    assert len(service.get_all_parts()) > 0
    assert service._repository.file_path == str(test_cat_path)


def test_service_factory_anchors_to_plugin_dir():
    factory = ServiceFactory(SynBioState())
    factory.build_all()

    service = factory.get("parts_catalogue")
    assert service is not None
    expected_path = Path(comp_root.__file__).resolve().parents[1] / "catalogue.json"
    assert service._repository.file_path == str(expected_path)


def test_synbio_panel_handles_plugin_context_parent():
    from PyQt6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel

    class DummyPluginContext:
        pass

    ctx = DummyPluginContext()
    panel = SynBioPanel(parent=ctx)
    assert panel.context is ctx
    assert panel.parent() is None

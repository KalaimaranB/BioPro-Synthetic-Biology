from pathlib import Path

import karcytics_plugins.synthetic_biology.ui.composition_root as comp_root

# pyrefly: ignore [missing-import]
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.analysis.user_paths import (
    USER_DIR_ENV,
    user_catalogue_path,
)
from karcytics_plugins.synthetic_biology.ui.composition_root import ServiceFactory


def test_service_factory_build_all_handles_explicit_path(tmp_path):
    factory = ServiceFactory(SynBioState())
    test_cat_path = tmp_path / "catalogue.json"
    factory.build_all(catalogue_path=str(test_cat_path))

    service = factory.get("parts_catalogue")
    assert service is not None
    assert len(service.get_all_parts()) > 0
    assert service._repository.file_path == str(test_cat_path)


def test_service_factory_reads_the_payload_but_writes_outside_it(tmp_path, monkeypatch):
    """Writes must land in the user directory, reads in the signed payload.

    This used to assert the write target was the payload's own catalogue.json,
    which is precisely the defect: that file is hashed into security.json, so
    every part a student saved invalidated the plugin signature.
    """
    monkeypatch.setenv(USER_DIR_ENV, str(tmp_path / "user_data"))

    factory = ServiceFactory(SynBioState())
    factory.build_all()

    service = factory.get("parts_catalogue")
    assert service is not None
    repo = service._repository

    payload_catalogue = Path(comp_root.__file__).resolve().parents[1] / "catalogue.json"
    assert repo.shipped_path == payload_catalogue, "shipped parts should still be read"
    assert Path(repo.file_path) == user_catalogue_path(), "writes must go to the user dir"
    assert not str(repo.file_path).startswith(str(payload_catalogue.parent))
    assert service.get_all_parts(), "the shipped catalogue should still be visible"


def test_synbio_panel_handles_plugin_context_parent(destroy_after):
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel

    class DummyPluginContext:
        pass

    ctx = DummyPluginContext()
    panel = destroy_after(SynBioPanel(parent=ctx))
    assert panel.context is ctx
    assert panel.parent() is None

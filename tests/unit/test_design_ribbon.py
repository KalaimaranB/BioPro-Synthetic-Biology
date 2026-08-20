"""Unit tests for DesignRibbon dynamic part selector QComboBox."""

import sys
from unittest.mock import MagicMock

# Mock sbol3 if not present
if "sbol3" not in sys.modules:
    sys.modules["sbol3"] = MagicMock()

from PyQt6.QtWidgets import QApplication, QComboBox

from karcytics_plugins.synthetic_biology.analysis.parts.components import CDS, Promoter
from karcytics_plugins.synthetic_biology.ui.ribbons.design_ribbon import DesignRibbon

app = QApplication.instance() or QApplication([])


class DummyCatalogueService:
    def __init__(self, parts):
        self._parts = parts

    def get_all_parts(self):
        return self._parts

    def get_part(self, part_id):
        for p in self._parts:
            if p.id == part_id:
                return p
        return None


class DummyFactory:
    def __init__(self, catalogue_service=None):
        self._cat = catalogue_service

    def get(self, name):
        if name == "parts_catalogue":
            return self._cat
        return None


def test_design_ribbon_ui_setup():
    """Test DesignRibbon initializes with part_selector_combo QComboBox."""
    ribbon = DesignRibbon(service_factory=None)

    assert hasattr(ribbon, "part_selector_combo")
    assert isinstance(ribbon.part_selector_combo, QComboBox)
    assert ribbon.part_selector_combo.minimumWidth() >= 250


def test_update_part_selector_role_filtering():
    """Test that update_part_selector filters database parts matching the selected
    role.
    """
    p1 = Promoter(id="P_tet", name="TetR Promoter")
    c1 = CDS(id="GFP_cds", name="GFP CDS")
    cat = DummyCatalogueService([p1, c1])
    factory = DummyFactory(cat)

    ribbon = DesignRibbon(service_factory=factory)

    # Role: Promoter
    ribbon.update_part_selector("Promoter")
    assert ribbon.part_selector_combo.count() == 1
    assert ribbon.part_selector_combo.currentData() == p1

    # Role: Coding Sequence
    ribbon.update_part_selector("Coding Sequence")
    assert ribbon.part_selector_combo.count() == 1
    assert ribbon.part_selector_combo.currentData() == c1


def test_on_fetch_emits_part_fetched():
    """Test that clicking Fetch Part emits part_fetched signal with selected part."""
    p1 = Promoter(id="P_tet", name="TetR Promoter")
    cat = DummyCatalogueService([p1])
    factory = DummyFactory(cat)

    ribbon = DesignRibbon(service_factory=factory)

    emitted_parts = []
    ribbon.part_fetched.connect(lambda p: emitted_parts.append(p))

    ribbon._on_fetch()

    assert len(emitted_parts) == 1
    assert emitted_parts[0] == p1

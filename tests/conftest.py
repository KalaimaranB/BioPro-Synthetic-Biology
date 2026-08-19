import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Ensure src is in sys.path
root_dir = Path(__file__).parent.parent
src_dir = root_dir / "src"

if str(src_dir) in sys.path:
    sys.path.remove(str(src_dir))
if str(root_dir) in sys.path:
    sys.path.remove(str(root_dir))

sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(root_dir))

import pytest  # noqa: E402
from PyQt6.QtWidgets import QLabel, QPushButton, QSplitter, QWidget  # noqa: E402

# Mock karcytics_sdk before it gets imported
mock_karcytics_sdk_plugin = MagicMock()


class DummyTaskBase:
    def __init__(self, *args, **kwargs):
        pass


from PyQt6.QtCore import pyqtSignal  # noqa: E402


class DummyPluginBase(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.plugin_id = kwargs.get("plugin_id", args[0] if args else "")


class DummyAnalysisBase:
    def __init__(self, *args, **kwargs):
        pass


class DummyButton(QPushButton):
    pass


class DummySplitter(QSplitter):
    pass


class DummyLabel(QLabel):
    pass


from PyQt6.QtWidgets import QComboBox, QLineEdit, QListWidget, QSpinBox  # noqa: E402


class DummyComboBox(QComboBox):
    pass


class DummyLineEdit(QLineEdit):
    pass


class DummyListWidget(QListWidget):
    pass


class DummySpinBox(QSpinBox):
    pass


mock_karcytics_sdk_plugin.PluginBase = DummyPluginBase
mock_karcytics_sdk_plugin.AnalysisBase = DummyAnalysisBase
mock_karcytics_sdk_plugin.PluginState = DummyAnalysisBase
mock_karcytics_sdk_plugin.validate_file_exists = lambda path: (True, "")

mock_tasks = MagicMock()
mock_tasks.TaskBase = DummyTaskBase
mock_karcytics_sdk_plugin.tasks = mock_tasks
sys.modules["karcytics_sdk.plugin.tasks"] = mock_tasks


class MockComponents:
    PrimaryButton: Any
    SecondaryButton: Any
    BioSplitter: Any
    BioCaptionLabel: Any
    BioComboBox: Any
    BioRunButton: Any
    BioCancelButton: Any
    BioStatusLabel: Any
    BioLineEdit: Any
    BioListWidget: Any
    BioToggleButton: Any
    BioSpinBox: Any


mock_components = MockComponents()
mock_components.PrimaryButton = DummyButton
mock_components.SecondaryButton = DummyButton
mock_components.BioSplitter = DummySplitter
mock_components.BioCaptionLabel = DummyLabel
mock_components.BioComboBox = DummyComboBox
mock_components.BioRunButton = DummyButton
mock_components.BioCancelButton = DummyButton
mock_components.BioStatusLabel = DummyLabel
mock_components.BioLineEdit = DummyLineEdit
mock_components.BioListWidget = DummyListWidget
mock_components.BioToggleButton = DummyButton
mock_components.BioSpinBox = DummySpinBox
mock_karcytics_sdk_plugin.components = mock_components


class DummyThemeMeta(type):
    def __getattr__(cls, name):
        if name.startswith("SIZE"):
            return "12"
        return "#000000"


class DummyColors(metaclass=DummyThemeMeta):
    pass


sys.modules["karcytics_sdk"] = MagicMock()
sys.modules["karcytics_sdk.plugin"] = mock_karcytics_sdk_plugin  # type: ignore
sys.modules["karcytics_sdk.plugin.components"] = mock_components  # type: ignore
sys.modules["karcytics_sdk.plugin.events"] = MagicMock()
sys.modules["karcytics_sdk.plugin.workflow"] = MagicMock()
sys.modules["karcytics_sdk.plugin.tasks"] = mock_tasks

mock_theme_fallback = types.ModuleType("theme_fallback")
mock_theme_fallback.Colors = DummyColors  # type: ignore
mock_theme_fallback.Fonts = DummyColors  # type: ignore
mock_theme_fallback.theme_manager = MagicMock()  # type: ignore
sys.modules["karcytics_sdk.plugin.theme_fallback"] = mock_theme_fallback

try:
    import sbol3  # noqa: F401
except ImportError:
    sys.modules["sbol3"] = MagicMock()

try:
    import pyqtgraph  # noqa: F401
except ImportError:
    sys.modules["pyqtgraph"] = MagicMock()

from karcytics_plugins.synthetic_biology.analysis.state import SynBioState  # noqa: E402


@pytest.fixture
def empty_state():
    """Returns a fresh SynBioState with empty circuit data."""
    return SynBioState()

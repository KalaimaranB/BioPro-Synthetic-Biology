import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure src and plugin paths are in sys.path
root_dir = Path(__file__).parent.parent
src_dir = root_dir / "src"
plugin_dir = src_dir / "biopro_plugins" / "synthetic_biology"

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
if str(plugin_dir) not in sys.path:
    sys.path.insert(0, str(plugin_dir))

import pytest  # noqa: E402
from PyQt6.QtWidgets import QLabel, QPushButton, QSplitter, QWidget  # noqa: E402

# Mock biopro_sdk before it gets imported
mock_biopro_sdk_plugin = MagicMock()


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


mock_biopro_sdk_plugin.PluginBase = DummyPluginBase
mock_biopro_sdk_plugin.AnalysisBase = DummyAnalysisBase
mock_biopro_sdk_plugin.PluginState = DummyAnalysisBase
mock_biopro_sdk_plugin.validate_file_exists = lambda path: (True, "")

mock_tasks = MagicMock()
mock_tasks.TaskBase = DummyTaskBase
mock_biopro_sdk_plugin.tasks = mock_tasks
sys.modules["biopro_sdk.plugin.tasks"] = mock_tasks


class MockComponents:
    pass


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
mock_biopro_sdk_plugin.components = mock_components

sys.modules["biopro_sdk"] = MagicMock()
sys.modules["biopro_sdk.plugin"] = mock_biopro_sdk_plugin
sys.modules["biopro_sdk.plugin.components"] = mock_components
sys.modules["biopro_sdk.plugin.events"] = MagicMock()
sys.modules["biopro_sdk.plugin.workflow"] = MagicMock()

# Mock biopro core and UI as well
mock_biopro = MagicMock()
sys.modules["biopro"] = mock_biopro
sys.modules["biopro.ui"] = MagicMock()


class DummyThemeMeta(type):
    def __getattr__(cls, name):
        if name.startswith("SIZE"):
            return "12"
        return "#000000"


class DummyColors(metaclass=DummyThemeMeta):
    pass


class DummyFonts(metaclass=DummyThemeMeta):
    pass


mock_theme = MagicMock()
mock_theme.Colors = DummyColors
mock_theme.Fonts = DummyFonts
sys.modules["biopro.ui.theme"] = mock_theme
sys.modules["biopro.core"] = MagicMock()
sys.modules["biopro.core.task_scheduler"] = MagicMock()
sys.modules["biopro.shared"] = MagicMock()
sys.modules["biopro.shared.ui"] = MagicMock()
sys.modules["biopro.shared.ui.ui_components"] = mock_components

from analysis.state import SynBioState  # noqa: E402
@pytest.fixture
def empty_state():
    """Returns a fresh SynBioState with empty circuit data."""
    return SynBioState()

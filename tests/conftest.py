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
from PyQt6.QtCore import QObject  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QSplitter, QWidget  # noqa: E402

try:
    import PySide6  # noqa: F401
except ImportError:
    import PyQt6.QtCore
    import PyQt6.QtGui
    import PyQt6.QtWidgets
    import PyQt6.QtTest

    pyside6 = types.ModuleType("PySide6")
    _qtcore = types.ModuleType("PySide6.QtCore")
    for _k, _v in PyQt6.QtCore.__dict__.items():
        setattr(_qtcore, _k, _v)
    _qtcore.Signal = PyQt6.QtCore.pyqtSignal
    _qtcore.Slot = PyQt6.QtCore.pyqtSlot
    _qtcore.Property = PyQt6.QtCore.pyqtProperty

    _qtgui = types.ModuleType("PySide6.QtGui")
    for _k, _v in PyQt6.QtGui.__dict__.items():
        setattr(_qtgui, _k, _v)

    _qtwidgets = types.ModuleType("PySide6.QtWidgets")
    for _k, _v in PyQt6.QtWidgets.__dict__.items():
        setattr(_qtwidgets, _k, _v)

    _qttest = types.ModuleType("PySide6.QtTest")
    for _k, _v in PyQt6.QtTest.__dict__.items():
        setattr(_qttest, _k, _v)

    pyside6.QtCore = _qtcore
    pyside6.QtGui = _qtgui
    pyside6.QtWidgets = _qtwidgets
    pyside6.QtTest = _qttest
    pyside6.__version__ = PyQt6.QtCore.PYQT_VERSION_STR
    _qtcore.__version__ = PyQt6.QtCore.PYQT_VERSION_STR
    pyside6.__path__ = []

    sys.modules["PySide6"] = pyside6
    sys.modules["PySide6.QtCore"] = _qtcore
    sys.modules["PySide6.QtGui"] = _qtgui
    sys.modules["PySide6.QtWidgets"] = _qtwidgets
    sys.modules["PySide6.QtTest"] = _qttest

_qapp = QApplication.instance() or QApplication(["pytest", "-platform", "offscreen"])

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


from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QLineEdit,
    QListWidget,
    QProgressDialog,
    QScrollArea,
    QSpinBox,
    QTableWidget,
)


class DummyComboBox(QComboBox):
    pass


class DummyLineEdit(QLineEdit):
    pass


class DummyListWidget(QListWidget):
    pass


class DummySpinBox(QSpinBox):
    pass


class DummyDoubleSpinBox(QDoubleSpinBox):
    pass


class DummyTableWidget(QTableWidget):
    pass


class DummyScrollArea(QScrollArea):
    pass


class DummyProgressDialog(QProgressDialog):
    pass


from PyQt6.QtWidgets import QGraphicsScene, QGraphicsView, QHBoxLayout


class DummyDirtyTrackingGraphicsScene(QGraphicsScene):
    def mark_dirty(self, item):
        item.update()


class DummyDirtyTrackingGraphicsView(QGraphicsView):
    def __init__(self, scene=None, parent=None, update_mode=None):
        if scene is not None:
            super().__init__(scene, parent)
        else:
            super().__init__(parent)


class DummyBioRibbon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self.run_button = DummyButton("Run", self)
        self.cancel_button = DummyButton("Cancel", self)

    def add_widget(self, w):
        self._layout.addWidget(w)

    def add_stretch(self):
        self._layout.addStretch()

    def add_separator(self):
        pass

    def start_run(self):
        pass

    def cancel_run(self):
        pass

    def finish_run(self):
        pass


mock_karcytics_sdk_plugin.PluginBase = DummyPluginBase
mock_karcytics_sdk_plugin.AnalysisBase = DummyAnalysisBase
mock_karcytics_sdk_plugin.PluginState = DummyAnalysisBase
mock_karcytics_sdk_plugin.DirtyTrackingGraphicsScene = DummyDirtyTrackingGraphicsScene
mock_karcytics_sdk_plugin.DirtyTrackingGraphicsView = DummyDirtyTrackingGraphicsView


class DummyAnalysisWorker(QWidget):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    cancelled = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._is_cancelled = False
        self._is_running = False

    def cancel(self):
        self._is_cancelled = True
        self._is_running = False

    def is_cancelled(self):
        return getattr(self, "_is_cancelled", False)

    def isRunning(self):
        return getattr(self, "_is_running", False)

    def start(self):
        self._is_running = True
        if hasattr(self, "run"):
            self.run()
        self._is_running = False

    def wait(self, msecs=0):
        return True

    def quit(self):
        self.cancel()

    def requestInterruption(self):
        self.cancel()


class DummyAnalysisRunnable:
    def __init__(self, worker):
        self.worker = worker

    def run(self):
        if self.worker:
            self.worker.run()


mock_karcytics_sdk_plugin.AnalysisWorker = DummyAnalysisWorker
mock_karcytics_sdk_plugin.validate_file_exists = lambda path: (True, "")

mock_tasks = MagicMock()
mock_tasks.TaskBase = DummyTaskBase
mock_karcytics_sdk_plugin.tasks = mock_tasks
sys.modules["karcytics_sdk.plugin.tasks"] = mock_tasks

mock_ribbon = types.ModuleType("ribbon")
mock_ribbon.BioRibbon = DummyBioRibbon
mock_karcytics_sdk_plugin.ribbon = mock_ribbon
sys.modules["karcytics_sdk.plugin.ribbon"] = mock_ribbon

mock_runtime_services = types.ModuleType("runtime_services")
mock_runtime_services.event_bus = MagicMock()
mock_runtime_services.task_scheduler = MagicMock()
mock_runtime_services.AnalysisRunnable = DummyAnalysisRunnable
mock_karcytics_sdk_plugin.runtime_services = mock_runtime_services
sys.modules["karcytics_sdk.plugin.runtime_services"] = mock_runtime_services
mock_runtime_services.task_scheduler = MagicMock()
mock_karcytics_sdk_plugin.runtime_services = mock_runtime_services
sys.modules["karcytics_sdk.plugin.runtime_services"] = mock_runtime_services


class MockComponents:
    PrimaryButton = DummyButton
    SecondaryButton = DummyButton
    DangerButton = DummyButton
    BioButton = DummyButton
    BioRunButton = DummyButton
    BioCancelButton = DummyButton
    BioToggleButton = DummyButton
    BioSplitter = DummySplitter
    BioCaptionLabel = DummyLabel
    BioHeaderLabel = DummyLabel
    BioStatusLabel = DummyLabel
    SubtitleLabel = DummyLabel
    BioComboBox = DummyComboBox
    BioLineEdit = DummyLineEdit
    BioListWidget = DummyListWidget
    BioSpinBox = DummySpinBox
    BioDoubleSpinBox = DummyDoubleSpinBox
    BioTableWidget = DummyTableWidget
    BioScrollArea = DummyScrollArea
    BioProgressDialog = DummyProgressDialog

    def __getattr__(self, name: str) -> Any:
        if "Button" in name:
            return DummyButton
        if "Table" in name:
            return DummyTableWidget
        if "Splitter" in name:
            return DummySplitter
        if "SpinBox" in name:
            return DummySpinBox
        if "LineEdit" in name:
            return DummyLineEdit
        if "ComboBox" in name:
            return DummyComboBox
        if "ListWidget" in name:
            return DummyListWidget
        if "Label" in name:
            return DummyLabel
        if "Dialog" in name:
            return DummyProgressDialog
        if "ScrollArea" in name:
            return DummyScrollArea
        return MagicMock


mock_components = MockComponents()
mock_karcytics_sdk_plugin.components = mock_components


class DummyThemeMeta(type):
    def __getattr__(cls, name):
        if name.startswith("SIZE"):
            return "12"
        if name == "CHART_COLORS":
            return ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
        return "#000000"


class DummyColors(metaclass=DummyThemeMeta):
    BG_DARKEST = "#121212"
    BG_DARK = "#1e1e1e"
    FG_PRIMARY = "#eeeeee"
    FG_SECONDARY = "#aaaaaa"
    CHART_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]


class DummyThemeManager(QObject):
    theme_changed = pyqtSignal(str)
    _theme = "dark"

    def set_theme(self, theme: str):
        self._theme = theme
        if theme == "light":
            DummyColors.BG_DARKEST = "#ffffff"
            DummyColors.BG_DARK = "#f0f0f0"
            DummyColors.FG_PRIMARY = "#111111"
            DummyColors.FG_SECONDARY = "#333333"
        else:
            DummyColors.BG_DARKEST = "#121212"
            DummyColors.BG_DARK = "#1e1e1e"
            DummyColors.FG_PRIMARY = "#eeeeee"
            DummyColors.FG_SECONDARY = "#aaaaaa"
        self.theme_changed.emit(theme)


dummy_theme_manager = DummyThemeManager()


class DummyOneShotWorkerThread(DummyAnalysisWorker):
    finished_ok = pyqtSignal(object)
    finished_err = pyqtSignal(str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_cancelled = False
        self._is_running = False

    def stop_and_wait(self, timeout=1000):
        self._is_running = False
        return True

    def cancel(self):
        self._is_cancelled = True
        self._is_running = False

    def is_cancelled(self):
        return getattr(self, "_is_cancelled", False)

    def isRunning(self):
        return getattr(self, "_is_running", False)

    def start(self):
        self._is_running = True
        if hasattr(self, "_execute"):
            self._execute()
        elif hasattr(self, "run"):
            self.run()
        self._is_running = False

    def wait(self, msecs=0):
        return True

    def quit(self):
        self.cancel()

    def requestInterruption(self):
        self.cancel()


mock_karcytics_sdk_plugin.OneShotWorkerThread = DummyOneShotWorkerThread

mock_sdk = types.ModuleType("karcytics_sdk")
mock_sdk.__path__ = []
mock_karcytics_sdk_plugin.__path__ = []
mock_sdk.plugin = mock_karcytics_sdk_plugin
sys.modules["karcytics_sdk"] = mock_sdk

mock_testing = types.ModuleType("karcytics_sdk.testing")
class DummyContractTestBase:
    PLUGIN_DIR = None
mock_testing.ContractTestBase = DummyContractTestBase
mock_sdk.testing = mock_testing
sys.modules["karcytics_sdk.testing"] = mock_testing

sys.modules["karcytics_sdk.plugin"] = mock_karcytics_sdk_plugin  # type: ignore
sys.modules["karcytics_sdk.plugin.components"] = mock_components  # type: ignore
sys.modules["karcytics_sdk.plugin.events"] = MagicMock()
sys.modules["karcytics_sdk.plugin.workflow"] = MagicMock()
sys.modules["karcytics_sdk.plugin.tasks"] = mock_tasks

mock_task_scheduler = types.ModuleType("task_scheduler")
mock_task_scheduler.AnalysisWorker = DummyAnalysisWorker
mock_task_scheduler.AnalysisRunnable = DummyAnalysisRunnable
mock_karcytics_sdk_plugin.task_scheduler = mock_task_scheduler
sys.modules["karcytics_sdk.plugin.task_scheduler"] = mock_task_scheduler

mock_dialogs = MagicMock()
mock_dialogs.show_error = MagicMock()
mock_dialogs.show_warning = MagicMock()
mock_dialogs.show_info = MagicMock()
mock_dialogs.ask_yes_no = MagicMock(return_value=True)
mock_dialogs.ask_ok_cancel = MagicMock(return_value=True)
mock_dialogs.get_save_path = MagicMock(return_value="/tmp/test.csv")
mock_dialogs.get_directory = MagicMock(return_value="/tmp")
mock_karcytics_sdk_plugin.dialogs = mock_dialogs
sys.modules["karcytics_sdk.plugin.dialogs"] = mock_dialogs

mock_toast = MagicMock()
mock_toast.show_toast = MagicMock()
mock_karcytics_sdk_plugin.toast = mock_toast
sys.modules["karcytics_sdk.plugin.toast"] = mock_toast

mock_theme_fallback = types.ModuleType("theme_fallback")
mock_theme_fallback.Colors = DummyColors  # type: ignore
mock_theme_fallback.Fonts = DummyColors  # type: ignore
mock_theme_fallback.theme_manager = dummy_theme_manager  # type: ignore
mock_theme_fallback.get_contrast_text_color = lambda bg: "#ffffff"  # type: ignore
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


@pytest.fixture(scope="session", autouse=True)
def _qt_application():
    """One QApplication for the whole run: building any widget without one aborts the process."""
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def destroy_after():
    """Register a top-level widget to be destroyed when the test ends.

    A panel that is merely dropped becomes cyclic garbage whose C++ half is
    still alive. The collector empties the Python wrapper's attributes first,
    and the C++ teardown then calls back into it: pyqtgraph's
    `LabelItem.sizeHint` raises AttributeError on its missing `_sizeHint`, and
    pytest-qt fails whichever unrelated test is running when that collection
    happens to fire. Destroying the widget through Qt first avoids it.
    """
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    widgets = []

    def register(widget):
        widgets.append(widget)
        return widget

    yield register
    for widget in widgets:
        widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

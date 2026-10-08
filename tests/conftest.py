import sys
from pathlib import Path
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

# The tests run against the real karcytics_sdk (a declared dependency), not a
# stand-in: a mocked SDK hides exactly the integration mistakes these tests
# should catch, and every newly-adopted SDK component would need a new stub.

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

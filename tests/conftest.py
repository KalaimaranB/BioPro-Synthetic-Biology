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

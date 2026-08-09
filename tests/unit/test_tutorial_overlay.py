"""Unit tests for AcademyTutorialDialog tutorial overlay."""

import sys
from unittest.mock import MagicMock

# Mock sbol3 if not present
if "sbol3" not in sys.modules:
    sys.modules["sbol3"] = MagicMock()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

try:
    from ui.wizards.tutorial_overlay import (
        AcademyTutorialDialog,
        SYNTHETIC_BIOLOGY_TUTORIAL_STEPS,
    )
except ImportError:
    from biopro.plugins.synthetic_biology.ui.wizards.tutorial_overlay import (
        AcademyTutorialDialog,
        SYNTHETIC_BIOLOGY_TUTORIAL_STEPS,
    )

app = QApplication.instance() or QApplication([])


def test_tutorial_overlay_initialization():
    """Test overlay dialog initialization and translucent frameless flags."""
    dlg = AcademyTutorialDialog()

    assert dlg.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dlg.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert dlg.current_step == 0
    assert (
        dlg.step_counter_label.text()
        == f"Step 1 of {len(SYNTHETIC_BIOLOGY_TUTORIAL_STEPS)}"
    )
    assert dlg.title_label.text() == SYNTHETIC_BIOLOGY_TUTORIAL_STEPS[0]["title"]
    assert dlg.progress_bar.value() == int(
        (1 / len(SYNTHETIC_BIOLOGY_TUTORIAL_STEPS)) * 100
    )


def test_tutorial_overlay_navigation():
    """Test step navigation: next, previous, progress bar update, finish state."""
    dlg = AcademyTutorialDialog()

    # Step 0: Back button hidden
    assert dlg.back_btn.isHidden()
    assert dlg.next_btn.text() == "Next ➔"

    # Click Next -> Step 1
    dlg._next_step()
    assert dlg.current_step == 1
    assert (
        dlg.step_counter_label.text()
        == f"Step 2 of {len(SYNTHETIC_BIOLOGY_TUTORIAL_STEPS)}"
    )
    assert not dlg.back_btn.isHidden()

    # Click Prev -> Step 0
    dlg._prev_step()
    assert dlg.current_step == 0

    # Fast forward to last step
    last_idx = len(SYNTHETIC_BIOLOGY_TUTORIAL_STEPS) - 1
    dlg.render_step(last_idx)
    assert dlg.current_step == last_idx
    assert dlg.next_btn.text() == "Finish 🎉"
    assert dlg.progress_bar.value() == 100

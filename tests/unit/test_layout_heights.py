"""Each view must fit the height the real dialog gives it.

test_ui_ux_compliance asserts width six times and height zero times, which is
exactly why the gel overflow shipped: GelView's layout minimum was 450 px, the
tab allotted 393 px, Qt could not satisfy the minimums and laid the caption
labels on top of the canvas. Nothing measured that, and a render at the
widget's own sizeHint() — which is what the visual QA used — looks fine,
because at its own sizeHint everything fits by definition.

So these measure inside the real dialog, at realistic window sizes.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
    PlasmidAssemblyController,
)
from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
    PrimerDesignDialog,
)

from .sequence_fixtures import ECORI_TAIL, HINDIII_TAIL, SYNTHETIC_TEMPLATE

#: Window sizes a student would actually use: a 13" laptop, and the size the
#: dialog asks for. Nothing here may depend on a maximised window.
REALISTIC_SIZES = [(1031, 783), (1280, 860), (1040, 760)]


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _settle(ms: int = 60) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _dialog(destroy_after, size):
    dialog = destroy_after(
        PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(SynBioState()))
    )
    dialog.resize(*size)
    dialog.show()
    _settle()
    return dialog


def _overlaps(first, second) -> bool:
    """True when two sibling widgets occupy the same vertical space."""
    a, b = first.geometry(), second.geometry()
    return a.bottom() > b.top() and b.bottom() > a.top()


@pytest.mark.unit
@pytest.mark.parametrize("size", REALISTIC_SIZES)
def test_every_tab_fits_the_height_the_dialog_allots_it(app, destroy_after, size):
    """A view whose layout minimum exceeds its allotment gets overlapped children."""
    dialog = _dialog(destroy_after, size)

    offenders = []
    for index in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(index)
        _settle()
        page = dialog.tabs.widget(index)
        needed = page.layout().minimumSize().height()
        allotted = page.height()
        if needed > allotted:
            offenders.append(
                f"{dialog.tabs.tabText(index)}: needs {needed}px, allotted {allotted}px"
            )
    assert not offenders, "tab content cannot fit:\n" + "\n".join(offenders)


@pytest.mark.unit
@pytest.mark.parametrize("size", REALISTIC_SIZES)
def test_the_gel_captions_are_never_drawn_over_the_gel(app, destroy_after, size):
    """The exact defect: captions laid inside the scroll area's rectangle."""
    dialog = _dialog(destroy_after, size)
    dialog.tabs.setCurrentIndex(2)
    _settle()

    view = dialog.gel_view
    scroll = view.canvas.parentWidget().parentWidget()

    for caption in (view.model_note, view.limitations, view.selection_note):
        assert not _overlaps(scroll, caption), (
            f"{caption.text()[:40]!r} overlaps the gel: "
            f"gel {scroll.geometry()}, caption {caption.geometry()}"
        )


@pytest.mark.unit
def test_the_gel_views_layout_minimum_stays_under_a_realistic_allotment(app, destroy_after):
    """Pinned as a number so the regression is visible, not just its symptom."""
    dialog = _dialog(destroy_after, (1031, 783))
    dialog.tabs.setCurrentIndex(2)
    _settle()

    needed = dialog.gel_view.layout().minimumSize().height()
    allotted = dialog.tabs.widget(2).height()
    assert needed <= allotted, f"GelView needs {needed}px but is given {allotted}px"


@pytest.mark.unit
@pytest.mark.parametrize("size", REALISTIC_SIZES)
def test_no_two_siblings_overlap_on_any_tab(app, destroy_after, size):
    """A generalisation of the gel bug: over-constrained layouts overlap."""
    dialog = _dialog(destroy_after, size)

    offenders = []
    for index in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(index)
        _settle()
        layout = dialog.tabs.widget(index).layout()
        widgets = [
            layout.itemAt(i).widget()
            for i in range(layout.count())
            if layout.itemAt(i).widget() is not None and layout.itemAt(i).widget().isVisible()
        ]
        for first, second in zip(widgets, widgets[1:], strict=False):
            if _overlaps(first, second):
                offenders.append(
                    f"{dialog.tabs.tabText(index)}: "
                    f"{type(first).__name__} overlaps {type(second).__name__}"
                )
    assert not offenders, "overlapping siblings:\n" + "\n".join(offenders)


@pytest.mark.unit
def test_the_gel_still_fits_after_a_real_run_with_three_lanes(app, destroy_after):
    """Lanes are added at runtime; the layout must survive the content."""
    dialog = _dialog(destroy_after, (1031, 783))
    dialog.fwd_overhang_edit.setText(ECORI_TAIL)
    dialog.rev_overhang_edit.setText(HINDIII_TAIL)
    dialog._on_design_clicked()
    dialog.candidate_table.selectRow(0)
    dialog.tabs.setCurrentIndex(2)
    _settle()

    view = dialog.gel_view
    scroll = view.canvas.parentWidget().parentWidget()
    assert len(view.canvas._lanes) >= 2
    assert not _overlaps(scroll, view.model_note)
    assert not _overlaps(scroll, view.limitations)

"""A bad character in a 5' tail box must not kill the plugin process.

The defect this closes, reported from a real session: on the Design Primers
dialog, typing ``q`` into a tail box crashed the whole application about
250 ms after the keystroke, with no error dialog and nothing in the log.

The chain was: ``textChanged`` -> a 250 ms debounce ``QTimer`` ->
``_refresh_tail_enzymes`` -> ``_tail_enzymes`` -> ``rst.enzymes_for_tail``,
which validates its input and raises ``SequenceRejectedError`` on anything
that is not ACGT. Raised from a timer slot, the exception unwinds into
PySide6 with no Python frame left to catch it, reaches the daemon's
``sys.excepthook``, and that handler calls ``sys.exit(1)``. The traceback
goes to stderr, which no log file was reading, which is why the plugin log
simply stopped mid-session.

Two things are asserted here, because only the second one is the actual bug:

* the refusal is reported next to the box, and Design refuses to run; and
* a process wired up the way the daemon wires it **survives** the keystroke.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap

import pytest
from PySide6.QtWidgets import QApplication

from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
    PlasmidAssemblyController,
)
from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
    PrimerDesignDialog,
)

from .sequence_fixtures import ECORI_TAIL, SYNTHETIC_TEMPLATE


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _dialog(destroy_after):
    return destroy_after(
        PrimerDesignDialog(SYNTHETIC_TEMPLATE, PlasmidAssemblyController(SynBioState()))
    )


# ── The refusal, rather than an exception ──────────────────────────────


@pytest.mark.unit
@pytest.mark.parametrize("typed", ["q", "Q", "GAATTq", "qqq", "GAATTC!", "hello"])
def test_resolving_a_non_dna_tail_never_raises(app, destroy_after, typed):
    """Every one of these used to take the process down from a timer slot."""
    dialog = _dialog(destroy_after)
    dialog.fwd_overhang_edit.setText(typed)

    names, problem = dialog._resolve_tail(typed, "Forward 5' tail")

    assert names == ()
    assert problem, "a refused tail must explain itself, not fail silently"


@pytest.mark.unit
def test_the_debounced_refresh_survives_a_bad_keystroke(app, destroy_after):
    """The exact slot the debounce timer invokes."""
    dialog = _dialog(destroy_after)
    dialog.fwd_overhang_edit.setText("q")

    dialog._refresh_tail_enzymes()  # must not raise

    assert "not DNA bases" in dialog.fwd_enzyme_label.text()
    assert "Q" in dialog.fwd_enzyme_label.text(), "name the offending character"


@pytest.mark.unit
def test_a_good_tail_still_resolves_to_its_enzyme(app, destroy_after):
    """The fix must not cost the feature."""
    dialog = _dialog(destroy_after)
    dialog.fwd_overhang_edit.setText(ECORI_TAIL)

    dialog._refresh_tail_enzymes()

    assert "EcoRI" in dialog.fwd_enzyme_label.text()
    assert dialog._tail_problems()[0] == ""


@pytest.mark.unit
def test_an_empty_tail_is_not_a_problem(app, destroy_after):
    dialog = _dialog(destroy_after)
    dialog.fwd_overhang_edit.setText("")

    assert dialog._resolve_tail("", "Forward 5' tail") == ((), "")


@pytest.mark.unit
def test_design_refuses_a_bad_tail_instead_of_dropping_it(app, destroy_after):
    """Primers without the tail the student typed would be the wrong answer."""
    dialog = _dialog(destroy_after)
    dialog.fwd_overhang_edit.setText("q")

    dialog._on_design_clicked()

    assert dialog.candidate_table.rowCount() == 0
    assert "not DNA bases" in dialog.input_problem.text()


# ── The process must stay alive ────────────────────────────────────────

_CRASH_HARNESS = textwrap.dedent(
    """
    import sys, traceback
    sys.path.insert(0, "src")

    # The plugin UI daemon's excepthook, verbatim from ui_daemon.py: this is
    # what turns an escaped slot exception into a dead application.
    def global_exception_handler(exctype, value, tb):
        traceback.print_exception(exctype, value, tb)
        sys.exit(1)
    sys.excepthook = global_exception_handler

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
    from karcytics_plugins.synthetic_biology.ui.controllers.plasmid_controller import (
        PlasmidAssemblyController,
    )
    from karcytics_plugins.synthetic_biology.ui.views.plasmid_assembly_view import (
        PrimerDesignDialog,
    )

    app = QApplication([])
    dialog = PrimerDesignDialog("ATGACGTACGTACGTACGTACGTACGTACGTACGTACGTA" * 4,
                                PlasmidAssemblyController(SynBioState()))

    # Type it the way a student does, and let the real debounce timer fire.
    dialog.fwd_overhang_edit.setText("q")
    QTimer.singleShot(1200, app.quit)
    app.exec()
    print("SURVIVED")
    """
)


@pytest.mark.unit
def test_the_process_survives_the_keystroke_that_killed_it(tmp_path):
    """End to end, through the real debounce timer and the daemon's excepthook.

    Run out of process on purpose: in-process the exception would merely fail
    a test, which is not what the bug was. The bug was ``sys.exit(1)``.
    """
    script = tmp_path / "harness.py"
    script.write_text(_CRASH_HARNESS)

    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        cwd=os.getcwd(),
    )

    assert proc.returncode == 0, (
        f"typing 'q' into a tail box killed the process "
        f"(exit {proc.returncode}).\nstderr:\n{proc.stderr}"
    )
    assert "SURVIVED" in proc.stdout
    assert "SequenceRejectedError" not in proc.stderr

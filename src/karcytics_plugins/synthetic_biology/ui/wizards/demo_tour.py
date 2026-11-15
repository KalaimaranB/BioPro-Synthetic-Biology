"""Presenter-driven guided tour of the Synthetic Biology demo.

A step bar that sits above the workspace and walks a presenter through the demo
in a fixed order, switching tabs and firing each simulation as its step is
reached. The presenter clicks Next, so the tour never runs ahead of a question
from the audience.

This is deliberately not the SDK Academy overlay. The Academy teaches a user by
validating what they did — it has mascots, per-step validators and highlight
geometry, and it waits on the learner. A demo tour is the inverse: the operator
already knows the material and wants the app to move itself while they talk, so
a step list with Back / Next is the whole requirement.

The steps carry the narration verbatim so the on-screen prompt and the written
run-sheet cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from karcytics_sdk.plugin.components import SecondaryButton
from karcytics_sdk.plugin.theme_fallback import Colors, Fonts, theme_manager
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class TourStep:
    """One stop on the tour."""

    title: str
    narration: str
    tab_index: int
    # Run against the main panel when the step is entered — switch a solver,
    # press Run, retune a parameter. Kept as a callable so the step list stays
    # declarative and the panel wiring lives in one place.
    action: Callable[[object], None] | None = field(default=None, compare=False)


class DemoTourBar(QFrame):
    """A step banner with Back / Next / Exit, shown while a tour is running."""

    step_changed = Signal(int)
    tour_finished = Signal()

    def __init__(self, steps: list[TourStep], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DemoTourBar")
        self._steps = steps
        self._index = 0
        self._setup_ui()
        self._apply_theme()
        theme_manager.theme_changed.connect(self._apply_theme)

    def _setup_ui(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 10)
        outer.setSpacing(12)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        self.step_label = QLabel()
        self.step_label.setObjectName("TourStepTitle")

        self.narration_label = QLabel()
        self.narration_label.setObjectName("TourNarration")
        self.narration_label.setWordWrap(True)

        text_box.addWidget(self.step_label)
        text_box.addWidget(self.narration_label)
        outer.addLayout(text_box, 1)

        self.btn_back = SecondaryButton("◀ Back", self)
        self.btn_back.clicked.connect(self.previous_step)

        self.btn_next = SecondaryButton("Next ▶", self)
        self.btn_next.clicked.connect(self.next_step)

        self.btn_exit = SecondaryButton("Exit tour", self)
        self.btn_exit.clicked.connect(self._on_exit)

        for btn in (self.btn_back, self.btn_next, self.btn_exit):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            outer.addWidget(btn)

        self._refresh()

    # -- navigation ----------------------------------------------------------

    @property
    def current_index(self) -> int:
        return self._index

    @property
    def current_step(self) -> TourStep | None:
        if 0 <= self._index < len(self._steps):
            return self._steps[self._index]
        return None

    def start(self) -> None:
        """Show the first step from the beginning."""
        self._index = 0
        self.setVisible(True)
        self._refresh()
        self.step_changed.emit(self._index)

    def next_step(self) -> None:
        if self._index >= len(self._steps) - 1:
            self._on_exit()
            return
        self._index += 1
        self._refresh()
        self.step_changed.emit(self._index)

    def previous_step(self) -> None:
        if self._index <= 0:
            return
        self._index -= 1
        self._refresh()
        self.step_changed.emit(self._index)

    def _on_exit(self) -> None:
        self.setVisible(False)
        self.tour_finished.emit()

    def _refresh(self) -> None:
        step = self.current_step
        if step is None:
            return
        self.step_label.setText(f"Step {self._index + 1} of {len(self._steps)} — {step.title}")
        self.narration_label.setText(step.narration)
        self.btn_back.setEnabled(self._index > 0)
        self.btn_next.setText("Finish" if self._index == len(self._steps) - 1 else "Next ▶")

    # -- theming -------------------------------------------------------------

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"""
            QFrame#DemoTourBar {{
                background: {Colors.BG_DARK};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 6px;
            }}
            QLabel#TourStepTitle {{
                font-size: {Fonts.SIZE_NORMAL}px;
                font-weight: bold;
                color: {Colors.ACCENT_PRIMARY};
            }}
            QLabel#TourNarration {{
                font-size: {Fonts.SIZE_SMALL}px;
                color: {Colors.FG_SECONDARY};
            }}
        """)

    def refresh_styles(self) -> None:
        """Alias used by the panel's theme-update fan-out."""
        self._apply_theme()


# Tab indices on SynBioPanel's tab bar, named so a reordering of the bar is a
# one-line change here rather than a silent mis-navigation.
TAB_DESIGN = 0
TAB_PLASMID = 2
TAB_CIRCUIT_SIM = 4
TAB_SIMULATE = 7
TAB_DEMO = 10


def _run_circuit_sim(panel: object, hill_n: float | None = None) -> None:
    """Press Run on the Circuit Simulation tab, optionally retuning n first."""
    view = getattr(panel, "circuit_view", None)
    if view is None:
        return
    if hill_n is not None and hasattr(view, "hill_n_spin"):
        view.hill_n_spin.setValue(hill_n)
    if hasattr(view, "_on_run_sim_clicked"):
        view._on_run_sim_clicked()


def build_demo_tour_steps() -> list[TourStep]:
    """The demo, in the order the run-sheet tells it."""
    return [
        TourStep(
            title="What you are looking at",
            narration=(
                "Nothing on this tab is a mock-up. The feature table is the assembly "
                "engine's output for this construct, and the guide RNAs are real SpCas9 "
                "sites found in this lacI sequence."
            ),
            tab_index=TAB_DEMO,
        ),
        TourStep(
            title="The construct",
            narration=(
                "Twelve parts, three transcription units: promoter, RBS, coding sequence, "
                "terminator, three times over. A promoter governs every coding sequence "
                "after it until the next promoter or terminator — that rule is what turns "
                "a flat list of parts into a network."
            ),
            tab_index=TAB_DESIGN,
        ),
        TourStep(
            title="The plasmid",
            narration=(
                "The same construct as an annotated 3,302 bp circular map, exportable as "
                "GenBank. This is the bridge back to the bench — the thing a student "
                "would actually order."
            ),
            tab_index=TAB_PLASMID,
        ),
        TourStep(
            title="Predicted behaviour",
            narration=(
                "Three phase-shifted oscillations, period about 28 minutes, holding "
                "89% of their amplitude out to 400. Each gene represses the next in a "
                "ring of three: production follows a Hill function, scaled so a gene "
                "settles at the output level its parameters describe, and degradation "
                "is first-order. Note n = 3.5 is higher than real repressors provide — "
                "this one-species-per-gene reduction needs more cooperativity than the "
                "published two-species model."
            ),
            tab_index=TAB_CIRCUIT_SIM,
            action=lambda panel: _run_circuit_sim(panel, hill_n=3.5),
        ),
        TourStep(
            title="Below the threshold",
            narration=(
                "Same circuit, Hill coefficient dropped from 3.5 to 2.0 — the oscillation "
                "damps to flat. That is a Hopf bifurcation: below a threshold in "
                "cooperativity the ring settles to a steady state instead of cycling. "
                "This threshold is 2.4514, and 2.0 is not just under it — for a "
                "three-gene ring the loop gain can never exceed n, so at n = 2 no "
                "choice of any other parameter would make it cycle. One slider, a real "
                "dynamical-systems result."
            ),
            tab_index=TAB_CIRCUIT_SIM,
            action=lambda panel: _run_circuit_sim(panel, hill_n=2.0),
        ),
        TourStep(
            title="Back above it",
            narration=(
                "Restored to 3.5 and the cycle returns. The threshold is a property of "
                "the network, not of the solver."
            ),
            tab_index=TAB_CIRCUIT_SIM,
            action=lambda panel: _run_circuit_sim(panel, hill_n=3.5),
        ),
        TourStep(
            title="Molecule by molecule",
            narration=(
                "The same circuit under a stochastic Gillespie simulation, in molecule "
                "counts rather than concentrations. The period survives; the smooth "
                "curve does not. That difference is the point — it is what a "
                "deterministic model hides."
            ),
            tab_index=TAB_SIMULATE,
            action=lambda panel: panel._simulate_view.plot_time_series(  # type: ignore[attr-defined]
                max_time=400, method="gillespie"
            ),
        ),
        TourStep(
            title="The write-up",
            narration=(
                "Every analysis run in this workspace is logged with the parameters it "
                "used, and turned into a Materials & Methods paragraph with numbered "
                "references, each checked against Crossref. This is the draft a student "
                "needs for the Methods section and the final cloning report. Copy it, "
                "or export BibTeX."
            ),
            tab_index=TAB_CIRCUIT_SIM,
            action=lambda panel: panel.open_methods_dialog(),  # type: ignore[attr-defined]
        ),
        TourStep(
            title="Save and come back next week",
            narration=(
                "The whole workspace — construct, circuit, simulations, guides and the "
                "methods log — is saved into the Hub project as a workflow. Reopen it "
                "from the Hub's workflow list or the Open button and it comes back "
                "exactly as it was, so a design can carry across a multi-week project."
            ),
            tab_index=TAB_DESIGN,
            action=lambda panel: panel.save_demo_workspace(),  # type: ignore[attr-defined]
        ),
    ]

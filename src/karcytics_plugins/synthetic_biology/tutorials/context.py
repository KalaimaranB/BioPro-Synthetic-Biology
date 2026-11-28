"""What an Academy validator in this module is allowed to look at.

``PluginBase.academy_context()`` exists so a validator can ask what the user
is *looking at* without reaching into a widget's private attributes. The SDK
leaves the shape of that answer to the plugin; this is ours.

Why a frozen snapshot rather than the live panel
------------------------------------------------
A validator is polled on a timer while a step is on screen. Handing it the
panel would let a course read half-built widgets mid-signal, and would make
every course a consumer of private UI internals — so renaming a private
attribute in a view would silently break a lesson, with no test that notices.
A snapshot is built once per poll from public reads, and the fields below are
the entire contract between the views and the courses.

It is also what keeps ``tutorials/`` free of PySide6. A course and its
validators are declarative data plus pure predicates; only ``ui/`` knows what
a ``QDialog`` is. The panel builds this (see
``ui.main_panel.SynBioPanel.academy_context``), the course only reads it.

No Qt imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PrimerDialogSnapshot:
    """What the primer-design dialog is showing, if it is open at all.

    ``candidate_count`` is how many ranked pairs the table holds, and
    ``selected_index`` is the row the user has highlighted (``None`` for no
    selection). ``visible_tab`` is the dialog's own inner tab — one of
    ``"candidates"``, ``"amplification"`` or ``"gel"`` — because three lessons
    turn on the learner having actually looked at a particular one.
    """

    is_open: bool = False
    candidate_count: int = 0
    selected_index: int | None = None
    visible_tab: str = ""
    target_tm: float = 0.0
    has_forward_tail: bool = False
    has_reverse_tail: bool = False

    @property
    def has_candidates(self) -> bool:
        return self.candidate_count > 0

    @property
    def has_selection(self) -> bool:
        return self.selected_index is not None


@dataclass(frozen=True)
class SynBioAcademyContext:
    """The read-only view of the workspace that this module's courses get.

    ``active_tab_index`` indexes the main tab bar in ``ui.main_panel``; the
    plasmid course only ever cares that it is the Plasmid Assembly tab, which
    :attr:`on_plasmid_tab` answers so a course never hardcodes the number.
    """

    #: Index of the Plasmid Assembly tab in the main tab bar.
    PLASMID_TAB: int = 2

    active_tab_index: int = -1
    plasmid_name: str = ""
    plasmid_length_bp: int = 0
    plasmid_feature_count: int = 0
    plasmid_is_circular: bool = False
    sequence_viewer_has_text: bool = False
    import_notice_text: str = ""
    method_kinds: tuple[str, ...] = field(default_factory=tuple)
    primer_dialog: PrimerDialogSnapshot = field(default_factory=PrimerDialogSnapshot)

    @property
    def on_plasmid_tab(self) -> bool:
        return self.active_tab_index == self.PLASMID_TAB

    @property
    def has_plasmid(self) -> bool:
        return self.plasmid_length_bp > 0

    def recorded(self, kind: str) -> bool:
        """Whether the Methods log already holds a step of this kind.

        The kinds are ``citations.STEP_ORDER`` — ``"primer_design"``,
        ``"amplification"``, ``"gel_migration"`` and so on — so a step can
        verify the learner's action reached the Methods log, which is the only
        evidence that it was a real analysis and not a redrawn view.
        """
        return kind in self.method_kinds

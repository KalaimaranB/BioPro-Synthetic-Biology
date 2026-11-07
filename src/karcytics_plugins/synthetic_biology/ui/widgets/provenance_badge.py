"""Shows where a displayed number came from, in the engine's own words.

The three-way distinction — a published value, our own convention, or our
threshold resting on a published mechanism — is the honesty of the whole tool,
and it is worthless if it only exists in the source. This widget is how it
reaches the screen.

It decides nothing. The label text, the explanation and the citation keys are
all read off :class:`analysis.provenance.Provenance` (or off a ``RubricCheck``,
which carries the same fields). Colour is the only thing chosen here, and it is
chosen from the SDK theme by the engine's ``kind``, never by inspecting a value.
"""

from __future__ import annotations

from typing import Any

from karcytics_sdk.plugin.citation_widgets import CitationLabel
from karcytics_sdk.plugin.components import (
    BioCaptionLabel,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from karcytics_sdk.plugin.theme_fallback import Colors

# Imported for its registration side effect: this badge renders citation keys
# through the SDK registry, which raises on an unknown key. Importing the
# module here means a badge can never be built before the works it names are
# registered, whatever order the rest of the UI happens to load in.
from ...analysis import citations as _citations  # noqa: F401

#: Engine ``kind`` -> theme colour token. The only mapping this module owns.
#: A convention is not an error, so it is informational rather than a warning;
#: what would be wrong is showing it as if it were a measured result.
_KIND_COLOUR = {
    "sourced": "ACCENT_SUCCESS",
    "convention": "ACCENT_WARNING",
    "mixed": "FG_SECONDARY",
    "": "FG_SECONDARY",
}


def _colour_for(kind: str) -> str:
    return getattr(Colors, _KIND_COLOUR.get(kind, "FG_SECONDARY"), Colors.FG_SECONDARY)


class ProvenanceBadge(QWidget):
    """A one-line badge naming the provenance of a value, with its citations.

    Args:
        label: The phrase to show, from ``Provenance.label()`` or
            ``RubricCheck.provenance_label``. Never composed here.
        kind: ``sourced`` / ``convention`` / ``mixed``, used only to pick a colour.
        mechanism: Citation keys for the rule's shape. When present the badge
            shows them inline, so a student sees the paper behind the rule
            without opening the methods dialog.
        explanation: Tooltip text, the engine's own wording.
    """

    def __init__(
        self,
        label: str,
        kind: str = "",
        mechanism: tuple[str, ...] = (),
        explanation: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)

        if label:
            chip = QLabel(label)
            chip.setStyleSheet(f"color: {_colour_for(kind)}; font-style: italic;")
            if explanation:
                chip.setToolTip(explanation)
            row.addWidget(chip)

        if mechanism:
            # "Mechanism" rather than "Powered by": the papers support why the
            # rule has this shape, not the threshold that was chosen.
            row.addWidget(CitationLabel("", mechanism, prefix="Mechanism:"))

        row.addStretch()


class ProvenanceNote(QWidget):
    """A stacked label + explanation, for a panel header rather than a row."""

    def __init__(
        self,
        label: str,
        kind: str = "",
        mechanism: tuple[str, ...] = (),
        explanation: str = "",
        mechanism_claim: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(ProvenanceBadge(label, kind, mechanism, explanation))
        for text in (explanation, mechanism_claim):
            if text:
                caption = BioCaptionLabel(text)
                caption.setWordWrap(True)
                column.addWidget(caption)


def badge_for(entry: Any, parent: QWidget | None = None) -> ProvenanceBadge:
    """Build a badge from a ``Provenance`` record, reading its own fields."""
    return ProvenanceBadge(
        label=entry.label(),
        kind=entry.kind,
        mechanism=tuple(entry.mechanism),
        explanation=entry.explanation,
        parent=parent,
    )


def badge_for_check(check: Any, parent: QWidget | None = None) -> ProvenanceBadge:
    """Build a badge from a ``RubricCheck``, which carries the same fields."""
    return ProvenanceBadge(
        label=getattr(check, "provenance_label", ""),
        kind=getattr(check, "provenance", ""),
        mechanism=tuple(getattr(check, "mechanism", ()) or ()),
        parent=parent,
    )


__all__ = ["ProvenanceBadge", "ProvenanceNote", "badge_for", "badge_for_check"]

"""Draws the lanes :mod:`analysis.assembly.gel` produces.

Mobility is **read off the band objects**, never recomputed here. The engine
already places every band on the gel's own resolving window — and a bug was
caught there where a lane kept a stale window and its positions disagreed with
the axis the gel advertised. Recomputing in the view would reintroduce exactly
that class of disagreement, and the view has no business knowing the equation
anyway.

``band.relative_mobility`` is 0 at the well and 1 at the far end, so the only
arithmetic here is multiplying it by the pixel height of the lane.

What the model does not do is shown alongside, not buried: a student comparing
this to a real gel needs to know that methylation sensitivity, star activity,
partial digestion and isoschizomers are not modelled, and that the log-linear
mobility form is a convention.
"""

from __future__ import annotations

from typing import Any

from karcytics_sdk.plugin.citation_widgets import CitationLabel
from karcytics_sdk.plugin.components import (
    BioCaptionLabel,
    BioScrollArea,
    BioSectionLabel,
    Qt,
    QVBoxLayout,
    QWidget,
)
from karcytics_sdk.plugin.theme_fallback import Colors, Fonts
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen

_LANE_WIDTH = 86
#: Room to the right of each lane for its band size labels.
_LABEL_GUTTER = 68
_LANE_GAP = 20
_TOP = 34
_BOTTOM = 26
_BAND_HEIGHT = 5

#: A soft floor only. Small enough that this view's layout minimum stays
#: under what the dialog actually allots, so the captions can never be laid
#: over the canvas; the gel grows past it via the stretch factor.
_MIN_GEL_HEIGHT = 140

#: Lane kind -> theme token for its label.
_KIND_COLOUR = {
    "ladder": "FG_SECONDARY",
    "pcr_product": "ACCENT_PRIMARY",
    "digest": "ACCENT_SUCCESS",
}


class _GelCanvas(QWidget):
    """The painted gel. One lane per column, bands placed by relative mobility."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lanes: list[Any] = []
        # Kept under the scroll area's own floor so the canvas expands to fill
        # the viewport rather than forcing a scrollbar: a PCR product runs near
        # the bottom of the gel and must not start out below the fold.
        self.setMinimumHeight(130)

    def set_lanes(self, lanes: list[Any]) -> None:
        self._lanes = list(lanes or [])
        # Each lane needs its own width plus a gutter for the size labels
        # drawn beside it, or the right-hand lane's labels are clipped.
        per_lane = _LANE_WIDTH + _LABEL_GUTTER + _LANE_GAP
        self.setMinimumWidth(max(_LANE_GAP + len(self._lanes) * per_lane, 240))
        self.update()

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            self._paint(painter)
        finally:
            painter.end()

    def _paint(self, painter: QPainter) -> None:
        if not self._lanes:
            return

        gel_top, gel_bottom = _TOP, self.height() - _BOTTOM
        lane_height = max(gel_bottom - gel_top, 1)

        painter.setBrush(QBrush(QColor(Colors.BG_DARKEST)))
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.drawRect(QRectF(0, gel_top, self.width(), lane_height))

        font = QFont()
        font.setPointSize(Fonts.SIZE_SMALL)
        painter.setFont(font)

        for index, lane in enumerate(self._lanes):
            x = _LANE_GAP + index * (_LANE_WIDTH + _LABEL_GUTTER + _LANE_GAP)
            self._draw_lane(painter, lane, x, gel_top, lane_height)

    def _draw_lane(
        self, painter: QPainter, lane: Any, x: float, gel_top: float, lane_height: float
    ) -> None:
        kind = getattr(lane, "kind", "sample")
        colour = QColor(getattr(Colors, _KIND_COLOUR.get(kind, "FG_PRIMARY"), Colors.FG_PRIMARY))

        painter.setPen(QPen(QColor(Colors.FG_SECONDARY), 1))
        # Elided rather than clipped: "1 kb Plus DNA ladder" does not fit a
        # lane's width, and a half-drawn name reads as a different ladder.
        metrics = painter.fontMetrics()
        name = metrics.elidedText(
            lane.name, Qt.TextElideMode.ElideRight, _LANE_WIDTH + _LABEL_GUTTER
        )
        painter.drawText(
            QRectF(x, 6, _LANE_WIDTH + _LABEL_GUTTER, 20), int(Qt.AlignmentFlag.AlignLeft), name
        )

        # The well.
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.setBrush(QBrush(QColor(Colors.BG_MEDIUM)))
        painter.drawRect(QRectF(x, gel_top + 2, _LANE_WIDTH, 4))

        for band in getattr(lane, "bands", ()) or ():
            # Straight from the engine. No mobility maths in the view.
            y = gel_top + band.relative_mobility * lane_height
            alpha = int(60 + 195 * max(0.0, min(1.0, band.intensity)))
            fill = QColor(colour)
            fill.setAlpha(alpha)

            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(fill.darker(130), 1))
            painter.drawRect(QRectF(x, y, _LANE_WIDTH, _BAND_HEIGHT))

            painter.setPen(QPen(QColor(Colors.FG_SECONDARY), 1))
            label = band.label or f"{band.size_bp} bp"
            if band.out_of_range:
                # Clamped, so its position is not a measurement.
                label += " *"
            painter.drawText(QPointF(x + _LANE_WIDTH + 4, y + _BAND_HEIGHT), label)


class GelView(QWidget):
    """A gel plus the limitations that belong beside any predicted gel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)

        self.heading = BioSectionLabel("Predicted gel")
        column.addWidget(self.heading)

        self.canvas = _GelCanvas()
        scroll = BioScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        # No hard floor here. A floor of 340 px made this layout's minimum
        # 450 px; inside the real dialog the tab allots 393 px, Qt could not
        # satisfy the minimums, and it laid the captions ON TOP of the canvas
        # -- the bands were not escaping their box, the captions were being
        # drawn over them. The gel is the stretch item instead, so it takes
        # whatever is left after the captions have their (small) natural
        # height, and it scrolls when that is tight.
        scroll.setMinimumHeight(_MIN_GEL_HEIGHT)
        column.addWidget(scroll, stretch=1)

        self.model_note = BioCaptionLabel("")
        self.model_note.setWordWrap(True)
        column.addWidget(self.model_note)

        self.limitations = BioCaptionLabel("")
        self.limitations.setWordWrap(True)
        self.limitations.setStyleSheet(f"color: {Colors.ACCENT_WARNING};")
        column.addWidget(self.limitations)

        from ...analysis.citations import FEATURE_CITATIONS

        column.addWidget(
            CitationLabel("Gel model", FEATURE_CITATIONS["gel_migration"], prefix="Based on")
        )

    def show_gel(self, gel: Any) -> None:
        """Render a ``Gel``. Mobility and intensity come from its bands."""
        self.canvas.set_lanes(list(getattr(gel, "lanes", ()) or ()))
        self.heading.setText(
            f"Predicted gel — {getattr(gel, 'min_bp', '')}-{getattr(gel, 'max_bp', '')} bp window"
        )
        self._show_model_basis(gel)
        self._show_limitations()

    def _show_model_basis(self, gel: Any) -> None:
        """State at the point of display that the mobility form is a convention."""
        from ...analysis.assembly.gel import THRESHOLD_PROVENANCE

        entry = THRESHOLD_PROVENANCE["mobility_model"]
        lines = [
            f"Mobility model: {getattr(gel, 'model', '')} ({entry.label()}).",
            entry.explanation,
        ]
        notes = list(getattr(gel, "notes", ()) or ())
        lines.extend(notes)
        self.model_note.setText(" ".join(lines))

    def _show_limitations(self) -> None:
        """DIGEST_LIMITATIONS belongs beside the gel, not in a methods dialog."""
        from ...analysis.assembly.restriction import DIGEST_LIMITATIONS

        names = ", ".join(name for name, _ in DIGEST_LIMITATIONS)
        self.limitations.setText(
            f"Not modelled: {names}. A real gel can differ from this for any of those reasons."
        )
        self.limitations.setToolTip(
            "\n\n".join(f"{name}: {reason}" for name, reason in DIGEST_LIMITATIONS)
        )

    def clear(self) -> None:
        self.canvas.set_lanes([])
        self.heading.setText("Predicted gel")
        self.model_note.setText("")
        self.limitations.setText("")


__all__ = ["GelView"]

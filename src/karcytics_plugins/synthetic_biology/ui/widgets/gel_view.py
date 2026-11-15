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
from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen

from ...analysis.assembly.gel import DEFAULT_MAX_BP, DEFAULT_MIN_BP

_LANE_WIDTH = 86
#: Room to the right of each lane for its band size labels.
_LABEL_GUTTER = 68
_LANE_GAP = 20
#: Space above the resolving area for the lane name, the well slot and an
#: off-scale marker, which previously collided with the lane name.
_TOP = 58
_BOTTOM = 26
_BAND_HEIGHT = 5

#: Minimum vertical gap between two band labels, in px. Below this they
#: overlap and neither is readable.
_MIN_LABEL_GAP = 14

#: Height of the drawn well slot, above the resolving area.
_WELL_HEIGHT = 5

#: Vertical step between stacked off-scale markers, in px.
_OFF_SCALE_STEP = 13

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

    #: Emitted with (lane, band) when a band is clicked.
    band_clicked = Signal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lanes: list[Any] = []
        self._min_bp = DEFAULT_MIN_BP
        self._max_bp = DEFAULT_MAX_BP
        #: Hit rectangles recorded while painting, so clicking uses exactly
        #: the geometry that was drawn rather than recomputing a position.
        self._hits: list[tuple[QRectF, Any, Any]] = []
        # Deliberately low. Raising it to 230 so the lane is roomier made the
        # canvas taller than the viewport on a 783 px dialog, and the PCR
        # product -- which runs near the bottom -- ended up below the fold
        # behind a scrollbar. Everything visible in a cramped gel beats a
        # roomier one you have to scroll to read.
        self.setMinimumHeight(130)

    def set_lanes(
        self, lanes: list[Any], min_bp: int = DEFAULT_MIN_BP, max_bp: int = DEFAULT_MAX_BP
    ) -> None:
        self._lanes = list(lanes or [])
        self._min_bp, self._max_bp = min_bp, max_bp
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
        self._hits = []
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

        # The well, drawn ABOVE the gel rather than just inside its top edge.
        # Inside, a filled 4 px bar at the very top of the window read as a
        # faint band at ~10 kb sitting above the real product — it was
        # reported as a stray fragment. It is now outside the resolving area
        # and outlined rather than filled, so it cannot be mistaken for DNA.
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(x, gel_top - _WELL_HEIGHT - 2, _LANE_WIDTH, _WELL_HEIGHT))

        last_label_y = float("-inf")
        off_scale_above = 0
        off_scale_below = 0
        for band in getattr(lane, "bands", ()) or ():
            # Straight from the engine. No mobility maths in the view.
            y = gel_top + band.relative_mobility * lane_height
            if band.out_of_range:
                # Drawing it at the clamped edge invents a position. An arrow
                # outside the gel says "off scale" without implying a size.
                if band.off_scale_high:
                    self._draw_off_scale(
                        painter, band, x, gel_top, lane_height, colour, off_scale_above
                    )
                    off_scale_above += 1
                else:
                    self._draw_off_scale(
                        painter, band, x, gel_top, lane_height, colour, off_scale_below
                    )
                    off_scale_below += 1
                continue
            alpha = int(60 + 195 * max(0.0, min(1.0, band.intensity)))
            fill = QColor(colour)
            fill.setAlpha(alpha)

            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(fill.darker(130), 1))
            rect = QRectF(x, y, _LANE_WIDTH, _BAND_HEIGHT)
            painter.drawRect(rect)
            # A band is only a few pixels tall; widen the hit area so it can
            # actually be clicked.
            self._hits.append((rect.adjusted(0, -4, 0, 4), lane, band))

            # Label only where there is room. A 16-band ladder in a short lane
            # cannot carry 16 labels: drawing them all put the text on top of
            # itself and made every size unreadable. The band is still drawn;
            # it is the label that is dropped, and clicking still identifies it.
            if y - last_label_y >= _MIN_LABEL_GAP:
                painter.setPen(QPen(QColor(Colors.FG_SECONDARY), 1))
                label = band.label or f"{band.size_bp} bp"
                if band.out_of_range:
                    # Clamped, so its position is not a measurement.
                    label += " *"
                painter.drawText(QPointF(x + _LANE_WIDTH + 4, y + _BAND_HEIGHT), label)
                last_label_y = y

    def _draw_off_scale(  # noqa: PLR0913 - position, colour and stacking index
        self,
        painter: QPainter,
        band: Any,
        x: float,
        gel_top: float,
        lane_height: float,
        colour: QColor,
        index: int = 0,
    ) -> None:
        """Mark a fragment the gel cannot resolve, without placing a band.

        Stacked by ``index`` so several fragments off the same end stay
        readable -- an 813 bp product cut with two enzymes leaves 1 bp and
        5 bp, and both markers were printed at the same y -- and elided to
        the lane's own column so a long marker does not run across its
        neighbour.
        """
        # The engine decides which edge; the view only draws it.
        above = band.off_scale_high
        step = index * _OFF_SCALE_STEP
        y = (gel_top - 6 - step) if above else (gel_top + lane_height + 14 + step)
        arrow = "\u25b2" if above else "\u25bc"
        bound = f">{self._max_bp}" if above else f"<{self._min_bp}"

        width = _LANE_WIDTH + _LABEL_GUTTER
        text = painter.fontMetrics().elidedText(
            f"{arrow} {band.size_bp} bp off scale ({bound} bp)",
            Qt.TextElideMode.ElideRight,
            int(width),
        )
        painter.setPen(QPen(colour, 1))
        painter.drawText(QPointF(x, y), text)
        self._hits.append((QRectF(x, y - 12, width, 16), self._lane_of(band), band))

    def _lane_of(self, band: Any) -> Any:
        for lane in self._lanes:
            if band in getattr(lane, "bands", ()):
                return lane
        return None

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 - Qt override
        """Select the band under the cursor, if any."""
        point = event.position()
        for rect, lane, band in self._hits:
            if rect.contains(point):
                self.band_clicked.emit(lane, band)
                return
        super().mousePressEvent(event)


class GelView(QWidget):
    """A gel plus the limitations that belong beside any predicted gel."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)

        self.heading = BioSectionLabel("Predicted gel")
        column.addWidget(self.heading)

        self.canvas = _GelCanvas()
        self.canvas.band_clicked.connect(self._on_band_clicked)
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

        self.legend = BioCaptionLabel(
            "\u2605 = high-intensity reference band.  "
            "* = at the edge of the resolving window; position approximate.  "
            "\u25b2/\u25bc = off scale, size shown but not positioned."
        )
        self.legend.setWordWrap(True)
        column.addWidget(self.legend)

        self.selection_note = BioCaptionLabel("Click a band to identify it.")
        self.selection_note.setWordWrap(True)
        column.addWidget(self.selection_note)

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

    #: Re-emitted so a container can react without reaching into the canvas.
    band_selected = Signal(object, object)

    def _on_band_clicked(self, lane: Any, band: Any) -> None:
        """Describe the clicked band, reading only what the engine put on it."""
        label = band.label or f"{band.size_bp} bp"
        reference = band.is_reference
        if lane.kind == "ladder":
            sentence = f"The {label} band of the {lane.name}"
            sentence += (
                " is the high-intensity reference band, loaded heavier as an orientation marker."
                if reference
                else " is a size standard."
            )
        else:
            sentence = f"{label} is a predicted fragment in the {lane.name} lane."

        parts = [sentence]
        if band.out_of_range:
            parts.append(
                "It falls outside the gel's resolving window, so it is shown "
                "off scale: its size is known but this gel cannot place it."
            )
        elif band.at_edge:
            parts.append(
                "It sits exactly on the edge of the resolving window, so its "
                "position is approximate."
            )
        provenance = getattr(lane, "provenance", "")
        if provenance:
            parts.append(provenance)
        self.selection_note.setText(" ".join(parts))
        self.band_selected.emit(lane, band)

    def show_gel(self, gel: Any) -> None:
        """Render a ``Gel``. Mobility and intensity come from its bands."""
        self.canvas.set_lanes(
            list(getattr(gel, "lanes", ()) or ()),
            getattr(gel, "min_bp", DEFAULT_MIN_BP),
            getattr(gel, "max_bp", DEFAULT_MAX_BP),
        )
        self.heading.setText(
            f"Predicted gel — {getattr(gel, 'min_bp', '')}-{getattr(gel, 'max_bp', '')} bp window"
        )
        self._show_model_basis(gel)
        self._show_limitations(gel)

    def _show_model_basis(self, gel: Any) -> None:
        """State at the point of display that the mobility form is a convention."""
        from ...analysis.assembly.gel import THRESHOLD_PROVENANCE

        entry = THRESHOLD_PROVENANCE["mobility_model"]
        notes = list(getattr(gel, "notes", ()) or ())
        # One visible line, full reasoning on hover. The label must still say
        # "our convention" at the point of display -- that is the rule -- but
        # a four-line paragraph here was taking the room the gel needs.
        headline = f"Mobility model: {getattr(gel, 'model', '')} ({entry.label()})."
        if notes:
            headline += " " + notes[0]
        self.model_note.setText(headline)
        self.model_note.setToolTip(" ".join([entry.explanation, *notes]))

    def _show_limitations(self, gel: Any) -> None:
        """The caveats that apply to THIS gel, beside it rather than buried.

        A PCR-only gel used to show the restriction-digest caveats --
        methylation sensitivity, star activity, isoschizomers -- which say
        nothing about a PCR and left its real failure modes unmentioned. The
        engine picks the set from the lane kinds actually present.
        """
        limitations = getattr(gel, "limitations", ())
        names = ", ".join(name for name, _ in limitations)
        self.limitations.setText(
            f"Not modelled: {names}. A real gel can differ from this for any of those reasons."
        )
        self.limitations.setToolTip(
            "\n\n".join(f"{name}: {reason}" for name, reason in limitations)
        )

    def clear(self) -> None:
        self.canvas.set_lanes([])
        self.heading.setText("Predicted gel")
        self.model_note.setText("")
        self.limitations.setText("")


__all__ = ["GelView"]

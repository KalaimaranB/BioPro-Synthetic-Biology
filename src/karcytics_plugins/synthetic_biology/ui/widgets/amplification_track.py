"""Draws the template, where the primers land, and what comes off it.

Everything drawn is read off the ``AmplificationResult`` the engine returns:
binding-site coordinates, strand, amplicon spans, product lengths, restriction
sites and their region labels, and the outcome. This widget computes no
biology. The only arithmetic here is turning a base index into a pixel, which
is scaling, not science.

The failure modes are drawn rather than raised. No product, several products
and primer-dimer are the teaching content of the exercise — a student who sees
two amplicons has learned that their primers are not unique, which an error
dialog would have hidden.
"""

from __future__ import annotations

from typing import Any

from karcytics_sdk.plugin.components import (
    BioCaptionLabel,
    BioSectionLabel,
    Qt,
    QVBoxLayout,
    QWidget,
)
from karcytics_sdk.plugin.theme_fallback import Colors
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF

#: Outcome -> theme token, for the headline. The engine decides the outcome.
_OUTCOME_COLOUR = {
    "product": "ACCENT_SUCCESS",
    "multiple_products": "ACCENT_WARNING",
    "no_product": "ACCENT_DANGER",
    "primer_dimer": "ACCENT_DANGER",
}

_OUTCOME_TITLE = {
    "product": "One product",
    "multiple_products": "Multiple products",
    "no_product": "No product",
    "primer_dimer": "Primer-dimer only",
}

#: Region label from the engine -> whether the site came from a tail.
#: A site the tails introduced is the point of the exercise; one already in the
#: template is a hazard. They must not look alike.
_TAIL_REGIONS = ("forward_tail", "reverse_tail", "tail_insert_junction")

_MARGIN = 46
_TRACK_HEIGHT = 16
_ROW_HEIGHT = 74
_ARROW_HEIGHT = 11

#: Smallest drawable feature widths, so a short primer or amplicon stays visible.
_MIN_ARROW_PX = 6
_MIN_SPAN_PX = 4


class _TrackCanvas(QWidget):
    """The painted surface. Separated so the panel can own labels and scrolling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._result: Any = None
        self._template_bp = 0
        self.setMinimumHeight(180)

    def set_result(self, result: Any, template_bp: int) -> None:
        self._result = result
        self._template_bp = max(int(template_bp or 0), 1)
        rows = 1 + max(len(getattr(result, "amplicons", ()) or ()), 1)
        self.setMinimumHeight(_MARGIN * 2 + rows * _ROW_HEIGHT)
        self.update()

    # ── Scaling ────────────────────────────────────────────────────────

    def _x(self, base: int) -> float:
        usable = max(self.width() - 2 * _MARGIN, 1)
        return _MARGIN + (base / self._template_bp) * usable

    # ── Painting ───────────────────────────────────────────────────────

    def paintEvent(self, event: Any) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            self._paint(painter)
        finally:
            painter.end()

    def _paint(self, painter: QPainter) -> None:
        if self._result is None:
            return

        top = _MARGIN
        self._draw_template(painter, top)
        self._draw_binding_sites(painter, top)

        amplicons = list(getattr(self._result, "amplicons", ()) or ())
        for index, amplicon in enumerate(amplicons):
            self._draw_amplicon(painter, top + (index + 1) * _ROW_HEIGHT, amplicon, index)

        if not amplicons:
            self._draw_absence(painter, top + _ROW_HEIGHT)

    def _draw_template(self, painter: QPainter, y: float) -> None:
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.setBrush(QBrush(QColor(Colors.BG_MEDIUM)))
        painter.drawRect(QRectF(_MARGIN, y, self.width() - 2 * _MARGIN, _TRACK_HEIGHT))

        painter.setPen(QPen(QColor(Colors.FG_SECONDARY), 1))
        painter.setFont(_small_font())
        # Clear of the forward-primer arrows, which sit directly above the track.
        painter.drawText(
            QPointF(_MARGIN, y - _ARROW_HEIGHT - 20), f"Template, {self._template_bp} bp"
        )

    def _draw_binding_sites(self, painter: QPainter, y: float) -> None:
        """Primers as directional arrows on the strand each anneals to."""
        for site in getattr(self._result, "forward_sites", ()) or ():
            self._draw_arrow(painter, site, y - _ARROW_HEIGHT - 3, forward=True)
        for site in getattr(self._result, "reverse_sites", ()) or ():
            self._draw_arrow(painter, site, y + _TRACK_HEIGHT + 3, forward=False)

    def _draw_arrow(self, painter: QPainter, site: Any, y: float, forward: bool) -> None:
        left, right = self._x(site.start), self._x(site.end)
        if right - left < _MIN_ARROW_PX:
            right = left + _MIN_ARROW_PX
        head = min(9.0, max(right - left, 1) / 2)

        colour = QColor(Colors.ACCENT_PRIMARY if forward else Colors.ACCENT_WARNING)
        painter.setPen(QPen(colour, 1))
        painter.setBrush(QBrush(colour))

        arrow = QPolygonF()
        if forward:
            arrow.append(QPointF(left, y))
            arrow.append(QPointF(right - head, y))
            arrow.append(QPointF(right, y + _ARROW_HEIGHT / 2))
            arrow.append(QPointF(right - head, y + _ARROW_HEIGHT))
            arrow.append(QPointF(left, y + _ARROW_HEIGHT))
        else:
            arrow.append(QPointF(right, y))
            arrow.append(QPointF(left + head, y))
            arrow.append(QPointF(left, y + _ARROW_HEIGHT / 2))
            arrow.append(QPointF(left + head, y + _ARROW_HEIGHT))
            arrow.append(QPointF(right, y + _ARROW_HEIGHT))
        painter.drawPolygon(arrow)

        painter.setFont(_small_font())
        painter.setPen(QPen(QColor(Colors.FG_SECONDARY), 1))
        # The engine already counted the mismatches; this only reports them.
        suffix = f" ({site.mismatches} mismatch)" if site.mismatches else ""
        anchor = y - 2 if forward else y + _ARROW_HEIGHT + 11
        painter.drawText(QPointF(left, anchor), f"{site.primer_name}{suffix}")

    def _draw_amplicon(self, painter: QPainter, y: float, amplicon: Any, index: int) -> None:
        left = self._x(amplicon.template_start)
        right = self._x(min(amplicon.template_end, self._template_bp))
        if right - left < _MIN_SPAN_PX:
            right = left + _MIN_SPAN_PX

        painter.setPen(QPen(QColor(Colors.ACCENT_SUCCESS), 1))
        painter.setBrush(QBrush(QColor(Colors.ACCENT_SUCCESS).lighter(140)))
        painter.drawRect(QRectF(left, y, right - left, _TRACK_HEIGHT))

        painter.setFont(_small_font())
        painter.setPen(QPen(QColor(Colors.FG_PRIMARY), 1))
        label = f"Product {index + 1}: {amplicon.length} bp, {amplicon.gc_percent:.1f}% GC"
        if getattr(amplicon, "wraps_origin", False):
            label += " (spans the origin)"
        painter.drawText(QPointF(self._label_x(painter, label, left), y - 5), label)

        self._draw_sites(painter, y, amplicon, left, right)

    def _label_x(self, painter: QPainter, text: str, preferred: float) -> float:
        """Keep a label inside the widget instead of letting it run off the edge."""
        width = painter.fontMetrics().horizontalAdvance(text)
        return max(2.0, min(preferred, self.width() - width - 4))

    def _draw_sites(
        self, painter: QPainter, y: float, amplicon: Any, left: float, right: float
    ) -> None:
        """Restriction sites, with tail-introduced ones marked distinctly."""
        sites = list(getattr(amplicon, "sites", ()) or ())
        if not sites:
            return
        span = max(amplicon.length, 1)
        for site in sites:
            from_tail = site.region in _TAIL_REGIONS
            x = left + (site.position / span) * max(right - left, 1)
            colour = QColor(Colors.ACCENT_PRIMARY if from_tail else Colors.ACCENT_DANGER)
            # Solid for a site the tails added, dashed for one already in the
            # template: the second is what would cut the insert.
            painter.setPen(
                QPen(colour, 2, Qt.PenStyle.SolidLine if from_tail else Qt.PenStyle.DashLine)
            )
            painter.drawLine(QPointF(x, y - 4), QPointF(x, y + _TRACK_HEIGHT + 10))

            painter.setFont(_small_font())
            painter.setPen(QPen(colour, 1))
            painter.drawText(QPointF(x + 3, y + _TRACK_HEIGHT + 22), site.enzyme)

    def _draw_absence(self, painter: QPainter, y: float) -> None:
        """A result, not an error: say what happened and leave the track empty."""
        outcome = getattr(self._result, "outcome", "")
        painter.setFont(_small_font())
        painter.setPen(
            QPen(QColor(getattr(Colors, _OUTCOME_COLOUR.get(outcome, "FG_SECONDARY"))), 1)
        )
        painter.drawText(QPointF(_MARGIN, y + _TRACK_HEIGHT), _OUTCOME_TITLE.get(outcome, outcome))


def _small_font() -> QFont:
    font = QFont()
    from karcytics_sdk.plugin.theme_fallback import Fonts

    font.setPointSize(Fonts.SIZE_SMALL)
    return font


class AmplificationTrack(QWidget):
    """The amplification view: a template track plus the engine's own notes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)

        self.heading = BioSectionLabel("Amplification")
        column.addWidget(self.heading)

        self.canvas = _TrackCanvas()
        column.addWidget(self.canvas)

        self.notes = BioCaptionLabel("")
        self.notes.setWordWrap(True)
        column.addWidget(self.notes)

        self.legend = BioCaptionLabel(
            "Arrows show primer binding: forward above the template, reverse below. "
            "Solid vertical lines are restriction sites the primer tails introduce; "
            "dashed lines are sites already present in the amplified region."
        )
        self.legend.setWordWrap(True)
        column.addWidget(self.legend)

    def show_result(self, result: Any, template_bp: int) -> None:
        """Render an ``AmplificationResult``. Nothing is recomputed."""
        outcome = getattr(result, "outcome", "")
        token = _OUTCOME_COLOUR.get(outcome, "FG_PRIMARY")
        self.heading.setText(f"Amplification — {_OUTCOME_TITLE.get(outcome, outcome)}")
        self.heading.setStyleSheet(f"color: {getattr(Colors, token, Colors.FG_PRIMARY)};")

        self.canvas.set_result(result, template_bp)
        # The engine writes the explanation; the view does not compose one.
        self.notes.setText("\n".join(getattr(result, "notes", ()) or ()))

    def clear(self) -> None:
        self.heading.setText("Amplification")
        self.heading.setStyleSheet("")
        self.canvas.set_result(None, 1)
        self.notes.setText("")


__all__ = ["AmplificationTrack"]

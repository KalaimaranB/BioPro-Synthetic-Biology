"""QGraphicsView for rendering SBOLv style genetic circuits."""

import hashlib
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
)

from ...analysis.parts.components import (
    CDS,
    RBS,
    Promoter,
    Terminator,
    Insulator,
    sgRNA,
)


class CircuitCanvas(QGraphicsView):
    """Central workspace canvas for the biological diagram."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(self.renderHints().Antialiasing)

        # Basic styling
        self.setBackgroundBrush(QBrush(QColor("#1e1e1e")))  # Dark theme background
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._parts = []

        # Font for labels
        self._font = QFont("Inter", 10)

        # Colors
        self.c_promoter = QColor("#2ecc71")
        self.c_rbs = QColor("#9b59b6")
        self.c_cds = QColor("#e74c3c")
        self.c_terminator = QColor("#e67e22")
        self.c_insulator = QColor("#f1c40f")
        self.c_sgrna = QColor("#1abc9c")
        self.c_backbone = QColor("#666666")
        self.c_text = QColor("#ffffff")

        self.render_circuit()

    def add_part(self, part):
        """Add a fetched part to the canvas."""
        self._parts.append(part)
        self.render_circuit()

    def render_circuit(self):
        """Render all parts along the DNA strand with SBOLv compliant graphics."""
        self.scene.clear()

        if not self._parts:
            # Draw empty backbone
            self.scene.addLine(-500, 0, 500, 0, QPen(self.c_backbone, 3))
            return

        # Pre-calculate precise text widths using actual QGraphicsTextItem measurements
        part_widths = []
        for part in self._parts:
            temp_text = self.scene.addText(part.name, self._font)
            tw = temp_text.boundingRect().width()
            self.scene.removeItem(temp_text)
            # Ensure a minimum of 100 pixels, plus 20px padding around text
            part_widths.append(max(100, tw + 20))

        total_width = sum(part_widths)
        start_x = -total_width / 2
        self.scene.addLine(
            start_x - 50, 0, start_x + total_width + 50, 0, QPen(self.c_backbone, 3)
        )

        part_positions = {}  # Map part index to cx

        x_offset = start_x
        for i, part in enumerate(self._parts):
            w = part_widths[i]

            if isinstance(part, Promoter):
                cx = self._draw_promoter(x_offset, part.name, w)
            elif isinstance(part, RBS):
                cx = self._draw_rbs(x_offset, part.name, w)
            elif isinstance(part, CDS):
                cx = self._draw_cds(x_offset, part.name, w)
            elif isinstance(part, Terminator):
                cx = self._draw_terminator(x_offset, part.name, w)
            elif isinstance(part, Insulator):
                cx = self._draw_insulator(x_offset, part.name, w)
            elif isinstance(part, sgRNA):
                cx = self._draw_sgrna(x_offset, part.name, w)
            else:
                cx = self._draw_generic(x_offset, part.name, w)

            part_positions[i] = cx

            x_offset += w

        # Draw Chemical Connections (Repression Lines)
        # Find all CDS products
        cds_map = {}  # product_name -> cx
        for i, part in enumerate(self._parts):
            if isinstance(part, CDS):
                product = getattr(part, "product", part.name.replace(" ", "_"))
                cds_map[product] = part_positions[i]
            elif isinstance(part, sgRNA):
                # sgRNA also acts as a repressor product
                cds_map[part.name] = part_positions[i]

        # Draw connections to promoters
        for i, part in enumerate(self._parts):
            if isinstance(part, Promoter):
                repressors = getattr(part, "repressors", [])
                for rep in repressors:
                    if rep in cds_map:
                        color = self._get_color_for_repressor(rep)
                        self._draw_repression_line(
                            cds_map[rep], part_positions[i], color
                        )

    def _get_color_for_repressor(self, rep: str) -> QColor:
        """Deterministically generate a vibrant color based on a string hash."""
        hash_val = int(hashlib.md5(rep.encode()).hexdigest(), 16)
        hue = hash_val % 360
        # h, s, l, a
        return QColor.fromHsl(hue, 200, 150)

    def _draw_promoter(self, x: float, name: str, cell_w: float):
        """Draw SBOLv bent arrow."""
        path = QPainterPath()
        cx = x + cell_w / 2 - 12
        path.moveTo(cx, 0)
        path.lineTo(cx, -40)
        path.lineTo(cx + 25, -40)

        item = QGraphicsPathItem(path)
        item.setPen(QPen(self.c_promoter, 3))
        self.scene.addItem(item)

        arrow = QPolygonF(
            [QPointF(cx + 25, -45), QPointF(cx + 35, -40), QPointF(cx + 25, -35)]
        )
        arrow_item = QGraphicsPolygonItem(arrow)
        arrow_item.setBrush(QBrush(self.c_promoter))
        arrow_item.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(arrow_item)

        text = self.scene.addText(name, self._font)
        text.setDefaultTextColor(self.c_text)
        tw = text.boundingRect().width()
        text.setPos(x + (cell_w - tw) / 2, 25)
        return cx

    def _draw_rbs(self, x: float, name: str, cell_w: float):
        """Draw SBOLv semi-circle."""
        path = QPainterPath()
        cx = x + cell_w / 2 - 15
        path.arcMoveTo(cx, -15, 30, 30, 0)
        path.arcTo(cx, -15, 30, 30, 0, 180)

        item = QGraphicsPathItem(path)
        item.setBrush(QBrush(self.c_rbs))
        item.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(item)

        text = self.scene.addText(name, self._font)
        text.setDefaultTextColor(self.c_text)
        tw = text.boundingRect().width()
        text.setPos(x + (cell_w - tw) / 2, -40)
        return cx

    def _draw_cds(self, x: float, name: str, cell_w: float):
        """Draw SBOLv block arrow."""
        cx = x + cell_w / 2 - 40
        poly = QPolygonF(
            [
                QPointF(cx, -15),
                QPointF(cx + 60, -15),
                QPointF(cx + 80, 0),
                QPointF(cx + 60, 15),
                QPointF(cx, 15),
            ]
        )
        item = QGraphicsPolygonItem(poly)
        item.setBrush(QBrush(self.c_cds))
        item.setPen(QPen(self.c_cds.darker(), 1))
        self.scene.addItem(item)

        text = self.scene.addText(name, self._font)
        text.setDefaultTextColor(self.c_text)
        tw = text.boundingRect().width()
        text.setPos(x + (cell_w - tw) / 2, 25)
        return cx + 30  # center of the arrow

    def _draw_terminator(self, x: float, name: str, cell_w: float):
        """Draw SBOLv T-shape."""
        path = QPainterPath()
        cx = x + cell_w / 2 - 15
        path.moveTo(cx + 15, 0)
        path.lineTo(cx + 15, -35)
        path.moveTo(cx, -35)
        path.lineTo(cx + 30, -35)

        item = QGraphicsPathItem(path)
        item.setPen(QPen(self.c_terminator, 3))
        self.scene.addItem(item)

        text = self.scene.addText(name, self._font)
        text.setDefaultTextColor(self.c_text)
        tw = text.boundingRect().width()
        text.setPos(x + (cell_w - tw) / 2, 25)
        return cx + 15

    def _draw_generic(self, x: float, name: str, cell_w: float):
        """Draw generic box."""
        cx = x + cell_w / 2 - 20
        self.scene.addRect(
            cx, -10, 40, 20, QPen(self.c_text), QBrush(QColor("#bdc3c7"))
        )
        text = self.scene.addText(name, self._font)
        text.setDefaultTextColor(self.c_text)
        tw = text.boundingRect().width()
        text.setPos(x + (cell_w - tw) / 2, 25)
        return cx + 20

    def _draw_repression_line(self, source_x: float, target_x: float, color: QColor):
        """Draw a repression line (curved with flat head) from CDS to Promoter."""
        path = QPainterPath()
        # Start at CDS top
        path.moveTo(source_x, -15)
        # Curve up and over to Promoter
        arch_height = (
            -100 - abs(source_x - target_x) * 0.15
        )  # Dynamic height to avoid overlaps
        path.quadTo((source_x + target_x) / 2, arch_height, target_x, -45)

        item = QGraphicsPathItem(path)
        item.setPen(QPen(color, 2, Qt.PenStyle.DashLine))
        self.scene.addItem(item)

        # Repression "T" head
        head = QPainterPath()
        head.moveTo(target_x - 8, -45)
        head.lineTo(target_x + 8, -45)
        head_item = QGraphicsPathItem(head)
        head_item.setPen(QPen(color, 3))
        self.scene.addItem(head_item)

    def _draw_insulator(self, x: float, name: str, cell_w: float):
        """Draw SBOLv Insulator (outer box)."""
        cx = x + cell_w / 2
        # A simple square on the backbone
        item = QGraphicsPolygonItem(
            QPolygonF(
                [
                    QPointF(cx - 10, -10),
                    QPointF(cx + 10, -10),
                    QPointF(cx + 10, 10),
                    QPointF(cx - 10, 10),
                ]
            )
        )
        item.setBrush(QBrush(self.c_insulator))
        item.setPen(QPen(self.c_insulator, 2))
        self.scene.addItem(item)

        # Inner box
        inner = QGraphicsPolygonItem(
            QPolygonF(
                [
                    QPointF(cx - 5, -5),
                    QPointF(cx + 5, -5),
                    QPointF(cx + 5, 5),
                    QPointF(cx - 5, 5),
                ]
            )
        )
        inner.setBrush(QBrush(self.c_backbone))
        inner.setPen(QPen(Qt.PenStyle.NoPen))
        self.scene.addItem(inner)

        text = self.scene.addText(name, self._font)
        text.setDefaultTextColor(self.c_text)
        tw = text.boundingRect().width()
        text.setPos(x + (cell_w - tw) / 2, 25)
        return cx

    def _draw_sgrna(self, x: float, name: str, cell_w: float):
        """Draw SBOLv non-coding RNA (wavy line / diamond)."""
        cx = x + cell_w / 2

        path = QPainterPath()
        path.moveTo(cx - 15, 0)
        # Wavy line for RNA
        path.quadTo(cx - 7, -10, cx, 0)
        path.quadTo(cx + 7, 10, cx + 15, 0)

        item = QGraphicsPathItem(path)
        item.setPen(QPen(self.c_sgrna, 3))
        self.scene.addItem(item)

        text = self.scene.addText(name, self._font)
        text.setDefaultTextColor(self.c_text)
        tw = text.boundingRect().width()
        text.setPos(x + (cell_w - tw) / 2, 25)
        return cx

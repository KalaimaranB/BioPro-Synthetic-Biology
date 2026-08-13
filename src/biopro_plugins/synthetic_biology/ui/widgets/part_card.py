"""Card widget representing a single biological part in the catalogue."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ...analysis.parts.base import BiologicalPart

try:
    from biopro.ui.theme import Colors, Fonts
except ImportError:
    try:
        from biopro_sdk.plugin.theme_fallback import Colors, Fonts
    except ImportError:

        class Colors:
            BG_DARKEST = "#0d1117"
            BG_DARK = "#161b22"
            BG_MEDIUM = "#21262d"
            FG_PRIMARY = "#e6edf3"
            FG_SECONDARY = "#8b949e"
            FG_DISABLED = "#484f58"
            BORDER = "#30363d"
            ACCENT_PRIMARY = "#00bcd4"

        class Fonts:
            SIZE_SMALL = 11


class PartCard(QFrame):
    """A card representing a single biological part in the catalogue."""

    clicked = pyqtSignal(str)

    def __init__(self, part: BiologicalPart = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.part_id = part.id if part else ""
        self.part_name = part.name if part else "Create New Part"
        self.part_type = part.part_type.capitalize() if part else ""
        self.part_description = part.description if part else ""

        self.is_create_card = part is None

        self._setup_ui()

    def _setup_ui(self):
        self.setFixedSize(200, 120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)

        if self.is_create_card:
            self.setStyleSheet(
                f"QFrame {{ background-color: transparent; "
                f"border: 2px dashed {Colors.BORDER}; border-radius: 8px; }}\n"
                f"QFrame:hover {{ border-color: {Colors.ACCENT_PRIMARY}; "
                f"background-color: rgba(255, 255, 255, 0.05); }}"
            )
            lbl = QLabel("+ Add New Part")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color: {Colors.FG_PRIMARY}; "
                f"font-size: {Fonts.SIZE_SMALL + 2}px; font-weight: bold;"
            )
            layout.addWidget(lbl)
        else:
            self.setStyleSheet(
                f"QFrame {{ background-color: transparent; "
                f"border: 1px solid {Colors.BORDER}; border-radius: 8px; }}\n"
                f"QFrame:hover {{ border-color: {Colors.ACCENT_PRIMARY}; "
                f"background-color: rgba(255, 255, 255, 0.05); }}"
            )

            type_lbl = QLabel(self.part_type)
            type_lbl.setStyleSheet(
                f"color: {Colors.FG_SECONDARY}; "
                f"font-size: {Fonts.SIZE_SMALL - 1}px; font-weight: bold;"
            )
            layout.addWidget(type_lbl)

            name_lbl = QLabel(self.part_name)
            name_lbl.setWordWrap(True)
            name_lbl.setStyleSheet(
                f"color: {Colors.FG_PRIMARY}; "
                f"font-size: {Fonts.SIZE_SMALL + 2}px; font-weight: bold;"
            )
            layout.addWidget(name_lbl)

            layout.addStretch()

            desc_text = (
                self.part_description
                if self.part_description
                else "No description available."
            )
            if len(desc_text) > 60:
                desc_text = desc_text[:57] + "..."

            desc_lbl = QLabel(desc_text)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(
                f"color: {Colors.FG_DISABLED}; font-size: {Fonts.SIZE_SMALL - 1}px;"
            )
            layout.addWidget(desc_lbl)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.part_id)
        super().mouseReleaseEvent(event)

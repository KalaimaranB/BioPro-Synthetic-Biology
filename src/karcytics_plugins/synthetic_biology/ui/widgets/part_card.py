"""Card widget representing a single biological part in the catalogue."""

from karcytics_sdk.plugin.theme_fallback import Colors, Fonts

# pyrefly: ignore [missing-import]
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout

from ...analysis.parts.base import BiologicalPart


class PartCard(QFrame):
    """A card representing a single biological part in the catalogue."""

    clicked = pyqtSignal(str)

    def __init__(self, part: BiologicalPart | None = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.part_id = part.id if part else ""
        self.part_name = part.name if part else "Create New Part"
        self.part_type = part.part_type.capitalize() if part else ""
        self.part_description = part.description if part else ""

        self.is_create_card = part is None

        self._create_lbl: QLabel | None = None
        self._type_lbl: QLabel | None = None
        self._name_lbl: QLabel | None = None
        self._desc_lbl: QLabel | None = None

        self._setup_ui()
        self.refresh_styles()

        from karcytics_sdk.plugin.theme_fallback import theme_manager

        theme_manager.theme_changed.connect(self.refresh_styles)

    def _setup_ui(self):
        self.setFixedSize(200, 120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)

        if self.is_create_card:
            self._create_lbl = QLabel("+ Add New Part")
            self._create_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self._create_lbl)
        else:
            self._type_lbl = QLabel(self.part_type)
            layout.addWidget(self._type_lbl)

            self._name_lbl = QLabel(self.part_name)
            self._name_lbl.setWordWrap(True)
            layout.addWidget(self._name_lbl)

            layout.addStretch()

            desc_text = (
                self.part_description if self.part_description else "No description available."
            )
            if len(desc_text) > 60:  # noqa: PLR2004
                desc_text = desc_text[:57] + "..."

            self._desc_lbl = QLabel(desc_text)
            self._desc_lbl.setWordWrap(True)
            layout.addWidget(self._desc_lbl)

    def refresh_styles(self) -> None:
        """Dynamically refresh card borders and label colors on theme change."""
        if self.is_create_card:
            self.setStyleSheet(
                f"QFrame {{ background-color: transparent; "
                f"border: 2px dashed {Colors.BORDER}; border-radius: 8px; }}\n"
                f"QFrame:hover {{ border-color: {Colors.ACCENT_PRIMARY}; "
                f"background-color: rgba(255, 255, 255, 0.05); }}"
            )
            if self._create_lbl:
                self._create_lbl.setStyleSheet(
                    f"color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_NORMAL}; font-weight: bold;"
                )
        else:
            self.setStyleSheet(
                f"QFrame {{ background-color: transparent; "
                f"border: 1px solid {Colors.BORDER}; border-radius: 8px; }}\n"
                f"QFrame:hover {{ border-color: {Colors.ACCENT_PRIMARY}; "
                f"background-color: rgba(255, 255, 255, 0.05); }}"
            )
            if self._type_lbl:
                self._type_lbl.setStyleSheet(
                    f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}; font-weight: bold;"
                )
            if self._name_lbl:
                self._name_lbl.setStyleSheet(
                    f"color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_NORMAL}; font-weight: bold;"
                )
            if self._desc_lbl:
                self._desc_lbl.setStyleSheet(
                    f"color: {Colors.FG_DISABLED}; font-size: {Fonts.SIZE_SMALL};"
                )

    def _apply_theme_styles(self) -> None:
        self.refresh_styles()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.part_id)
        super().mouseReleaseEvent(event)

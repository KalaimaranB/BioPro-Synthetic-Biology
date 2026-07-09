from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal, Qt

from analysis.parts.base import BiologicalPart
from biopro.ui.theme import Colors, Fonts


class PartCard(QFrame):
    """A card representing a single biological part in the catalogue."""
    
    clicked = pyqtSignal(str)
    
    def __init__(self, part: BiologicalPart = None, parent=None):
        super().__init__(parent)
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
            self.setStyleSheet(f"""
                PartCard {{
                    background: {Colors.BG_MEDIUM};
                    border: 2px dashed {Colors.BORDER};
                    border-radius: 8px;
                }}
                PartCard:hover {{
                    border-color: {Colors.ACCENT_PRIMARY};
                }}
            """)
            lbl = QLabel("+ Add New Part")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_SMALL + 2}px; font-weight: bold;")
            layout.addWidget(lbl)
        else:
            self.setStyleSheet(f"""
                PartCard {{
                    background: {Colors.BG_DARK};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 8px;
                }}
                PartCard:hover {{
                    border-color: {Colors.ACCENT_PRIMARY};
                    background: {Colors.BG_MEDIUM};
                }}
            """)
            
            type_lbl = QLabel(self.part_type)
            type_lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL - 1}px; font-weight: bold;")
            layout.addWidget(type_lbl)
            
            name_lbl = QLabel(self.part_name)
            name_lbl.setWordWrap(True)
            name_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: {Fonts.SIZE_SMALL + 2}px; font-weight: bold;")
            layout.addWidget(name_lbl)
            
            layout.addStretch()
            
            desc_text = self.part_description if self.part_description else "No description available."
            if len(desc_text) > 60:
                desc_text = desc_text[:57] + "..."
            
            desc_lbl = QLabel(desc_text)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(f"color: {Colors.FG_DISABLED}; font-size: {Fonts.SIZE_SMALL - 1}px;")
            layout.addWidget(desc_lbl)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.part_id)
        super().mouseReleaseEvent(event)

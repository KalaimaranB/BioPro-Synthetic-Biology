from karcytics_sdk.plugin.theme_fallback import Colors
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QScrollArea, QSplitter, QVBoxLayout, QWidget

from ...analysis.catalogue.service import PartsCatalogueService
from ...ui.widgets.flow_layout import FlowLayout
from ...ui.widgets.part_card import PartCard
from ...ui.widgets.part_inspector import PartInspector


class CatalogueView(QWidget):
    """View displaying the parts catalogue using a card-based layout and details
    inspector.
    """

    def __init__(self, catalogue_service: PartsCatalogueService, parent=None):
        super().__init__(parent)
        self.service = catalogue_service
        self._setup_ui()
        self.refresh_catalogue()
        self.refresh_styles()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main Splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter)

        # Left Side: Scroll Area with FlowLayout for Cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setMinimumWidth(500)
        self.scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("QWidget { background: transparent; }")
        self.flow_layout = FlowLayout(
            self.cards_container, margin=10, hSpacing=10, vSpacing=10
        )
        self.scroll_area.setWidget(self.cards_container)

        self.splitter.addWidget(self.scroll_area)

        # Right Side: Part Inspector
        self.inspector = PartInspector(catalogue_service=self.service)
        self.inspector.part_saved.connect(self._on_part_saved)
        self.inspector.part_deleted.connect(self._on_part_deleted)
        self.splitter.addWidget(self.inspector)

        # Splitter sizing and 70:30 stretch constraints
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 7)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([700, 320])

    def _on_part_deleted(self, part_id: str):
        self.refresh_catalogue()
        self.inspector.clear()
        self.splitter.setSizes([700, 320])

    def refresh_catalogue(self):
        """Reload all cards from the service."""
        # Clear existing cards
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add 'Create New Part' card first
        create_card = PartCard(None)
        create_card.clicked.connect(self._on_card_clicked)
        self.flow_layout.addWidget(create_card)

        # Add all existing parts
        parts = self.service.get_all_parts()
        for part in parts:
            card = PartCard(part)
            card.clicked.connect(self._on_card_clicked)
            self.flow_layout.addWidget(card)

    def _on_card_clicked(self, part_id: str):
        if not part_id:
            # Create new part clicked
            self.inspector.set_part(None)
        else:
            part = self.service.get_part(part_id)
            self.inspector.set_part(part)

    def _on_part_saved(self, part):
        self.service.add_part(part)
        self.refresh_catalogue()
        # Reselect the part
        self.inspector.set_part(part)

    def refresh_table(self):
        """Alias for compatibility with main panel."""
        self.refresh_catalogue()

    def refresh_styles(self):
        """Apply theme styling dynamically to splitter and inspector."""
        splitter_qss = f"""
            QSplitter::handle {{
                background-color: {Colors.BORDER};
            }}
            QSplitter::handle:horizontal {{
                width: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
            }}
        """
        self.splitter.setStyleSheet(splitter_qss)
        if hasattr(self, "inspector") and hasattr(self.inspector, "refresh_styles"):
            self.inspector.refresh_styles()

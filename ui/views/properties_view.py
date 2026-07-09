"""Properties view for quantitative data of biological parts (Inspector style)."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from analysis.parts.components import CDS, RBS, Promoter, Terminator


class PropertiesView(QWidget):
    """An inspector view for viewing and editing kinetic properties of components."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parts = []
        self._current_part = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1) # small gap between split

        # Left panel: List of parts
        self.part_list = QListWidget()
        self.part_list.setMaximumWidth(300)
        self.part_list.currentItemChanged.connect(self._on_part_selected)
        layout.addWidget(self.part_list)

        # Right panel: Form for properties
        self.inspector_scroll = QScrollArea()
        self.inspector_scroll.setWidgetResizable(True)
        self.inspector_widget = QWidget()
        self.form_layout = QFormLayout(self.inspector_widget)
        self.form_layout.setContentsMargins(16, 16, 16, 16)
        self.form_layout.setSpacing(12)
        
        self.inspector_scroll.setWidget(self.inspector_widget)
        layout.addWidget(self.inspector_scroll)

        # Apply theme styles once for global migration to pick up
        try:
            from biopro.ui.theme import Colors
            self.part_list.setStyleSheet(
                f"QListWidget {{ background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY}; border: none; }}"
                f"QListWidget::item {{ padding: 8px; border-bottom: 1px solid {Colors.BORDER}; }}"
                f"QListWidget::item:selected {{ background: {Colors.BG_MEDIUM}; border-left: 3px solid {Colors.ACCENT_PRIMARY}; }}"
            )
            self.inspector_scroll.setStyleSheet(f"QScrollArea {{ border: none; background: {Colors.BG_DARK}; }}")
            self.inspector_widget.setStyleSheet(f"background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY};")
        except ImportError:
            pass

    def set_parts(self, parts: list):
        """Update the list with a new list of parts."""
        self._parts = parts
        
        # Save current selection if any
        current_id = None
        if self.part_list.currentItem():
            current_id = self.part_list.currentItem().data(Qt.ItemDataRole.UserRole)
            
        self.part_list.clear()
        
        for part in self._parts:
            item = QListWidgetItem(f"{part.id} - {part.name}")
            item.setData(Qt.ItemDataRole.UserRole, part.id)
            self.part_list.addItem(item)
            if current_id == part.id:
                self.part_list.setCurrentItem(item)

    def _on_part_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if not current:
            self._clear_inspector()
            return
            
        part_id = current.data(Qt.ItemDataRole.UserRole)
        part = next((p for p in self._parts if p.id == part_id), None)
        if part:
            self._populate_inspector(part)

    def _clear_inspector(self):
        """Remove all rows from the inspector form."""
        while self.form_layout.rowCount() > 0:
            self.form_layout.removeRow(0)
        self._current_part = None

    def _populate_inspector(self, part):
        """Populate the inspector form with the properties of the selected part."""
        self._clear_inspector()
        self._current_part = part
        
        # Header
        title = QLabel(f"<b>{part.id}</b> ({part.__class__.__name__})")
        try:
            from biopro.ui.theme import Colors
            title.setStyleSheet(f"font-size: 24px; color: {Colors.ACCENT_PRIMARY};")
        except ImportError:
            pass
        self.form_layout.addRow(title)
        self.form_layout.addRow(QLabel(f"<i>{part.name}</i>"))

        # External Links
        link_label = QLabel(f"<a href='http://parts.igem.org/Part:{part.id}' style='color: #00bcd4;'>View Part on iGEM Registry</a>")
        link_label.setOpenExternalLinks(True)
        self.form_layout.addRow(link_label)
        
        # Kinetics source
        citation = ""
        if hasattr(part, "properties") and "citation" in part.properties:
            citation = part.properties["citation"]
        elif isinstance(part, Promoter):
            citation = "Voigt Lab Cello Library (Science 2016)"
            
        if citation:
            # Simple heuristic to make URLs clickable if present
            if "http" in citation:
                import re
                url_match = re.search(r'(https?://\S+)', citation)
                if url_match:
                    url = url_match.group(1)
                    citation = citation.replace(url, f"<a href='{url}' style='color: #8b949e;'>[Link]</a>")
            source_label = QLabel(f"<small style='color: #8b949e;'><i>Source: {citation}</i></small>")
            source_label.setOpenExternalLinks(True)
            source_label.setWordWrap(True)
            self.form_layout.addRow(source_label)

        self.form_layout.addRow(QLabel("")) # Spacer
        
        # Base Properties
        if hasattr(part, 'sequence'):
            seq_display = part.sequence[:30] + "..." if len(part.sequence) > 30 else part.sequence
            self.form_layout.addRow("Sequence (start):", QLabel(seq_display))

        # Role-specific Kinetic Parameters
        if isinstance(part, Promoter):
            self._add_double_spinbox("y_min (Leakiness in RPU):", "y_min", part.y_min, 0.0, 10.0, 0.01)
            self._add_double_spinbox("y_max (Max Output in RPU):", "y_max", part.y_max, 0.0, 20.0, 0.1)
            self._add_double_spinbox("K_d (Threshold):", "K_d", part.K_d, 0.0, 10.0, 0.05)
            self._add_double_spinbox("n (Hill Coefficient):", "n", part.n, 0.1, 10.0, 0.1)
            
            reps = ", ".join(part.repressors) if part.repressors else "None"
            self.form_layout.addRow("Repressors:", QLabel(reps))
            
        elif isinstance(part, CDS):
            self._add_double_spinbox("Translation Rate:", "translation_rate", part.translation_rate, 0.0, 10.0, 0.1)
            self._add_double_spinbox("Degradation Rate:", "degradation_rate", part.degradation_rate, 0.0, 1.0, 0.001)
            
        elif isinstance(part, RBS):
            self._add_double_spinbox("Binding Strength:", "translation_initiation_rate", part.translation_initiation_rate, 0.0, 10.0, 0.1)
            
        elif isinstance(part, Terminator):
            self._add_double_spinbox("Efficiency:", "termination_efficiency", part.termination_efficiency, 0.0, 1.0, 0.01)

        self.form_layout.addRow(QLabel("")) # Spacer
        
        # Raw properties from iGEM
        if hasattr(part, "properties") and part.properties:
            self.form_layout.addRow(QLabel("<b>Raw Registry Properties:</b>"))
            for k, v in part.properties.items():
                if k not in ["control", "repressors", "protein", "forward_efficiency", "efficiency"]:
                    # Skip properties we already parsed out
                    self.form_layout.addRow(f"{k}:", QLabel(str(v)))

    def _add_double_spinbox(self, label: str, attr_name: str, value: float, min_val: float, max_val: float, step: float):
        """Helper to create and bind a QDoubleSpinBox to a part attribute."""
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setDecimals(3)
        if value is not None:
            spin.setValue(value)
        else:
            # Show empty if None, by setting special text or just 0
            spin.setSpecialValueText("N/A")
            spin.setValue(min_val)

        # Connect value change to update the model
        spin.valueChanged.connect(lambda val, attr=attr_name: self._on_param_changed(attr, val))
        
        try:
            from biopro.ui.theme import Colors
            spin.setStyleSheet(f"background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY}; border: 1px solid {Colors.BORDER}; padding: 4px;")
        except ImportError:
            pass

        self.form_layout.addRow(label, spin)

    def _on_param_changed(self, attr_name: str, value: float):
        if self._current_part:
            setattr(self._current_part, attr_name, value)

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QFormLayout, 
    QLineEdit, QPushButton, QTextEdit, QLabel, QComboBox, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap

from analysis.parts.base import BiologicalPart
from analysis.parts.components import CDS, Promoter, Terminator, RBS
from biopro.ui.theme import Colors, Fonts


class PartInspector(QWidget):
    """Details pane for viewing and editing a biological part."""
    
    part_saved = pyqtSignal(BiologicalPart)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_part = None
        self._setup_ui()
        self.setMinimumWidth(300)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.header_lbl = QLabel("Part Inspector")
        self.header_lbl.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {Colors.FG_PRIMARY};")
        self.layout.addWidget(self.header_lbl)
        
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # Properties Tab
        self.props_tab = QWidget()
        self.props_layout = QFormLayout(self.props_tab)
        
        self.id_edit = QLineEdit()
        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Promoter", "CDS", "Terminator", "RBS"])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        
        self.props_layout.addRow("ID:", self.id_edit)
        self.props_layout.addRow("Name:", self.name_edit)
        self.props_layout.addRow("Type:", self.type_combo)
        
        # Promoter
        self.kd_lbl = QLabel("K_d:")
        self.kd_edit = QLineEdit()
        self.ymax_lbl = QLabel("y_max:")
        self.ymax_edit = QLineEdit()
        self.ymin_lbl = QLabel("y_min:")
        self.ymin_edit = QLineEdit()
        self.n_lbl = QLabel("n:")
        self.n_edit = QLineEdit()
        
        self.props_layout.addRow(self.kd_lbl, self.kd_edit)
        self.props_layout.addRow(self.ymax_lbl, self.ymax_edit)
        self.props_layout.addRow(self.ymin_lbl, self.ymin_edit)
        self.props_layout.addRow(self.n_lbl, self.n_edit)

        # CDS
        self.trans_rate_lbl = QLabel("Translation Rate:")
        self.trans_rate_edit = QLineEdit()
        self.deg_rate_lbl = QLabel("Degradation Rate:")
        self.deg_rate_edit = QLineEdit()
        self.product_lbl = QLabel("Product:")
        self.product_edit = QLineEdit()
        
        self.props_layout.addRow(self.trans_rate_lbl, self.trans_rate_edit)
        self.props_layout.addRow(self.deg_rate_lbl, self.deg_rate_edit)
        self.props_layout.addRow(self.product_lbl, self.product_edit)
        
        # Terminator
        self.term_eff_lbl = QLabel("Termination Eff.:")
        self.term_eff_edit = QLineEdit()
        self.props_layout.addRow(self.term_eff_lbl, self.term_eff_edit)
        
        # RBS
        self.rbs_init_rate_lbl = QLabel("Translation Init Rate:")
        self.rbs_init_rate_edit = QLineEdit()
        self.props_layout.addRow(self.rbs_init_rate_lbl, self.rbs_init_rate_edit)
        
        self.desc_lbl = QLabel()
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-style: italic; margin-top: 10px;")
        self.props_layout.addRow(self.desc_lbl)
        
        self.tabs.addTab(self.props_tab, "Properties")
        
        # Sequence Tab
        self.seq_tab = QWidget()
        self.seq_layout = QVBoxLayout(self.seq_tab)
        self.seq_edit = QTextEdit()
        self.seq_layout.addWidget(self.seq_edit)
        self.tabs.addTab(self.seq_tab, "Sequence")
        
        # Structure Tab
        self.struct_tab = QWidget()
        self.struct_layout = QVBoxLayout(self.struct_tab)
        self.struct_lbl = QLabel()
        self.struct_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.struct_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.struct_layout.addWidget(self.struct_lbl)
        self.tabs.addTab(self.struct_tab, "Structure")
        
        # Save Button
        self.save_btn = QPushButton("Save / Update Part")
        self.save_btn.setStyleSheet(f"background: {Colors.ACCENT_PRIMARY}; color: {Colors.BG_DARKEST}; font-weight: bold;")
        self.save_btn.clicked.connect(self._on_save)
        self.layout.addWidget(self.save_btn)
        
        self.clear()
        self._on_type_changed(self.type_combo.currentText())

    def _on_type_changed(self, text):
        part_type = text.lower()
        
        is_promoter = part_type == "promoter"
        self.kd_lbl.setVisible(is_promoter)
        self.kd_edit.setVisible(is_promoter)
        self.ymax_lbl.setVisible(is_promoter)
        self.ymax_edit.setVisible(is_promoter)
        self.ymin_lbl.setVisible(is_promoter)
        self.ymin_edit.setVisible(is_promoter)
        self.n_lbl.setVisible(is_promoter)
        self.n_edit.setVisible(is_promoter)
        
        is_cds = part_type == "cds"
        self.trans_rate_lbl.setVisible(is_cds)
        self.trans_rate_edit.setVisible(is_cds)
        self.deg_rate_lbl.setVisible(is_cds)
        self.deg_rate_edit.setVisible(is_cds)
        self.product_lbl.setVisible(is_cds)
        self.product_edit.setVisible(is_cds)
        
        is_term = part_type == "terminator"
        self.term_eff_lbl.setVisible(is_term)
        self.term_eff_edit.setVisible(is_term)
        
        is_rbs = part_type == "rbs"
        self.rbs_init_rate_lbl.setVisible(is_rbs)
        self.rbs_init_rate_edit.setVisible(is_rbs)

    def set_part(self, part: BiologicalPart = None):
        """Populate the inspector. If None, clear for new part."""
        self.current_part = part
        
        is_editable = part.is_custom if part else True
        
        self.name_edit.setReadOnly(not is_editable)
        self.type_combo.setEnabled(is_editable)
        self.seq_edit.setReadOnly(not is_editable)
        
        self.kd_edit.setReadOnly(not is_editable)
        self.ymax_edit.setReadOnly(not is_editable)
        self.ymin_edit.setReadOnly(not is_editable)
        self.n_edit.setReadOnly(not is_editable)
        
        self.trans_rate_edit.setReadOnly(not is_editable)
        self.deg_rate_edit.setReadOnly(not is_editable)
        self.product_edit.setReadOnly(not is_editable)
        
        self.term_eff_edit.setReadOnly(not is_editable)
        self.rbs_init_rate_edit.setReadOnly(not is_editable)
        
        self.save_btn.setVisible(is_editable)
        
        if part is None:
            self.header_lbl.setText("New Theoretical Part")
            self.id_edit.setText("")
            self.id_edit.setReadOnly(False)
            self.name_edit.setText("")
            self.type_combo.setCurrentIndex(0)
            self.seq_edit.setText("")
            
            self.kd_edit.setText("")
            self.ymax_edit.setText("")
            self.ymin_edit.setText("")
            self.n_edit.setText("")
            
            self.trans_rate_edit.setText("")
            self.deg_rate_edit.setText("")
            self.product_edit.setText("")
            
            self.term_eff_edit.setText("")
            self.rbs_init_rate_edit.setText("")
            
            self.desc_lbl.setText("")
            self.struct_lbl.setText("No structure generated for this part.")
            self.struct_lbl.setStyleSheet(f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; color: {Colors.FG_SECONDARY};")
        else:
            self.header_lbl.setText(f"{part.name} ({part.id})")
            self.id_edit.setText(part.id)
            self.id_edit.setReadOnly(True)
            self.name_edit.setText(part.name)
            
            for i in range(self.type_combo.count()):
                if self.type_combo.itemText(i).lower() == part.part_type.lower():
                    self.type_combo.setCurrentIndex(i)
                    break
            
            self.seq_edit.setText(part.sequence)
            self.desc_lbl.setText(part.description if part.description else "No description available.")
            
            self.kd_edit.setText("")
            self.ymax_edit.setText("")
            self.ymin_edit.setText("")
            self.n_edit.setText("")
            
            self.trans_rate_edit.setText("")
            self.deg_rate_edit.setText("")
            self.product_edit.setText("")
            
            self.term_eff_edit.setText("")
            self.rbs_init_rate_edit.setText("")
            
            if isinstance(part, Promoter):
                self.kd_edit.setText(str(part.K_d) if part.K_d is not None else "")
                self.ymax_edit.setText(str(part.y_max) if part.y_max is not None else "")
                self.ymin_edit.setText(str(part.y_min) if part.y_min is not None else "")
                self.n_edit.setText(str(part.n) if part.n is not None else "")
            elif isinstance(part, CDS):
                self.trans_rate_edit.setText(str(part.translation_rate) if part.translation_rate is not None else "")
                self.deg_rate_edit.setText(str(part.degradation_rate) if part.degradation_rate is not None else "")
                self.product_edit.setText(str(part.product) if part.product else "")
            elif isinstance(part, Terminator):
                self.term_eff_edit.setText(str(part.termination_efficiency) if part.termination_efficiency is not None else "")
            elif isinstance(part, RBS):
                self.rbs_init_rate_edit.setText(str(part.translation_initiation_rate) if part.translation_initiation_rate is not None else "")
                
            self._render_static_structure(part)

    def clear(self):
        self.set_part(None)

    def _render_static_structure(self, part: BiologicalPart):
        """Show a static 2D image or a generic placeholder."""
        image_rel_path = part.properties.get("image_path")
        
        if image_rel_path:
            # Resolve relative path to absolute
            import analysis.catalogue.service as svc
            base_dir = os.path.dirname(os.path.abspath(svc.__file__))
            abs_path = os.path.join(base_dir, os.path.basename(image_rel_path) if not image_rel_path.startswith("images") else image_rel_path)
            
            if os.path.exists(abs_path):
                pixmap = QPixmap(abs_path)
                self.struct_lbl.setStyleSheet("")
                self.struct_lbl.setPixmap(pixmap.scaled(self.struct_tab.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                return
                
        self.struct_lbl.setStyleSheet(f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; color: {Colors.FG_SECONDARY};")
        self.struct_lbl.setText("No structure available.\\n(Generic Placeholder)")

    def _on_save(self):
        if self.current_part and not self.current_part.is_custom:
            return  # Safety check
            
        part_id = self.id_edit.text().strip()
        if not part_id:
            return
            
        name = self.name_edit.text().strip()
        seq = self.seq_edit.toPlainText().strip()
        part_type = self.type_combo.currentText().lower()
        
        def _parse_float(txt):
            try: return float(txt)
            except ValueError: return None
            
        part = self.current_part
        if not part:
            if part_type == "promoter":
                part = Promoter(id=part_id, name=name, sequence=seq)
            elif part_type == "terminator":
                part = Terminator(id=part_id, name=name, sequence=seq)
            elif part_type == "rbs":
                part = RBS(id=part_id, name=name, sequence=seq)
            else:
                part = CDS(id=part_id, name=name, sequence=seq)
        else:
            part.name = name
            part.sequence = seq
            
        if isinstance(part, Promoter):
            part.K_d = _parse_float(self.kd_edit.text())
            part.y_max = _parse_float(self.ymax_edit.text())
            part.y_min = _parse_float(self.ymin_edit.text())
            part.n = _parse_float(self.n_edit.text())
        elif isinstance(part, CDS):
            part.translation_rate = _parse_float(self.trans_rate_edit.text())
            part.degradation_rate = _parse_float(self.deg_rate_edit.text())
            part.product = self.product_edit.text()
        elif isinstance(part, Terminator):
            part.termination_efficiency = _parse_float(self.term_eff_edit.text())
        elif isinstance(part, RBS):
            part.translation_initiation_rate = _parse_float(self.rbs_init_rate_edit.text())
            
        self.part_saved.emit(part)


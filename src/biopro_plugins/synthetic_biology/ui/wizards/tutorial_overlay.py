"""Full-screen dimmed interactive tutorial overlay with pop-out mascot for Synthetic Biology workspace."""

from typing import List, Dict, Optional

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QBrush,
    QPixmap,
    QLinearGradient,
)
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QProgressBar,
    QGraphicsDropShadowEffect,
)


SYNTHETIC_BIOLOGY_TUTORIAL_STEPS: List[Dict[str, str]] = [
    {
        "title": "System Initialization Protocol",
        "text": "Should the user initiate the Synthetic Biology module, the system will prepare to evaluate transcriptional and translational biophysics. Proceed to the Parts Catalogue to establish the wild type sequence baseline.",
        "icon": "⚙️",
    },
    {
        "title": "Transcriptional Regulation (Promoters)",
        "text": "Upon selecting a promoter sequence, the engine will apply a Thermodynamic Position Weight Matrix. This calculates the change in Gibbs free energy associated with the RNA polymerase holoenzyme binding to the minus 10 and minus 35 consensus motifs. Torsional strain penalties will be applied if the spacer length deviates from 17 base pairs.",
        "icon": "🧬",
    },
    {
        "title": "Translational Kinetics & Stability (CDS)",
        "text": "If a coding sequence is processed, the system will evaluate translation elongation rates utilizing the Codon Adaptation Index. Concurrently, the BLOSUM62 substitution matrix will evaluate structural stability. Should the user introduce a missense mutation, the matrix will calculate a severe thermodynamic penalty and drastically scale the degradation rate parameter.",
        "icon": "⚡",
    },
    {
        "title": "Comparative Visualization",
        "text": "Should the user invoke the graphing module, a Levenshtein distance algorithm will scan the local database to isolate the wild type origin. The engine will subsequently feed the extracted kinetic parameters into the Repressive Hill Equation and the differential equation solver to plot comparative steady state protein accumulation. Click Finish to execute these protocols.",
        "icon": "📊",
    },
]


def create_default_mascot_pixmap(width: int = 120, height: int = 200) -> QPixmap:
    """Draw a high-quality Biotech AI Mascot pixmap with glowing DNA badge."""
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Mascot body gradient (cyan to deep blue)
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0.0, QColor("#00e5ff"))
    grad.setColorAt(0.5, QColor("#0091ea"))
    grad.setColorAt(1.0, QColor("#0d47a1"))

    # Outer glow / aura
    painter.setBrush(QBrush(QColor(0, 229, 255, 45)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(5, 10, width - 10, height - 20)

    # Capsule Body / Head
    painter.setBrush(QBrush(grad))
    painter.drawRoundedRect(15, 20, width - 30, height - 45, 28, 28)

    # Dark Screen Face
    painter.setBrush(QBrush(QColor("#0a192f")))
    painter.drawRoundedRect(25, 36, width - 50, 48, 14, 14)

    # Glowing Cyan Eyes
    painter.setBrush(QBrush(QColor("#00ffff")))
    painter.drawEllipse(35, 52, 12, 12)
    painter.drawEllipse(width - 47, 52, 12, 12)

    # Eye highlights
    painter.setBrush(QBrush(QColor("#ffffff")))
    painter.drawEllipse(38, 54, 4, 4)
    painter.drawEllipse(width - 44, 54, 4, 4)

    # Smile curve
    path = QPainterPath()
    path.moveTo(45, 72)
    path.quadTo(width // 2, 78, width - 45, 72)
    pen = QPen(QColor("#00ffff"), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)

    # Top Antenna
    painter.setPen(QPen(QColor("#00e5ff"), 3))
    painter.drawLine(width // 2, 20, width // 2, 8)
    painter.setBrush(QBrush(QColor("#ff007f")))
    painter.drawEllipse(width // 2 - 5, 3, 10, 10)

    # DNA Badge
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor("#ffffff")))
    painter.drawEllipse(width // 2 - 16, height - 55, 32, 32)

    painter.setFont(QFont("Arial", 14))
    painter.setPen(QPen(QColor("#0091ea")))
    painter.drawText(
        QRectF(width // 2 - 16, height - 55, 32, 32), Qt.AlignmentFlag.AlignCenter, "🧬"
    )

    painter.end()
    return pixmap


class AcademyTutorialDialog(QDialog):
    """Full-screen dimmed tutorial overlay with pop-out mascot layout."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        steps: Optional[List[Dict[str, str]]] = None,
    ):
        super().__init__(parent)
        self.steps = steps or SYNTHETIC_BIOLOGY_TUTORIAL_STEPS
        self.current_step = 0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)

        self._setup_ui()
        self._update_geometry()
        self.render_step(0)

    def _setup_ui(self):
        # Center container for positioning mascot + white card
        self.center_container = QWidget(self)
        self.center_container.setFixedSize(620, 250)

        # 1. White Content Box (positioned at x=60)
        self.content_card = QFrame(self.center_container)
        self.content_card.setGeometry(60, 0, 560, 250)
        self.content_card.setStyleSheet(
            """
            QFrame {
                background-color: #ffffff;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
            }
            """
        )

        # Drop shadow for white content card
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.content_card.setGraphicsEffect(shadow)

        # Card Inner Layout (left margin=70 so text clears the overlapping mascot)
        card_layout = QVBoxLayout(self.content_card)
        card_layout.setContentsMargins(70, 16, 20, 16)
        card_layout.setSpacing(10)

        # Header Row
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)

        self.step_counter_label = QLabel("Step 1 of 6")
        self.step_counter_label.setStyleSheet(
            "color: #718096; font-weight: bold; font-size: 12px; border: none;"
        )

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                color: #a0aec0;
                border: none;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #4a5568;
            }
            """
        )
        self.close_btn.clicked.connect(self.reject)

        top_row.addWidget(self.step_counter_label)
        top_row.addStretch()
        top_row.addWidget(self.close_btn)
        card_layout.addLayout(top_row)

        # Body Row
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            "color: #1a202c; font-size: 16px; font-weight: 700; border: none;"
        )

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setStyleSheet(
            "color: #4a5568; font-size: 12px; line-height: 1.4; border: none;"
        )

        card_layout.addWidget(self.title_label)
        card_layout.addWidget(self.text_label, 1)

        # Footer Row: Flat Progress Bar + Primary Solid Blue Next Button
        bottom_box = QVBoxLayout()
        bottom_box.setSpacing(10)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                background-color: #e2e8f0;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #00bcd4;
                border-radius: 2px;
            }
            """
        )
        bottom_box.addWidget(self.progress_bar)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)

        self.back_btn = QPushButton("◀ Back")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #edf2f7;
                color: #4a5568;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e2e8f0;
            }
            """
        )
        self.back_btn.clicked.connect(self._prev_step)

        self.next_btn = QPushButton("Next ➔")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #00bcd4;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #00acc1;
            }
            """
        )
        self.next_btn.clicked.connect(self._next_step)

        nav_row.addWidget(self.back_btn)
        nav_row.addStretch()
        nav_row.addWidget(self.next_btn)
        bottom_box.addLayout(nav_row)

        card_layout.addLayout(bottom_box)

        # 2. Pop-out Mascot (positioned at x=0, extending 60px outside content_card on left)
        self.mascot_label = QLabel(self.center_container)
        self.mascot_label.setGeometry(0, 25, 120, 200)
        pixmap = create_default_mascot_pixmap(120, 200)
        self.mascot_label.setPixmap(pixmap)
        self.mascot_label.setStyleSheet("background: transparent; border: none;")
        self.mascot_label.raise_()

    def _update_geometry(self):
        """Fit overlay over full parent window rect and center the container."""
        parent_w = self.parentWidget()
        if parent_w:
            self.setGeometry(parent_w.rect())
            p_rect = parent_w.rect()
            c_w = self.center_container.width()
            c_h = self.center_container.height()
            x = max(0, (p_rect.width() - c_w) // 2)
            y = max(0, (p_rect.height() - c_h) // 2)
            self.center_container.move(x, y)
        else:
            self.resize(800, 600)
            self.center_container.move(90, 175)

    def paintEvent(self, event):
        """Draw full-screen semi-transparent black dimmed overlay (rgba(0, 0, 0, 150))."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 150))

    def showEvent(self, event):
        super().showEvent(event)
        self._update_geometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_geometry()

    def render_step(self, step_idx: int):
        """Render step content at index step_idx."""
        if not self.steps or step_idx < 0 or step_idx >= len(self.steps):
            return

        self.current_step = step_idx
        step_data = self.steps[step_idx]
        total_steps = len(self.steps)

        self.step_counter_label.setText(f"Step {step_idx + 1} of {total_steps}")
        self.title_label.setText(step_data.get("title", ""))
        self.text_label.setText(step_data.get("text", ""))

        progress_pct = int(((step_idx + 1) / total_steps) * 100)
        self.progress_bar.setValue(progress_pct)

        self.back_btn.setEnabled(step_idx > 0)
        self.back_btn.setVisible(step_idx > 0)

        if step_idx == total_steps - 1:
            self.next_btn.setText("Finish 🎉")
        else:
            self.next_btn.setText("Next ➔")

    def _next_step(self):
        if self.current_step < len(self.steps) - 1:
            self.render_step(self.current_step + 1)
        else:
            self.accept()

    def _prev_step(self):
        if self.current_step > 0:
            self.render_step(self.current_step - 1)


# Class alias for backward compatibility across modules
TutorialOverlay = AcademyTutorialDialog

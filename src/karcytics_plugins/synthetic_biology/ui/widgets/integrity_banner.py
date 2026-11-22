"""The banner that states why a panel's numbers cannot be trusted.

Half of the rule in ``analysis/result_integrity.py`` is a judgement and lives
there. This is the other half: making that judgement the most prominent thing
on screen when it is not "trustworthy".

Prominence is the point. Both defects this closes (audit findings C-3 and
C-4) had the engine's own warning available at the view boundary and dropped
it. A caption below a table would have been dropped just as effectively,
because nobody reads a caption under a table of confident-looking numbers. So
the banner sits above the results it qualifies, fills the width, carries a
coloured rule, and is the first thing in the panel's reading order.

The widget decides no science. It receives a
:class:`~...analysis.result_integrity.ResultIntegrity` and renders it.
"""

from __future__ import annotations

from karcytics_sdk.plugin.components import BioCaptionLabel, BioSectionLabel
from karcytics_sdk.plugin.theme_fallback import Colors, theme_manager
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from ...analysis.result_integrity import DEMO, FAILED, INVALID, ResultIntegrity

#: Accent per level. Demonstration data is the loudest because it is the one
#: that looks like a result; a failure already looks like a failure.
_ACCENT = {
    DEMO: "ACCENT_DANGER",
    INVALID: "ACCENT_WARNING",
    FAILED: "ACCENT_WARNING",
}


class IntegrityBanner(QWidget):
    """Shows a payload's integrity verdict, or hides when there is nothing to say."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._verdict: ResultIntegrity | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(0)

        self._frame = QFrame()
        self._frame.setObjectName("IntegrityBanner")
        inner = QVBoxLayout(self._frame)
        inner.setContentsMargins(10, 8, 10, 8)
        inner.setSpacing(2)

        self._headline = BioSectionLabel("")
        self._headline.setWordWrap(True)
        self._detail = BioCaptionLabel("")
        self._detail.setWordWrap(True)

        inner.addWidget(self._headline)
        inner.addWidget(self._detail)
        layout.addWidget(self._frame)

        self.setVisible(False)
        theme_manager.theme_changed.connect(self._apply_theme)

    # ── API ────────────────────────────────────────────────────────────

    def show_verdict(self, verdict: ResultIntegrity) -> None:
        """Display ``verdict``, or hide entirely when the payload is trustworthy."""
        self._verdict = verdict
        if verdict.presentable:
            self.clear()
            return

        self._headline.setText(verdict.headline)
        self._detail.setText(verdict.detail)
        self._detail.setVisible(bool(verdict.detail))
        self._apply_theme()
        self.setVisible(True)

    def clear(self) -> None:
        """Hide the banner and forget the verdict."""
        self._verdict = None
        self._headline.setText("")
        self._detail.setText("")
        self.setVisible(False)

    @property
    def verdict(self) -> ResultIntegrity | None:
        """The verdict currently displayed, or None when hidden."""
        return self._verdict

    # ── Presentation ───────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        if self._verdict is None:
            return
        accent = getattr(Colors, _ACCENT.get(self._verdict.level, "ACCENT_WARNING"))
        self._frame.setStyleSheet(
            f"#IntegrityBanner {{"
            f" background-color: {Colors.BG_SECONDARY};"
            f" border-left: 4px solid {accent};"
            f" border-radius: 3px; }}"
        )
        self._headline.setStyleSheet(f"color: {accent}; font-weight: 600;")


__all__ = ["IntegrityBanner"]

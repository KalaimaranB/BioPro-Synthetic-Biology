"""Methods & References: the write-up for what this workspace actually ran.

Reads the methods log kept in ``SynBioState`` — one entry per kind of analysis,
with the parameters it used and the citation keys behind it — and renders it as
a Materials & Methods paragraph with numbered references, ready to paste into a
lab report, plus BibTeX for a reference manager.

Non-modal on purpose: the guided demo tour opens it as one of its steps and
moves on with Next, and a modal dialog would block the tour bar.
"""

from __future__ import annotations

from typing import Any

from karcytics_sdk.plugin.citation_widgets import CitationsPanel
from karcytics_sdk.plugin.components import BioScrollArea, PrimaryButton, SecondaryButton
from karcytics_sdk.plugin.dialogs import get_save_path, show_error
from karcytics_sdk.plugin.theme_fallback import Colors, Fonts, theme_manager
from karcytics_sdk.plugin.toast import show_toast
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...analysis.citations import bibtex, cited_keys, methods_text


class MethodsReferencesDialog(QDialog):
    """Methods paragraph, linked references, and BibTeX export for a workspace."""

    def __init__(self, state: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self.setWindowTitle("Methods & References")
        self.setModal(False)
        self.resize(820, 640)
        self._setup_ui()
        self._apply_theme()
        theme_manager.theme_changed.connect(self._apply_theme)
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        intro = QLabel(
            "A Materials & Methods paragraph for the analyses run in this workspace, "
            "with the parameters each one used. References were checked against "
            "Crossref. Paste it into a lab report draft, or export BibTeX for a "
            "reference manager."
        )
        intro.setObjectName("MethodsIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        methods_lbl = QLabel("Methods")
        methods_lbl.setObjectName("MethodsHeading")
        layout.addWidget(methods_lbl)

        self.methods_edit = QPlainTextEdit(self)
        self.methods_edit.setReadOnly(True)
        self.methods_edit.setObjectName("MethodsText")
        self.methods_edit.setMinimumHeight(170)
        layout.addWidget(self.methods_edit, 2)

        refs_lbl = QLabel("References")
        refs_lbl.setObjectName("MethodsHeading")
        layout.addWidget(refs_lbl)

        # Numbered in the same order as the bracketed numbers above.
        self.references_panel = CitationsPanel(parent=self)
        scroll = BioScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.references_panel)
        layout.addWidget(scroll, 3)

        buttons = QHBoxLayout()
        self.btn_copy = PrimaryButton("Copy methods + references", self)
        self.btn_copy.clicked.connect(self.copy_to_clipboard)
        self.btn_bibtex = SecondaryButton("Export BibTeX…", self)
        self.btn_bibtex.clicked.connect(self.export_bibtex)
        self.btn_close = SecondaryButton("Close", self)
        self.btn_close.clicked.connect(self.close)
        buttons.addWidget(self.btn_copy)
        buttons.addWidget(self.btn_bibtex)
        buttons.addStretch()
        buttons.addWidget(self.btn_close)
        layout.addLayout(buttons)

    # ── Content ─────────────────────────────────────────────────────────

    def _log(self) -> list[dict[str, Any]]:
        return list(getattr(self.state, "methods_log", []) or [])

    def refresh(self) -> None:
        """Re-read the methods log; call whenever the dialog is (re)shown."""
        log = self._log()
        self.methods_edit.setPlainText(methods_text(log, include_references=False))
        keys = cited_keys(log)
        self.references_panel.set_keys(keys)
        self.btn_bibtex.setEnabled(bool(keys))

    def full_text(self) -> str:
        """Paragraph plus plain-text reference list, as copied to the clipboard."""
        return methods_text(self._log(), include_references=True)

    def copy_to_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.full_text())
            show_toast("Methods and references copied")

    def export_bibtex(self) -> None:
        text = bibtex(self._log())
        if not text:
            return
        path = get_save_path(
            self, "Export BibTeX", "synbio_references.bib", "BibTeX (*.bib);;All files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            show_error(self, "Export failed", f"Could not write {path}:\n{exc}")
            return
        show_toast(f"BibTeX exported to {path}")

    def showEvent(self, event: Any) -> None:  # noqa: N802 - Qt override
        self.refresh()
        super().showEvent(event)

    # ── Theme ───────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        self.setStyleSheet(f"""
            MethodsReferencesDialog {{ background: {Colors.BG_DARKEST}; }}
            QLabel#MethodsIntro {{
                color: {Colors.FG_SECONDARY};
                font-size: {Fonts.SIZE_SMALL}px;
            }}
            QLabel#MethodsHeading {{
                color: {Colors.ACCENT_PRIMARY};
                font-size: {Fonts.SIZE_NORMAL}px;
                font-weight: bold;
            }}
            QPlainTextEdit#MethodsText {{
                background: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 8px;
                font-size: {Fonts.SIZE_NORMAL}px;
            }}
        """)

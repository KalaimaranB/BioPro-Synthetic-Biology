"""Renders the rubric verdict for one primer pair, check by check.

Every value shown is read off the ``RubricCheck`` objects the screening engine
returns. This panel performs no comparison: it does not know what the GC window
is, and it does not decide whether a value is inside it. ``check.passed`` is
already True, False or None, and the panel's whole job is to show which, with
the observed value, the threshold it was judged against, where that threshold
came from, and — when it failed — what to do about it.

Two cases get deliberate treatment:

* **A check that could not run** (``passed is None``) is never a silent gap. It
  shows as "not run" with the engine's reason, because a skipped check that
  looks like a pass is how a student ships a primer nothing checked.
* **A failing check** shows the engine's remediation text. A bare FAIL teaches
  nothing; the GFP start-codon case returns a correct failure on an AT-rich
  region, and what the student needs is what to do instead.
"""

from __future__ import annotations

from typing import Any

from karcytics_sdk.plugin.components import (
    BioCaptionLabel,
    BioSectionLabel,
    BioTableWidget,
    QLabel,
    Qt,
    QVBoxLayout,
    QWidget,
)
from karcytics_sdk.plugin.theme_fallback import Colors

from .provenance_badge import ProvenanceBadge

#: Engine verdict -> (text, theme colour token). The engine decides the
#: verdict; this only chooses how to show it.
_VERDICT = {
    "pass": ("PASS", "ACCENT_SUCCESS"),
    "fail": ("FAIL", "ACCENT_DANGER"),
    "incomplete": ("INCOMPLETE", "ACCENT_WARNING"),
}

_OUTCOME = {
    True: ("pass", "ACCENT_SUCCESS"),
    False: ("fail", "ACCENT_DANGER"),
    None: ("not run", "ACCENT_WARNING"),
}

_HEADERS = ("Check", "Observed", "Threshold", "Result", "Basis")

#: Wide enough that the basis column is readable rather than elided.
_MIN_TABLE_WIDTH = 860


def _title(name: str) -> str:
    return name.replace("_", " ").title()


class RubricPanel(QWidget):
    """A table of rubric checks plus the remediation for the failing ones."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._column = QVBoxLayout(self)

        self.verdict_label = QLabel("No candidate selected.")
        self._column.addWidget(self.verdict_label)

        self.table = BioTableWidget()
        self.table.setColumnCount(len(_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_HEADERS))
        self.table.setEditTriggers(BioTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(BioTableWidget.SelectionBehavior.SelectRows)
        # The basis column carries the provenance badge and its citations, so
        # it gets the slack: truncated to "our c..." it would hide the one
        # distinction this panel exists to show.
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        self.table.setMinimumWidth(_MIN_TABLE_WIDTH)
        self._column.addWidget(self.table)

        self.advice_header = BioSectionLabel("What to do about the failures")
        self.advice_header.setVisible(False)
        self._column.addWidget(self.advice_header)

        self.advice_box = QWidget()
        self._advice_layout = QVBoxLayout(self.advice_box)
        self._advice_layout.setContentsMargins(0, 0, 0, 0)
        self._column.addWidget(self.advice_box)

    # ── Rendering ──────────────────────────────────────────────────────

    def clear(self) -> None:
        self.table.setRowCount(0)
        self.verdict_label.setText("No candidate selected.")
        self.verdict_label.setStyleSheet("")
        self._clear_advice()

    def _clear_advice(self) -> None:
        while self._advice_layout.count():
            item = self._advice_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        self.advice_header.setVisible(False)

    def show_candidate(self, checks: Any, summary: Any) -> None:
        """Render a candidate's checks and its overall verdict.

        Args:
            checks: ``RubricCheck`` objects, or the dicts they serialise to.
            summary: The engine's own summary mapping, including ``verdict``.
        """
        rows = [_as_record(check) for check in (checks or [])]
        self._render_verdict(summary or {})
        self._render_rows(rows)
        self._render_advice(rows)

    def _render_verdict(self, summary: dict[str, Any]) -> None:
        verdict = str(summary.get("verdict", "") or "")
        text, token = _VERDICT.get(verdict, (verdict.upper() or "—", "FG_PRIMARY"))
        passed = summary.get("passed", "")
        total = summary.get("total", "")
        skipped = summary.get("skipped", 0)
        detail = f"{passed}/{total} checks passed"
        if skipped:
            # Said out loud: a skipped check is not a pass.
            detail += f", {skipped} not run"
        self.verdict_label.setText(f"{text} — {detail}")
        self.verdict_label.setStyleSheet(
            f"color: {getattr(Colors, token, Colors.FG_PRIMARY)}; font-weight: bold;"
        )

    def _render_rows(self, rows: list[dict[str, Any]]) -> None:
        self.table.setRowCount(len(rows))
        for row, record in enumerate(rows):
            outcome_text, outcome_token = _OUTCOME[record["passed"]]

            self._set(row, 0, _title(record["name"]), tooltip=record["message"])
            observed = record["observed_value"]
            self._set(row, 1, "—" if observed is None else str(observed))
            self._set(row, 2, record["threshold"] or "—")
            self._set(
                row,
                3,
                outcome_text,
                colour=getattr(Colors, outcome_token, Colors.FG_PRIMARY),
                tooltip=record["message"],
            )
            # The basis cell is a widget, not text: it may carry citations.
            self.table.setCellWidget(
                row,
                4,
                ProvenanceBadge(
                    label=record["provenance_label"],
                    kind=record["provenance"],
                    mechanism=record["mechanism"],
                ),
            )
        self.table.resizeColumnsToContents()
        # resizeColumnsToContents sizes the badge column to the widget's hint,
        # which is narrow; let it take the remaining width back.
        self.table.horizontalHeader().setStretchLastSection(True)
        # The badge embeds a citation link, which is taller than a text cell.
        self.table.resizeRowsToContents()

    def _set(
        self,
        row: int,
        column: int,
        text: str,
        colour: str | None = None,
        tooltip: str = "",
    ) -> None:
        from karcytics_sdk.plugin.components import QTableWidget  # noqa: F401

        item = _table_item(text)
        if colour:
            from PySide6.QtGui import QBrush, QColor

            item.setForeground(QBrush(QColor(colour)))
        if tooltip:
            item.setToolTip(tooltip)
        self.table.setItem(row, column, item)

    def _render_advice(self, rows: list[dict[str, Any]]) -> None:
        self._clear_advice()
        failing = [r for r in rows if r["passed"] is False and r["remediation"]]
        skipped = [r for r in rows if r["passed"] is None]

        self.advice_header.setVisible(bool(failing or skipped))

        for record in failing:
            title = QLabel(f"{_title(record['name'])} — {record['message']}")
            title.setWordWrap(True)
            title.setStyleSheet(f"color: {Colors.ACCENT_DANGER};")
            self._advice_layout.addWidget(title)

            advice = BioCaptionLabel(record["remediation"])
            advice.setWordWrap(True)
            self._advice_layout.addWidget(advice)

        for record in skipped:
            note = BioCaptionLabel(f"{_title(record['name'])} could not run: {record['message']}")
            note.setWordWrap(True)
            note.setStyleSheet(f"color: {Colors.ACCENT_WARNING};")
            self._advice_layout.addWidget(note)


def _table_item(text: str) -> Any:
    from PySide6.QtWidgets import QTableWidgetItem

    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item


def _as_record(check: Any) -> dict[str, Any]:
    """Normalise a ``RubricCheck`` or its dict form into one shape.

    Reads only; nothing is computed. A saved workspace reloads checks as dicts,
    so the panel has to accept both without caring which it got.
    """
    if isinstance(check, dict):
        data = check
    else:
        data = check.to_dict()
    return {
        "name": data.get("name", ""),
        "passed": data.get("passed"),
        "message": data.get("message", ""),
        "observed_value": data.get("observed_value"),
        "threshold": data.get("threshold", ""),
        "provenance": data.get("provenance", ""),
        "provenance_label": data.get("provenance_label", ""),
        "mechanism": tuple(data.get("mechanism") or ()),
        "remediation": data.get("remediation", ""),
    }


__all__ = ["RubricPanel"]

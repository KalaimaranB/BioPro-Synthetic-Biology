"""The analysis layer must stay free of the interface.

This is what makes the engines testable headlessly and lets them be reused
outside the desktop app. The brief for the primer work states that "the
pre-commit mypy and test gates enforce this" — they did not. mypy checks types,
not layering, and no test asserted it. This file is that gate.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ANALYSIS = Path("src/karcytics_plugins/synthetic_biology/analysis")
FORBIDDEN_ROOTS = ("PySide6", "PyQt5", "PyQt6")


def _imported_roots(path: Path) -> set[str]:
    """Top-level package names imported by ``path``, at module scope or inside it."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.unit
def test_no_analysis_module_imports_qt():
    offenders = [
        f"{path.relative_to(ANALYSIS)}: {sorted(_imported_roots(path) & set(FORBIDDEN_ROOTS))}"
        for path in sorted(ANALYSIS.rglob("*.py"))
        if _imported_roots(path) & set(FORBIDDEN_ROOTS)
    ]
    assert not offenders, "analysis/ must not import the interface:\n" + "\n".join(offenders)


@pytest.mark.unit
def test_no_analysis_module_imports_the_hub():
    """The plugin depends on the SDK, never on `karcytics.*` from the Hub."""
    offenders = [
        str(path.relative_to(ANALYSIS))
        for path in sorted(ANALYSIS.rglob("*.py"))
        if "karcytics" in _imported_roots(path)
    ]
    assert not offenders, "analysis/ must not import the Hub:\n" + "\n".join(offenders)


@pytest.mark.unit
def test_the_primer_engine_is_importable_without_a_display():
    """The new primer layer must work with no QApplication and no screen.

    Known gap, deliberately not asserted here: importing any `analysis`
    module also executes the plugin's top-level `__init__.py`, which has
    imported `PySide6.QtWidgets` since the PySide6 migration (58a09f8d). So Qt
    is loaded transitively even though no analysis module asks for it, and a
    genuinely headless consumer still pays for Qt. Fixing that means moving the
    Qt import in the package `__init__` behind a function, which touches the
    plugin entry point and is out of scope for this phase.
    """
    import subprocess

    code = (
        "import karcytics_plugins.synthetic_biology.analysis.assembly.primer_screen as s;"
        "import karcytics_plugins.synthetic_biology.analysis.assembly.thermodynamics as t;"
        "from karcytics_plugins.synthetic_biology.analysis.assembly.primer_rubric import PrimerRubric;"
        "checks = s.screen_primer('ATGCATGCATGCATGCAT', '', PrimerRubric());"
        "assert len(checks) == len(s.SINGLE_CHECKS);"
        "assert t.duplex_delta_g('GCGC', 'CGCG') < 0;"
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": "src", "QT_QPA_PLATFORM": "offscreen"},
        check=False,
    )
    assert result.returncode == 0, result.stderr[-1500:]
    assert "ok" in result.stdout

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


# ── The other direction: no science in the views ──────────────────────

UI = Path("src/karcytics_plugins/synthetic_biology/ui")

#: Engine entry points a view must never call, because each one makes or
#: re-derives a scientific judgement the analysis layer already owns.
FORBIDDEN_CALLS = {
    # Mobility is read off the band objects. A build_gel bug was already caught
    # where lanes kept a stale window; recomputing in a view would reintroduce
    # exactly that disagreement.
    "relative_mobility",
    "is_resolvable",
    # Verdicts, screening and thermodynamics belong to the engines.
    "screen_primer",
    "screen_pair",
    "summarise",
    "score",
    "gc_percent",
    "duplex_delta_g",
    "delta_g_37",
    "duplex_enthalpy_entropy",
    "self_dimer",
    "hetero_dimer",
    "hairpin",
    "calculate_tm",
    "longest_homopolymer",
    "count_binding_sites",
}

#: Rubric fields whose literal appearance in a view would mean a threshold was
#: duplicated there instead of read from the rubric.
FORBIDDEN_THRESHOLD_NAMES = {
    "gc_min_percent",
    "gc_max_percent",
    "clamp_min_gc",
    "clamp_max_gc",
    "max_poly_run",
    "pair_tm_tolerance",
    "hairpin_min_dg",
    "self_dimer_min_dg",
    "hetero_dimer_min_dg",
    "three_prime_dimer_min_dg",
}


def _called_names(path: Path) -> set[str]:
    """Every function or method name called in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


@pytest.mark.unit
def test_no_view_recomputes_a_scientific_value():
    """A view renders engine results; it must not derive them.

    The brief for the UI phase puts it plainly: if a view needs a number the
    engine does not return, the number goes into the engine's return value.
    """
    offenders = []
    for path in sorted(UI.rglob("*.py")):
        hits = _called_names(path) & FORBIDDEN_CALLS
        if hits:
            offenders.append(f"{path.relative_to(UI)}: {sorted(hits)}")
    assert not offenders, "ui/ must not compute science:\n" + "\n".join(offenders)


@pytest.mark.unit
def test_no_view_names_a_rubric_threshold_field():
    """A threshold mentioned in a view is a threshold not read from the rubric."""
    offenders = []
    for path in sorted(UI.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        hits = {name for name in FORBIDDEN_THRESHOLD_NAMES if name in text}
        if hits:
            offenders.append(f"{path.relative_to(UI)}: {sorted(hits)}")
    assert not offenders, "ui/ must read thresholds from the rubric:\n" + "\n".join(offenders)


@pytest.mark.unit
def test_the_new_primer_widgets_perform_no_comparisons_on_engine_values():
    """The panels must not re-decide pass/fail or re-place a band.

    Checked structurally: inside the three new widgets, no comparison operator
    may have an engine-derived attribute on either side. `check.passed is None`
    is a read of a decision the engine already made, so identity tests against
    None are allowed; `band.size_bp > 1000` would not be.
    """
    watched = (
        "widgets/rubric_panel.py",
        "widgets/amplification_track.py",
        "widgets/gel_view.py",
    )
    engine_attrs = {
        "passed",
        "size_bp",
        "relative_mobility",
        "intensity",
        "delta_g",
        "observed_value",
        "length",
        "gc_percent",
        "mismatches",
        "template_start",
        "template_end",
    }

    offenders = []
    for name in watched:
        path = UI / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            # `x is None` / `x is not None` reads a decision, it does not make one.
            if all(isinstance(op, ast.Is | ast.IsNot) for op in node.ops):
                continue
            for side in [node.left, *node.comparators]:
                if isinstance(side, ast.Attribute) and side.attr in engine_attrs:
                    offenders.append(f"{name}:{node.lineno} compares .{side.attr}")
    assert not offenders, "views must not judge engine values:\n" + "\n".join(offenders)

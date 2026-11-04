"""Unit tests verifying UI/UX compliance with Karcytics SDK standards.

Covers:
1. Version check and welcome toast triggering during begin_async_init().
2. Main tab bar iconography, mode routing, and theme-managed styling.
3. BioTabWidget usage and theme reactivity in sub-views.
"""

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QTabBar

from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel
from karcytics_plugins.synthetic_biology.ui.views.empirical_analytics_view import (
    EmpiricalAnalyticsView,
)
from karcytics_plugins.synthetic_biology.ui.views.laboratory_execution_view import (
    LaboratoryExecutionView,
)
from karcytics_plugins.synthetic_biology.ui.widgets.bio_tab_widget import BioTabWidget
from karcytics_plugins.synthetic_biology.ui.widgets.part_inspector import PartInspector


def test_synbio_panel_triggers_update_check_on_begin_async_init(destroy_after):
    """Verify that begin_async_init invokes check_for_updates to show the version toast."""
    panel = destroy_after(SynBioPanel())

    with patch.object(panel, "check_for_updates") as mock_check:
        panel.begin_async_init()
        mock_check.assert_called_once_with(
            repo_url="https://github.com/KalaimaranB/Karcytics-SyntheticBiology",
            display_name="Synthetic Biology",
        )


def test_synbio_panel_tab_bar_has_icons_and_11_tabs(destroy_after):
    """Verify that all 11 workspace tabs exist with standard iconography."""
    panel = destroy_after(SynBioPanel())
    tab_bar = panel._tab_bar
    assert isinstance(tab_bar, QTabBar)
    assert tab_bar.count() == 11

    tab_titles = [tab_bar.tabText(i) for i in range(11)]
    assert "🎨 Design" in tab_titles[0]
    assert "🔬 Biological View" in tab_titles[1]
    assert "🧬 Plasmid Assembly" in tab_titles[2]
    assert "✂️ CRISPR Design" in tab_titles[3]
    assert "⚡ Circuit Simulation" in tab_titles[4]
    assert "📊 Empirical Analytics" in tab_titles[5]
    assert "🧫 Laboratory Execution" in tab_titles[6]
    assert "📈 Simulate" in tab_titles[7]
    assert "🔢 Quantitative Data" in tab_titles[8]
    assert "📦 Parts Catalogue" in tab_titles[9]
    assert "🚀 Demo Showcase" in tab_titles[10]


def test_bio_tab_widget_structure():
    """Verify BioTabWidget initializes properly with document mode enabled."""
    tab_widget = BioTabWidget()
    assert tab_widget.documentMode() is True


def test_laboratory_execution_view_uses_bio_tab_widget(destroy_after):
    """Verify LaboratoryExecutionView uses the standardized BioTabWidget."""
    view = destroy_after(LaboratoryExecutionView())
    assert isinstance(view.tabs, BioTabWidget)
    assert view.tabs.count() == 3


def test_empirical_analytics_view_uses_bio_tab_widget(destroy_after):
    """Verify EmpiricalAnalyticsView uses the standardized BioTabWidget."""
    state = SynBioState()
    mock_ctrl = MagicMock()
    view = destroy_after(EmpiricalAnalyticsView(state=state, controller=mock_ctrl))
    assert isinstance(view.tabs, BioTabWidget)
    assert view.tabs.count() == 3


def test_part_inspector_uses_bio_tab_widget(destroy_after):
    """Verify PartInspector uses the standardized BioTabWidget."""
    inspector = destroy_after(PartInspector())
    assert isinstance(inspector.tabs, BioTabWidget)
    assert inspector.tabs.count() == 3


def test_no_unescaped_ampersand_in_mnemonic_widget_text():
    """Qt treats a lone "&" in tab, button, group-box and action text as a
    keyboard-mnemonic marker: "Sequence & PAM" renders as "Sequence _PAM" and
    "Methods & References" as "Methods_References". A literal ampersand must be
    written "&&". Plain QLabel text is unaffected and not checked.
    """
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src"
    pattern = re.compile(
        r"(QGroupBox|Button|addTab|setTitle|addAction|setTabText)\("
        r"[^)]*?\"[^\"]*?(?<!&)&(?!&)[^\"]*?\""
    )
    offenders = [
        f"{path.relative_to(src)}:{lineno}: {line.strip()}"
        for path in src.rglob("*.py")
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if pattern.search(line)
    ]
    assert not offenders, "Escape '&' as '&&':\n" + "\n".join(offenders)


# Smallest display the plugin window has to fit, in logical pixels: a 1280-wide
# laptop, the narrowest this is expected to run on.
#
# Deliberately an absolute budget rather than a ratio, because the requirement
# is absolute — but note it is measured against platform font metrics, and
# those differ enough to matter. The same panel that reports 822 px on macOS
# reported 1332 px on Windows, where wider default fonts and control padding
# inflate every widget's minimum. A margin that looks generous on a developer
# machine can therefore be none at all on CI, so leave real headroom here
# rather than tuning this to whatever the local platform happens to report.
MAX_PANEL_MIN_WIDTH = 1280


def test_panel_fits_a_small_display(destroy_after):
    """The workspace must be shrinkable to fit the screen.

    A window cannot be resized below its layout's minimum, so a single greedy
    widget anywhere in the panel becomes a hard floor on the window — and the
    window then extends past the edge of the display with no way to pull it
    back. This caught a 1,879 px floor set by one label.
    """
    panel = destroy_after(SynBioPanel())
    width = panel.minimumSizeHint().width()
    assert width <= MAX_PANEL_MIN_WIDTH, (
        f"the panel cannot shrink below {width} px, so it will not fit a "
        f"{MAX_PANEL_MIN_WIDTH} px workspace"
    )


#: No single label may demand more than half the window's whole width budget.
#:
#: Expressed as a fraction of MAX_PANEL_MIN_WIDTH rather than a tuned constant,
#: because that is the thing it protects: one label is never entitled to half
#: of what the entire workspace gets.
#:
#: Note what this can and cannot catch. Label widths scale with the platform's
#: font metrics — the same labels measure roughly 1.6x wider on Windows than on
#: macOS — while the window budget is a fixed number of real pixels. So Windows
#: is the binding platform, and a label that is comfortable locally may be the
#: one that fails there. Running this on macOS alone is not evidence; the
#: Windows CI job is what actually enforces it.
MAX_LABEL_MIN_WIDTH = MAX_PANEL_MIN_WIDTH // 2


def test_no_unwrapped_label_inflates_the_window(destroy_after):
    """A long QLabel that cannot wrap reports its whole text as a minimum width.

    Because a QStackedWidget's minimum is the maximum over every page, such a
    label on any one tab sets the floor for the entire window — even while that
    tab is hidden.

    Long labels must therefore either wrap or sit in a scroll area. Both are
    legitimate: wrapping suits prose, while preformatted content (a CSV
    preview, a sequence) must not be re-flowed and scrolls instead. A label
    inside a scroll area is skipped because the viewport, not the label,
    determines what the window has to accommodate.
    """
    from PySide6.QtWidgets import QAbstractScrollArea, QLabel

    def inside_scroll_area(widget) -> bool:
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QAbstractScrollArea):
                return True
            parent = parent.parentWidget()
        return False

    panel = destroy_after(SynBioPanel())
    greedy = [
        (lbl.minimumSizeHint().width(), lbl.text()[:60].replace("\n", " "))
        for lbl in panel.findChildren(QLabel)
        if not lbl.wordWrap()
        and lbl.minimumSizeHint().width() > MAX_LABEL_MIN_WIDTH
        and not inside_scroll_area(lbl)
    ]
    assert not greedy, (
        "these labels put a floor under the window; wrap them, or scroll them "
        "if they are preformatted:\n"
        + "\n".join(f"  {w} px: {t!r}" for w, t in sorted(greedy, reverse=True))
    )


def test_tab_bar_does_not_dictate_the_window_width(destroy_after):
    """Eleven tabs end to end are wider than a laptop screen.

    The bar has to yield that width and fall back to its scroll arrows, or its
    preferred size propagates up and the window opens wider than the display.
    """
    from PySide6.QtWidgets import QSizePolicy

    panel = destroy_after(SynBioPanel())
    assert panel._tab_bar.usesScrollButtons()
    assert panel._tab_bar.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    # The 11 tabs end to end ask for ~1,784 px on macOS and ~2,700 px on Windows.
    # Yielding that width keeps panel.sizeHint().width() strictly smaller than the
    # tab bar's own preferred size, and within the platform-scaled view budget
    # (~1,050 px on macOS, ~1,560 px on Windows where wider fonts/padding inflate
    # default widget hints).
    assert panel.sizeHint().width() < panel._tab_bar.sizeHint().width()
    assert panel.sizeHint().width() <= MAX_PANEL_MIN_WIDTH + 400

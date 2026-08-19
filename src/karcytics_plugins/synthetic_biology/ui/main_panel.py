"""Synthetic Biology workspace — the root panel injected by BioPro.

This is the main entry point UI class.  It sets up the workspace
layout and exposes the BioPro-required interface: signals, export_state,
load_state, cleanup, get_state, set_state.

This file is intentionally thin — all complex widgets will live in their
own modules under ``ui/widgets/``, ``ui/canvas/``, and ``ui/ribbons/``.
"""

from __future__ import annotations

from karcytics_sdk.plugin import PluginBase, get_logger
from karcytics_sdk.plugin.theme_fallback import Colors, Fonts, theme_manager
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..analysis.parts.base import BiologicalPart

# Relative imports — all within this plugin
from ..analysis.state import SynBioState

logger = get_logger(__name__, "synthetic_biology")


class SynBioPanel(PluginBase):
    """Root widget for the Synthetic Biology workspace.

    Injected by BioPro's ``ModuleManager`` as the central workspace
    widget.  Provides the full BioPro plugin interface.

    Layout (future)::

        ┌────────────────────────────────────────────────────┐
        │  Tab Bar: Library | Designer | Checker | Simulate  │
        │  ┌──────────────────────────────────────────────┐  │
        │  │            Toolbar Ribbon (stacked)          │  │
        │  └──────────────────────────────────────────────┘  │
        ├───────────┬────────────────────────┬───────────────┤
        │ Parts     │                        │ Properties &  │
        │ Palette   │   Circuit Canvas       │ Parameters    │
        │───────────│   (drag-and-drop)      │               │
        │ Part      │                        │               │
        │ Search    │                        │               │
        └───────────┴────────────────────────┴───────────────┘

    Signals:
        state_changed:  Emitted on any structural edit (BioPro hooks
                        this to ``HistoryManager`` for undo/redo).
        status_message: Piped to the core status bar.
        results_ready:  Emitted when simulation results are available.
    """

    # ── BioPro-required signals ───────────────────────────────────────
    # state_changed and status_message are provided by PluginBase
    results_ready = pyqtSignal(object)

    def __init__(self, plugin_id: str = "synthetic_biology", parent=None) -> None:
        super().__init__(plugin_id, parent)

        # ── State ─────────────────────────────────────────────────────
        self.state = SynBioState()

        # ── Services ──────────────────────────────────────────────────
        self._setup_services()

        # ── Size policy ───────────────────────────────────────────────
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Build UI ──────────────────────────────────────────────────
        self.setStyleSheet(f"background: {Colors.BG_DARKEST};")
        self._setup_ui()

    def _setup_services(self) -> None:
        """Initialize and wire all core analysis and UI services."""
        from .composition_root import ServiceFactory

        self._factory = ServiceFactory(self.state, self)
        self._factory.build_all()

    # ── UI Construction ───────────────────────────────────────────────

    def _setup_ui(self) -> None:  # noqa: PLR0915
        """Build the workspace layout with ribbons and central canvas/view."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from PyQt6.QtWidgets import QStackedWidget, QTabBar, QWidget

        from .canvas import CircuitCanvas
        from .controllers import (
            CircuitSimulationController,
            CRISPRDesignController,
            EmpiricalAnalyticsController,
            PlasmidAssemblyController,
        )
        from .ribbons import BiologicalViewRibbon, DesignRibbon, SimulateRibbon
        from .ribbons.catalogue_ribbon import CatalogueRibbon
        from .views.catalogue_view import CatalogueView
        from .views.circuit_simulation_view import CircuitSimulationView
        from .views.crispr_view import CRISPRDesignView
        from .views.empirical_analytics_view import EmpiricalAnalyticsView
        from .views.laboratory_execution_view import LaboratoryExecutionView
        from .views.plasmid_assembly_view import PlasmidAssemblyView
        from .views.properties_view import PropertiesView
        from .views.simulate_view import SimulateView

        self._parts_cache: list[BiologicalPart] = []

        # ── Controllers & Attached Views ──────────────────────────────
        self._plasmid_controller = PlasmidAssemblyController(self.state)
        self._crispr_controller = CRISPRDesignController(self.state)
        self._circuit_controller = CircuitSimulationController(self.state)
        self._empirical_controller = EmpiricalAnalyticsController(self.state, self)

        self.plasmid_view = PlasmidAssemblyView(self.state, self._plasmid_controller)
        self.crispr_view = CRISPRDesignView(self.state, self._crispr_controller)
        self.circuit_view = CircuitSimulationView(self.state, self._circuit_controller)
        self.empirical_analytics_view = EmpiricalAnalyticsView(
            self.state, self._empirical_controller
        )
        self.lab_execution_view = LaboratoryExecutionView()
        self.plasmid_tab = self.plasmid_view
        self.crispr_tab = self.crispr_view
        self.circuit_tab = self.circuit_view
        self.empirical_analytics_tab = self.empirical_analytics_view
        self.lab_execution_tab = self.lab_execution_view

        # ── Top Tab Bar ───────────────────────────────────────────────
        self._tab_bar = QTabBar()
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDocumentMode(True)
        self._tab_bar.addTab("Design")
        self._tab_bar.addTab("Biological View")
        self._tab_bar.addTab("Plasmid Assembly")
        self._tab_bar.addTab("CRISPR Design")
        self._tab_bar.addTab("Circuit Simulation")
        self._tab_bar.addTab("Empirical Analytics")
        self._tab_bar.addTab("Laboratory Execution")
        self._tab_bar.addTab("Simulate")
        self._tab_bar.addTab("Quantitative Data")
        self._tab_bar.addTab("Parts Catalogue")
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tab_bar)

        # ── Ribbon Stack ──────────────────────────────────────────────
        self._ribbon_stack = QStackedWidget()

        self._design_ribbon = DesignRibbon(self._factory)
        self._bio_ribbon = BiologicalViewRibbon(self._factory)
        self._plasmid_ribbon = QWidget()
        self._crispr_ribbon = QWidget()
        self._circuit_sim_ribbon = QWidget()
        self._empirical_ribbon = QWidget()
        self._lab_execution_ribbon = QWidget()
        self._sim_ribbon = SimulateRibbon(self._factory)
        self._data_ribbon = QWidget()
        self._catalogue_ribbon = CatalogueRibbon(self._factory)

        self._ribbon_stack.addWidget(self._design_ribbon)
        self._ribbon_stack.addWidget(self._bio_ribbon)
        self._ribbon_stack.addWidget(self._plasmid_ribbon)
        self._ribbon_stack.addWidget(self._crispr_ribbon)
        self._ribbon_stack.addWidget(self._circuit_sim_ribbon)
        self._ribbon_stack.addWidget(self._empirical_ribbon)
        self._ribbon_stack.addWidget(self._lab_execution_ribbon)
        self._ribbon_stack.addWidget(self._sim_ribbon)
        self._ribbon_stack.addWidget(self._data_ribbon)
        self._ribbon_stack.addWidget(self._catalogue_ribbon)
        layout.addWidget(self._ribbon_stack)

        # ── Central Views Stack ───────────────────────────────────────
        self._central_stack = QStackedWidget()

        self._circuit_canvas = CircuitCanvas()
        self._properties_view = PropertiesView()
        self._simulate_view = SimulateView()
        self._catalogue_view = CatalogueView(self._factory.get("parts_catalogue"))

        self._central_stack.addWidget(self._circuit_canvas)
        self._central_stack.addWidget(self._circuit_canvas)
        self._central_stack.addWidget(self.plasmid_view)
        self._central_stack.addWidget(self.crispr_view)
        self._central_stack.addWidget(self.circuit_view)
        self._central_stack.addWidget(self.empirical_analytics_view)
        self._central_stack.addWidget(self.lab_execution_view)
        self._central_stack.addWidget(self._simulate_view)
        self._central_stack.addWidget(self._properties_view)
        self._central_stack.addWidget(self._catalogue_view)

        layout.addWidget(self._central_stack, 1)

        # Connect design ribbon to local cache and views
        self._design_ribbon.part_fetched.connect(self._on_part_added)

        # Connect simulate ribbon to simulation view
        self._sim_ribbon.run_simulation.connect(self._on_run_simulation)

        # ── Status bar ────────────────────────────────────────────────
        self._status_label = QLabel("Synthetic Biology Module ready.")
        self._status_label.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px; "
            f"padding: 4px 12px; background: {Colors.BG_DARK}; "
            f"border-top: 1px solid {Colors.BORDER};"
        )
        layout.addWidget(self._status_label)

        # ── Theme Sync ────────────────────────────────────────────────
        self._apply_theme_styles()
        theme_manager.theme_changed.connect(self._apply_theme_styles)

    def _on_part_added(self, part):
        """Handle a new part fetched from the ribbon."""
        self._parts_cache.append(part)
        self._circuit_canvas.add_part(part)
        self._properties_view.set_parts(self._parts_cache)
        self._simulate_view.set_parts(self._parts_cache)

        # Save to local catalogue and refresh view
        catalogue = self._factory.get("parts_catalogue")
        if catalogue:
            catalogue.add_part(part)
            self._catalogue_view.refresh_table()

    def _on_run_simulation(self, max_time: int, method: str) -> None:
        """Route simulation run request based on selected method."""
        if not self._parts_cache:
            catalogue = self._factory.get("parts_catalogue")
            if catalogue:
                self._parts_cache = catalogue.get_all_parts()
            self._simulate_view.set_parts(self._parts_cache)

        self._simulate_view.plot_time_series(max_time=max_time, method=method)

    def _on_tab_changed(self, index: int) -> None:
        """Handle main tab changes to update ribbon and central view."""
        self._ribbon_stack.setCurrentIndex(index)

        # Switch central view based on tab index
        if index in {0, 1}:
            self._central_stack.setCurrentWidget(self._circuit_canvas)
        elif index == 2:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self.plasmid_view)
        elif index == 3:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self.crispr_view)
        elif index == 4:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self.circuit_view)
        elif index == 5:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self.empirical_analytics_view)
        elif index == 6:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self.lab_execution_view)
        elif index == 7:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self._simulate_view)
            if not self._parts_cache:
                catalogue = self._factory.get("parts_catalogue")
                if catalogue:
                    self._parts_cache = catalogue.get_all_parts()
                self._simulate_view.set_parts(self._parts_cache)
            self._simulate_view.plot_time_series(max_time=100, method="ode")
        elif index == 8:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self._properties_view)
        elif index == 9:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self._catalogue_view)
        else:
            self._central_stack.setCurrentWidget(self._circuit_canvas)

    def _apply_theme_styles(self) -> None:
        """Dynamically refresh all UI colors based on the current theme."""
        global_qss = f"""
            SynBioPanel, QWidget#SynBioPanel {{
                background: {Colors.BG_DARKEST};
                color: {Colors.FG_PRIMARY};
            }}
            QComboBox {{
                background: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: none;
            }}
            QComboBox::down-arrow {{
                width: 0;
                height: 0;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {Colors.FG_PRIMARY};
                margin-right: 6px;
            }}
            QComboBox::down-arrow:on {{
                border-top: none;
                border-bottom: 5px solid {Colors.FG_PRIMARY};
            }}
            QComboBox QAbstractItemView {{
                background: {Colors.BG_DARKEST};
                color: {Colors.FG_PRIMARY};
                selection-background-color: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.BORDER};
            }}
            QSplitter::handle {{
                background-color: {Colors.BORDER};
            }}
            QSplitter::handle:horizontal {{
                width: 2px;
            }}
            QSplitter::handle:vertical {{
                height: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
            }}
            QFrame[frameShape="4"], QFrame[frameShape="5"],
            QFrame#HorizontalSeparator, QFrame#VerticalSeparator {{
                background-color: {Colors.BORDER};
                border: none;
            }}
        """
        self.setStyleSheet(global_qss)

        if hasattr(self, "_tab_bar"):
            self._tab_bar.setStyleSheet(
                f"QTabBar {{ background: {Colors.BG_DARKEST}; border: none; }}"
                f"QTabBar::tab {{ background: {Colors.BG_DARKEST}; "
                f"color: {Colors.FG_SECONDARY}; padding: 10px 20px; border: none; "
                f"border-bottom: 2px solid transparent; "
                f"font-size: {Fonts.SIZE_SMALL}px; font-weight: 600; }}"
                f"QTabBar::tab:selected {{ color: {Colors.ACCENT_PRIMARY}; "
                f"border-bottom: 2px solid {Colors.ACCENT_PRIMARY}; "
                f"background: {Colors.BG_DARKEST}; }}"
                f"QTabBar::tab:hover {{ color: {Colors.FG_PRIMARY}; "
                f"background: {Colors.BG_MEDIUM}; }}"
            )

        if hasattr(self, "_ribbon_stack"):
            self._ribbon_stack.setStyleSheet(
                f"background: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER};"
            )

        # Deep recursion for sub-widgets
        for child in self.findChildren(QWidget):
            if hasattr(child, "_apply_theme_styles") and child is not self:
                child._apply_theme_styles()
            elif hasattr(child, "refresh_styles"):
                child.refresh_styles()
            child.update()

    # ── State Management (BioPro interface) ───────────────────────────

    def get_state(self) -> SynBioState:
        """Package the workspace state for the SDK."""
        return self.state

    def set_state(self, state: SynBioState) -> None:  # type: ignore[override]
        """Restore the workspace from an SDK state object."""
        if not state:
            return
        self.state = state

    def export_state(self) -> dict:
        """Package the workspace state for serialization."""
        return {
            "synbio_state": self.state.to_dict(),
        }

    def load_state(self, state_dict: dict) -> None:
        """Restore the workspace from a serialized state dict."""
        if not state_dict:
            return
        synbio_data = state_dict.get("synbio_state", {})
        self.state = SynBioState.from_dict(synbio_data)

    # ── Resource Lifecycle ────────────────────────────────────────────

    def cleanup(self) -> None:
        """Resource cleanup on plugin close."""
        self.logger.info("Cleaning up Synthetic Biology workspace...")
        emp_view = getattr(self, "empirical_analytics_view", None)
        if emp_view is not None:
            try:
                emp_view.teardown()
            except Exception as ex:
                self.logger.warning(f"Error during view teardown: {ex}")
        super().cleanup()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.logger.info(f"SynBioPanel resized: {self.width()}x{self.height()}")

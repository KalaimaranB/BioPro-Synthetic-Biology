"""Synthetic Biology workspace — the root panel injected by Karcytics.

This is the main entry point UI class.  It sets up the workspace
layout and exposes the Karcytics-required interface: signals, export_state,
load_state, cleanup, get_state, set_state.

This file is intentionally thin — all complex widgets will live in their
own modules under ``ui/widgets/``, ``ui/canvas/``, and ``ui/ribbons/``.
"""

from __future__ import annotations

from typing import Any

from karcytics_sdk.plugin import PluginBase, get_logger
from karcytics_sdk.plugin.theme_fallback import Colors, Fonts, theme_manager
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

# Relative imports — all within this plugin
from ..analysis.state import SynBioState

logger = get_logger(__name__, "synthetic_biology")


class SynBioPanel(PluginBase):
    """Root widget for the Synthetic Biology workspace.

    Injected by Karcytics's ``ModuleManager`` as the central workspace
    widget.  Provides the full Karcytics plugin interface.

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
        state_changed:  Emitted on any structural edit (Karcytics hooks
                        this to ``HistoryManager`` for undo/redo).
        status_message: Piped to the core status bar.
        results_ready:  Emitted when simulation results are available.
    """

    # ── Karcytics-required signals ────────────────────────────────────
    # state_changed and status_message are provided by PluginBase
    results_ready = Signal(object)
    panel_ready = Signal()
    data_ready = Signal()

    def __init__(
        self,
        plugin_id: Any = "synthetic_biology",
        parent: QWidget | None = None,
        context: Any | None = None,
        **kwargs: Any,
    ) -> None:
        actual_parent: QWidget | None
        if isinstance(plugin_id, QWidget):
            actual_parent = plugin_id
            actual_plugin_id = "synthetic_biology"
        else:
            actual_plugin_id = str(plugin_id) if plugin_id else "synthetic_biology"
            actual_parent = parent

        raw_context = context or kwargs.get("context")

        if actual_parent is not None and isinstance(actual_parent, QWidget):
            qt_parent = actual_parent
        else:
            qt_parent = None
            if actual_parent is not None and raw_context is None:
                raw_context = actual_parent

        self.context = raw_context

        super().__init__(actual_plugin_id, qt_parent)
        self.logger = getattr(self, "logger", None) or logger

        # ── State ─────────────────────────────────────────────────────
        self.state = SynBioState()

        # ── Services ──────────────────────────────────────────────────
        self._setup_services()

        # ── Size policy ───────────────────────────────────────────────
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── Build UI ──────────────────────────────────────────────────
        self.setStyleSheet(f"background: {Colors.BG_DARKEST};")
        self._methods_dialog: Any = None
        self._setup_ui()
        self._setup_workspace_persistence()

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

        from PySide6.QtWidgets import QStackedWidget, QTabBar

        from .canvas import CircuitCanvas
        from .controllers import (
            CircuitSimulationController,
            CRISPRDesignController,
            EmpiricalAnalyticsController,
            PlasmidAssemblyController,
        )
        from .ribbons import (
            BiologicalViewRibbon,
            CatalogueRibbon,
            DesignRibbon,
            PlaceholderRibbon,
            SimulateRibbon,
        )
        from .views.catalogue_view import CatalogueView
        from .views.circuit_simulation_view import CircuitSimulationView
        from .views.crispr_view import CRISPRDesignView
        from .views.demo_showcase_view import DemoShowcaseView
        from .views.empirical_analytics_view import EmpiricalAnalyticsView
        from .views.laboratory_execution_view import LaboratoryExecutionView
        from .views.plasmid_assembly_view import PlasmidAssemblyView
        from .views.properties_view import PropertiesView
        from .views.simulate_view import SimulateView
        from .wizards.demo_tour import DemoTourBar, build_demo_tour_steps

        # ── Controllers & Attached Views ──────────────────────────────
        self._plasmid_controller = PlasmidAssemblyController(self.state)
        self._crispr_controller = CRISPRDesignController(self.state)
        self._circuit_controller = CircuitSimulationController(self.state)
        self._empirical_controller = EmpiricalAnalyticsController(self.state, self)

        self.plasmid_view = PlasmidAssemblyView(
            self.state,
            self._plasmid_controller,
            catalogue=self._factory.get("parts_catalogue"),
        )
        self.crispr_view = CRISPRDesignView(self.state, self._crispr_controller)
        self.circuit_view = CircuitSimulationView(self.state, self._circuit_controller)
        self.empirical_analytics_view = EmpiricalAnalyticsView(
            self.state, self._empirical_controller
        )
        self.lab_execution_view = LaboratoryExecutionView()
        self.demo_showcase_view = DemoShowcaseView(self.state, main_panel=self)
        self.plasmid_tab = self.plasmid_view
        self.crispr_tab = self.crispr_view
        self.circuit_tab = self.circuit_view
        self.empirical_analytics_tab = self.empirical_analytics_view
        self.lab_execution_tab = self.lab_execution_view
        self.demo_showcase_tab = self.demo_showcase_view

        # ── Top Tab Bar ───────────────────────────────────────────────
        self._tab_bar = QTabBar()
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDocumentMode(True)
        self._tab_bar.addTab("🎨 Design")
        self._tab_bar.addTab("🔬 Biological View")
        self._tab_bar.addTab("🧬 Plasmid Assembly")
        self._tab_bar.addTab("✂️ CRISPR Design")
        self._tab_bar.addTab("⚡ Circuit Simulation")
        self._tab_bar.addTab("📊 Empirical Analytics")
        self._tab_bar.addTab("🧫 Laboratory Execution")
        self._tab_bar.addTab("📈 Simulate")
        self._tab_bar.addTab("🔢 Quantitative Data")
        self._tab_bar.addTab("📦 Parts Catalogue")
        self._tab_bar.addTab("🚀 Demo Showcase")
        self._tab_bar.currentChanged.connect(self._on_tab_changed)
        if hasattr(theme_manager, "apply_style"):
            theme_manager.apply_style(
                self._tab_bar,
                """
                QTabBar {
                    background: {BG_DARKEST};
                    border: none;
                    border-bottom: 1px solid {BORDER};
                }
                QTabBar::tab {
                    background: {BG_DARKEST};
                    color: {FG_SECONDARY};
                    padding: 10px 18px;
                    border: none;
                    border-bottom: 2px solid transparent;
                    font-size: 13px;
                    font-weight: 500;
                }
                QTabBar::tab:selected {
                    color: {ACCENT_PRIMARY};
                    border-bottom: 2px solid {ACCENT_PRIMARY};
                    background: {BG_DARKEST};
                    font-weight: 600;
                }
                QTabBar::tab:hover {
                    color: {FG_PRIMARY};
                    background: {BG_MEDIUM};
                }
                """,
            )
        # ── Workspace controls beside the tab bar ─────────────────────
        # Open / Methods & References / Save sit on the tab row so they are
        # reachable from every tab. The Save button is the SDK's
        # WorkspaceSaveButton: it shows unsaved state and splits into
        # "update" vs "save as new" on its own.
        from karcytics_sdk.plugin.components import SecondaryButton, WorkspaceSaveButton
        from PySide6.QtWidgets import QHBoxLayout

        tab_row = QWidget(self)
        tab_row_layout = QHBoxLayout(tab_row)
        tab_row_layout.setContentsMargins(0, 0, 8, 0)
        tab_row_layout.setSpacing(6)
        tab_row_layout.addWidget(self._tab_bar, 1)

        self._btn_open_workspace = SecondaryButton("📂 Open", tab_row)
        self._btn_open_workspace.setToolTip("Open a saved Synthetic Biology workflow")
        self._btn_open_workspace.clicked.connect(self.open_workspace)

        self._btn_methods = SecondaryButton("📚 Methods && References", tab_row)
        self._btn_methods.setToolTip(
            "Materials & Methods paragraph and references for what this workspace ran"
        )
        self._btn_methods.clicked.connect(self.open_methods_dialog)

        self._save_button = WorkspaceSaveButton(tab_row)
        self._save_button.save_requested.connect(self.save_workspace_as)
        self._save_button.update_requested.connect(self.save_workspace)

        for control in (self._btn_open_workspace, self._btn_methods, self._save_button):
            tab_row_layout.addWidget(control)
        layout.addWidget(tab_row)

        # ── Guided demo tour ──────────────────────────────────────────
        # Hidden until the Demo Showcase starts a tour. Sits under the tab bar
        # so the narration stays visible while the tour drives the tabs.
        self._demo_tour_bar = DemoTourBar(build_demo_tour_steps(), self)
        self._demo_tour_bar.setVisible(False)
        self._demo_tour_bar.step_changed.connect(self._on_demo_tour_step)
        self._demo_tour_bar.tour_finished.connect(self.close_methods_dialog)
        layout.addWidget(self._demo_tour_bar)

        # ── Ribbon Stack ──────────────────────────────────────────────
        self._ribbon_stack = QStackedWidget()

        self._design_ribbon = DesignRibbon(self._factory)
        self._bio_ribbon = BiologicalViewRibbon(self._factory)
        self._plasmid_ribbon = PlaceholderRibbon("Plasmid Assembly Ribbon")
        self._crispr_ribbon = PlaceholderRibbon("CRISPR Design Ribbon")
        self._circuit_sim_ribbon = PlaceholderRibbon("Circuit Simulation Ribbon")
        self._empirical_ribbon = PlaceholderRibbon("Empirical Analytics Ribbon")
        self._lab_execution_ribbon = PlaceholderRibbon("Laboratory Execution Ribbon")
        self._sim_ribbon = SimulateRibbon(self._factory)
        self._data_ribbon = PlaceholderRibbon("Quantitative Data Ribbon")
        self._catalogue_ribbon = CatalogueRibbon(self._factory)
        self._demo_ribbon = PlaceholderRibbon("Demo Showcase Ribbon")

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
        self._ribbon_stack.addWidget(self._demo_ribbon)
        layout.addWidget(self._ribbon_stack)

        # ── Central Views Stack ───────────────────────────────────────
        self._central_stack = QStackedWidget()

        self._circuit_canvas = CircuitCanvas(state=self.state)
        self._properties_view = PropertiesView(state=self.state)
        self._simulate_view = SimulateView(state=self.state, controller=self._circuit_controller)
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
        self._central_stack.addWidget(self.demo_showcase_view)

        layout.addWidget(self._central_stack, 1)

        # Connect design ribbon to local cache and views
        self._design_ribbon.part_fetched.connect(self._on_part_added)

        # Connect biological view ribbon toggles to circuit canvas
        self._bio_ribbon.toggle_seq.toggled.connect(self._circuit_canvas.set_show_sequences)
        self._bio_ribbon.toggle_stubs.toggled.connect(self._circuit_canvas.set_show_stubs)

        # Connect properties view state sync
        if hasattr(self, "state_changed"):
            self._properties_view.state_changed.connect(self.state_changed)

        # Connect simulate ribbon to simulation view
        self._sim_ribbon.run_simulation.connect(self._on_run_simulation)

        # ── Status bar ────────────────────────────────────────────────
        self._status_label = QLabel("Synthetic Biology Module ready.")
        layout.addWidget(self._status_label)

        # ── Theme Sync ────────────────────────────────────────────────
        self._apply_theme_styles()
        theme_manager.theme_changed.connect(self._apply_theme_styles)

    def begin_async_init(self) -> None:
        """Chain Phase 2 async initialization to satisfy the Hub's Ready Gate protocol."""
        self.logger.info("[phase2] begin_async_init: initializing SynBio panel")

        # Asynchronously verify module updates and surface standard notification toast
        if hasattr(self, "check_for_updates"):
            self.check_for_updates(
                repo_url="https://github.com/KalaimaranB/Karcytics-SyntheticBiology",
                display_name="Synthetic Biology",
            )

        def _complete_init() -> None:
            try:
                import shiboken6

                if not shiboken6.isValid(self):
                    return
            except Exception:
                pass
            self.logger.info("[phase2] SynBioPanel panel_ready and data_ready emitting")
            self.panel_ready.emit()
            self.data_ready.emit()

        QTimer.singleShot(50, _complete_init)

    def _on_part_added(self, part):
        """Handle a new part fetched from the ribbon.

        The part goes into the shared state first; every view then re-reads it
        from there, so the Design, Properties, Assembly and Simulate tabs all
        show the same construct.
        """
        self.state.add_design_part(part)
        self._refresh_views_from_state()

        # Save to local catalogue and refresh view
        catalogue = self._factory.get("parts_catalogue")
        if catalogue:
            catalogue.add_part(part)
            self._catalogue_view.refresh_table()

        self.state.state_changed()
        if hasattr(self, "state_changed"):
            self.state_changed.emit()

    def _on_run_simulation(self, max_time: int, method: str) -> None:
        """Route simulation run request based on selected method."""
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
            if (
                not self._simulate_view.is_circuit_empty()
                and self._simulate_view._last_simulation_result is None
            ):
                self._simulate_view.plot_time_series(max_time=100, method="ode")
        elif index == 8:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self._properties_view)
        elif index == 9:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self._catalogue_view)
        elif index == 10:  # noqa: PLR2004
            self._central_stack.setCurrentWidget(self.demo_showcase_view)
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

        if hasattr(self, "_ribbon_stack"):
            self._ribbon_stack.setStyleSheet(
                f"background: {Colors.BG_DARK}; border-bottom: 1px solid {Colors.BORDER};"
            )

        if hasattr(self, "_status_label"):
            self._status_label.setStyleSheet(
                f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px; "
                f"padding: 4px 12px; background: {Colors.BG_DARK}; "
                f"border-top: 1px solid {Colors.BORDER};"
            )

        # Deep recursion for sub-widgets
        for child in self.findChildren(QWidget):
            if hasattr(child, "_apply_theme_styles") and child is not self:
                child._apply_theme_styles()
            elif hasattr(child, "refresh_styles"):
                child.refresh_styles()
            child.update()

    # ── State Management (Karcytics interface) ─────────────────────────

    def get_state(self) -> SynBioState:
        """Package the workspace state for the SDK."""
        return self.state

    def set_state(self, state: SynBioState) -> None:  # type: ignore[override]
        """Restore the workspace from an SDK state object."""
        if not state:
            return
        self.state.copy_from(state)
        self._refresh_views_from_state()

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
        self.state.load_from_dict(synbio_data)
        self._refresh_views_from_state()

    # ── Workspace persistence (save / reopen through the Hub project) ──

    def _project_manager(self) -> Any:
        """The Hub's project manager, or ``None`` when no project is open.

        ``window().project_manager`` is the real ``ProjectManager`` in-process
        and the SDK's ``RemoteProjectManager`` when isolated; both are ``None``
        with no project open, which callers treat as a normal case.
        """
        window = self.window()
        if window is None or window is self:
            return None
        return getattr(window, "project_manager", None)

    def _setup_workspace_persistence(self) -> None:
        from .workspace_persistence import WorkspacePersistence

        self._persistence = WorkspacePersistence(
            self.state, self.plugin_id, self._project_manager, self
        )
        self._persistence.dirty_changed.connect(self._save_button.set_dirty)
        self._save_button.set_dirty(False)
        self._save_button.set_workflow_active(False)

        # Unsaved-changes tracking by content hash, so every way the state can
        # change is caught without each mutation site flagging itself.
        self._dirty_timer = QTimer(self)
        self._dirty_timer.setInterval(1000)
        self._dirty_timer.timeout.connect(self._persistence.check_dirty)
        self._dirty_timer.start()

        # The SDK's shared autosave loop. "Unsaved changes" is reported False
        # with no project open: there is nowhere to save to, so the loop should
        # neither try nor nag.
        self.setup_workflow_autosave(
            has_saved_once=lambda: self._persistence.filename is not None,
            save=self._persistence.quiet_save,
            has_unsaved_changes=lambda: (
                self._persistence.has_project() and self._persistence.is_dirty()
            ),
        )

    def prepare_for_replacement(self, action: str) -> bool:
        """Confirm, then unlink from the current workflow, before the whole
        workspace is replaced (e.g. by loading the demo).

        Returns False if the user declines. Unlinking matters as much as
        asking: a workspace opened from workflow X and then replaced must not
        have its next Save overwrite X with unrelated content.
        """
        from karcytics_sdk.plugin.dialogs import ask_yes_no

        self._persistence.check_dirty()
        if self._persistence.is_dirty() and not ask_yes_no(
            self,
            title="Replace the current workspace?",
            message=(
                f"{action} will replace the current workspace, which has unsaved changes. Continue?"
            ),
        ):
            return False
        self._persistence.filename = None
        self._persistence.metadata = {}
        self._save_button.set_workflow_active(False)
        return True

    def _notify_saved(self, filename: str) -> None:
        self._save_button.set_workflow_active(True)
        controller = getattr(self, "_workflow_autosave_controller", None)
        if controller is not None:
            controller.notify_saved()
        name = self._persistence.metadata.get("name") or filename
        if hasattr(self, "_status_label"):
            self._status_label.setText(f"💾 Saved workflow “{name}” ({filename}).")

    def save_workspace_as(self) -> str | None:
        """Ask for a name and save the workspace as a new workflow."""
        from karcytics_sdk.plugin.dialogs import SaveWorkflowDialog, show_error, show_warning
        from karcytics_sdk.plugin.toast import show_toast

        if not self._persistence.has_project():
            show_warning(
                self,
                title="No project open",
                message=(
                    "Open or create a project in the Karcytics Hub to save this "
                    "workspace as a workflow."
                ),
            )
            return None

        dialog = SaveWorkflowDialog(self)
        if not dialog.exec():
            return None
        try:
            filename = self._persistence.save(metadata=dialog.get_metadata(), filename=None)
        except Exception as ex:
            show_error(self, "Save failed", f"The workspace could not be saved:\n{ex}")
            return None
        self._notify_saved(filename)
        show_toast(f"Workspace saved as {filename}")
        return filename

    def save_workspace(self) -> str | None:
        """Save over the current workflow, or ask for a name if there isn't one."""
        from karcytics_sdk.plugin.dialogs import show_error
        from karcytics_sdk.plugin.toast import show_toast

        if self._persistence.filename is None:
            return self.save_workspace_as()
        try:
            filename = self._persistence.save()
        except Exception as ex:
            show_error(self, "Save failed", f"The workspace could not be saved:\n{ex}")
            return None
        self._notify_saved(filename)
        show_toast("Workspace saved")
        return filename

    def save_demo_workspace(self) -> str | None:
        """Save the demo under a fixed name, without dialogs, for the guided tour.

        A fixed filename means re-running the tour overwrites the demo workflow
        instead of piling up copies. Returns ``None`` (and says why) when there
        is no project to save into.
        """
        from karcytics_sdk.plugin.toast import show_toast

        if not self._persistence.has_project():
            show_toast(
                "No Karcytics project is open, so the demo was not saved. Open a "
                "project in the Hub to try save and reopen."
            )
            return None
        try:
            filename = self._persistence.save(
                metadata={
                    "name": "BIOL341 demo — repressilator",
                    "description": (
                        "Three-gene repressilator strand from the Demo Showcase, with its "
                        "simulations and methods log."
                    ),
                    "tags": ["demo", "biol341", "repressilator"],
                },
                filename="biol341_demo_repressilator.json",
            )
        except Exception as ex:
            show_toast(f"The demo could not be saved: {ex}")
            return None
        self._notify_saved(filename)
        show_toast(f"Saved to the project as {filename}")
        return filename

    def open_workspace(self) -> None:
        """Pick one of this module's saved workflows and open it."""
        from karcytics_sdk.plugin.dialogs import ask_yes_no, show_error, show_info, show_warning
        from PySide6.QtWidgets import QInputDialog

        if not self._persistence.has_project():
            show_warning(
                self,
                title="No project open",
                message="Open a project in the Karcytics Hub to see its saved workflows.",
            )
            return

        try:
            workflows = self._persistence.list_workflows()
        except Exception as ex:
            show_error(self, "Open failed", f"Could not list workflows:\n{ex}")
            return
        if not workflows:
            show_info(
                self, "No saved workflows", "This project has no Synthetic Biology workflows yet."
            )
            return

        labels = []
        for wf in workflows:
            stamp = str(wf.get("timestamp", ""))[:16].replace("T", " ")
            labels.append(f"{wf.get('name') or wf.get('filename')}  —  {stamp}")
        choice, ok = QInputDialog.getItem(
            self, "Open workflow", "Saved Synthetic Biology workflows:", labels, 0, False
        )
        if not ok:
            return
        chosen = workflows[labels.index(choice)]

        if self._persistence.is_dirty() and not ask_yes_no(
            self,
            title="Discard unsaved changes?",
            message="This workspace has unsaved changes. Open the workflow anyway?",
        ):
            return

        filename = str(chosen.get("filename"))
        try:
            payload = self._persistence.fetch_payload(filename)
        except Exception as ex:
            show_error(self, "Open failed", f"Could not read {filename}:\n{ex}")
            return
        self.load_workflow(payload, filename=filename, metadata=chosen)

    def load_workflow(
        self,
        payload: dict,
        filename: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Restore a saved workflow — the hook the Hub calls.

        The Hub's workflow dashboard delivers a saved workflow by calling
        ``panel.load_workflow(payload, filename=..., metadata=...)``, directly
        when in-process and through the SDK daemon's ``inject_workflow`` RPC
        when isolated. This panel had no such method, so opening a Synthetic
        Biology workflow from the Hub silently did nothing.
        """
        from karcytics_sdk.plugin.dialogs import show_error

        from .workspace_persistence import UnsupportedWorkflowError

        try:
            self._persistence.apply_payload(payload, filename=filename, metadata=metadata)
        except UnsupportedWorkflowError as ex:
            show_error(self, "Cannot open workflow", str(ex))
            return

        self._refresh_views_from_state()
        self._restore_results_from_state()
        self._save_button.set_workflow_active(filename is not None)
        self._save_button.set_dirty(False)

        name = (metadata or {}).get("name") or filename or "workflow"
        if hasattr(self, "_status_label"):
            self._status_label.setText(f"📂 Opened “{name}”.")

    def _restore_results_from_state(self) -> None:
        """Redraw saved results that the views do not re-read on their own.

        ``reload_from_state`` restores designs, but the Circuit Simulation plot
        and the CRISPR table are drawn from results the views were handed, not
        from the state — so without this a reopened workspace has its circuit
        back and its plots blank.
        """
        result = self.state.get_simulation_result()
        if result is not None and getattr(result, "time_points", None):
            try:
                self.circuit_view.render_simulation_results(result, announce=False)
            except Exception as ex:
                self.logger.warning(f"Could not redraw the saved simulation: {ex}")

        candidates = self.state.get_grna_candidates()
        if candidates:
            try:
                self.crispr_view.render_grna_results(candidates, announce=False)
            except Exception as ex:
                self.logger.warning(f"Could not redraw the saved guide RNAs: {ex}")

    # ── Methods & References ──────────────────────────────────────────

    def open_methods_dialog(self) -> None:
        """Show the Methods & References dialog for this workspace (non-modal)."""
        from .wizards.methods_dialog import MethodsReferencesDialog

        if self._methods_dialog is None:
            self._methods_dialog = MethodsReferencesDialog(self.state, self)
        self._methods_dialog.refresh()
        self._methods_dialog.show()
        self._methods_dialog.raise_()

    def close_methods_dialog(self) -> None:
        if self._methods_dialog is not None:
            self._methods_dialog.close()

    # ── Guided demo tour ──────────────────────────────────────────────

    def start_demo_tour(self) -> None:
        """Show the tour bar at step one and navigate to that step."""
        self._demo_tour_bar.start()

    def _on_demo_tour_step(self, index: int) -> None:
        """Navigate to a tour step: switch the tab, then run its action.

        The action runs after the tab switch so whatever it triggers renders on
        a tab the audience is already looking at. Failures are logged and
        swallowed: a tour that stops dead mid-presentation is worse than one
        that skips a simulation.
        """
        step = self._demo_tour_bar.current_step
        if step is None:
            return

        # A step that opened the Methods dialog should not leave it covering
        # the next one; the step that wants it reopens it in its action.
        self.close_methods_dialog()

        if 0 <= step.tab_index < self._tab_bar.count():
            self._tab_bar.setCurrentIndex(step.tab_index)

        if step.action is not None:
            try:
                step.action(self)
            except Exception as ex:
                self.logger.warning(f"Demo tour step {index + 1} action failed: {ex}")

    def _refresh_views_from_state(self) -> None:
        """Re-read the shared state into every view after a session restore.

        ``self.state`` is mutated in place rather than rebound, so the
        controllers and views still point at the right object; they just need
        to be told the contents changed.
        """
        for view_attr in (
            "_circuit_canvas",
            "_properties_view",
            "_simulate_view",
            "plasmid_view",
            "crispr_view",
            "circuit_view",
        ):
            view = getattr(self, view_attr, None)
            if view is not None and hasattr(view, "reload_from_state"):
                try:
                    view.reload_from_state()
                except Exception as ex:
                    self.logger.warning(f"Error refreshing {view_attr} from state: {ex}")

    # ── Resource Lifecycle ────────────────────────────────────────────

    def cleanup(self) -> None:
        """Resource cleanup on plugin close."""
        self.logger.info("Cleaning up Synthetic Biology workspace...")

        # 1. Teardown views with background workers
        for view_attr in (
            "empirical_analytics_view",
            "lab_execution_view",
            "_simulate_view",
            "crispr_view",
            "plasmid_view",
            "circuit_view",
        ):
            view = getattr(self, view_attr, None)
            if view is not None and hasattr(view, "teardown"):
                try:
                    view.teardown()
                except Exception as ex:
                    self.logger.warning(f"Error during {view_attr} teardown: {ex}")

        # 2. Teardown controllers managing QThread instances
        for ctrl_attr in (
            "_crispr_controller",
            "_circuit_controller",
            "_plasmid_controller",
            "_empirical_controller",
        ):
            ctrl = getattr(self, ctrl_attr, None)
            if ctrl is not None and hasattr(ctrl, "teardown"):
                try:
                    ctrl.teardown()
                except Exception as ex:
                    self.logger.warning(f"Error during {ctrl_attr} teardown: {ex}")

        try:
            super().cleanup()
        except Exception as ex:
            self.logger.warning(f"Error during super().cleanup(): {ex}")

    def closeEvent(self, event) -> None:
        """Perform graceful resource teardown and allow Qt window destruction."""
        self.logger.info("SynBioPanel closeEvent triggered: shutting down background threads.")
        try:
            self.cleanup()
        except Exception as ex:
            self.logger.warning(f"Error during closeEvent cleanup: {ex}")

        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.logger.info(f"SynBioPanel resized: {self.width()}x{self.height()}")

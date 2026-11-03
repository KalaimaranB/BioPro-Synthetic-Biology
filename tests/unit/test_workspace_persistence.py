"""Save and reopen a workspace through the Hub project.

``FakeProjectManager`` mirrors the core ``ProjectManager`` / ``WorkflowManager``
contract this module depends on (``karcytics/core/projects/workflows.py``): a
filename derived from the workflow name when none is given, the module id
stamped into the metadata on save, ``workflows.list_all()`` returning metadata
with the filename added, and ``load_workflow_payload`` returning the payload.
"""

from __future__ import annotations

import copy
import inspect
from typing import Any

import pytest

from karcytics_plugins.synthetic_biology.analysis.citations import primer_step
from karcytics_plugins.synthetic_biology.analysis.parts.components import CDS, Promoter
from karcytics_plugins.synthetic_biology.analysis.state import SynBioState
from karcytics_plugins.synthetic_biology.ui.workspace_persistence import (
    WORKFLOW_SCHEMA,
    WORKFLOW_SCHEMA_VERSION,
    NoProjectOpenError,
    UnsupportedWorkflowError,
    WorkspacePersistence,
    build_payload,
    extract_state_dict,
)

MODULE_ID = "synthetic_biology"


class _Workflows:
    def __init__(self, store: dict[str, dict[str, Any]]) -> None:
        self._store = store

    def list_all(self) -> list[dict[str, Any]]:
        out = []
        for name, data in self._store.items():
            meta = dict(data["metadata"])
            meta["filename"] = name
            out.append(meta)
        out.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
        return out


class FakeProjectManager:
    def __init__(self) -> None:
        self.store: dict[str, dict[str, Any]] = {}
        self.workflows = _Workflows(self.store)

    def save_workflow(self, module_id, payload, metadata, filename=None, attachments=None):
        if filename:
            name = filename
        else:
            safe = "".join(c for c in metadata["name"] if c.isalnum() or c == " ")
            safe = safe.replace(" ", "_").lower() or "untitled_workflow"
            name, counter = f"{safe}.json", 1
            while name in self.store:
                name = f"{safe}_{counter}.json"
                counter += 1
        metadata = dict(metadata)
        metadata["module"] = module_id
        # Deep-copy: the real manager serialises to disk, so a later mutation of
        # the live state must not leak into what was saved.
        self.store[name] = {"metadata": metadata, "payload": copy.deepcopy(payload)}
        return name

    def load_workflow_payload(self, filename):
        return copy.deepcopy(self.store[filename]["payload"])


def _state_with_design() -> SynBioState:
    state = SynBioState()
    state.add_design_part(
        Promoter(id="pTet", name="pTet", sequence="TCCCTATCAG", y_max=10.0, repressors=["TetR"])
    )
    state.add_design_part(CDS(id="gfp", name="GFP", sequence="ATGAGTAAA", product="GFP"))
    state.record_method(primer_step(60.0, 60.41, 59.55))
    return state


# ── The bug that made reopen impossible ────────────────────────────────────


@pytest.mark.unit
def test_plugin_set_state_actually_restores():
    """``set_state`` used to call the classmethod ``from_dict`` on the live state,
    discarding the new object it returned: restore was a silent no-op.
    """
    from karcytics_plugins.synthetic_biology import SyntheticBiologyPlugin

    saved = _state_with_design().to_dict()

    class _Panel:
        def __init__(self) -> None:
            self.state = SynBioState()
            self.refreshed = 0

        def _refresh_views_from_state(self) -> None:
            self.refreshed += 1

    plugin = SyntheticBiologyPlugin.__new__(SyntheticBiologyPlugin)
    panel = _Panel()
    held = panel.state
    plugin._panel = panel

    plugin.set_state(saved)

    assert panel.state is held, "restore must mutate in place, not rebind"
    assert [p.id for p in panel.state.design_parts] == ["pTet", "gfp"]
    assert panel.refreshed == 1


@pytest.mark.unit
def test_panel_implements_the_hub_load_workflow_hook(destroy_after):
    """The Hub calls ``panel.load_workflow(payload, filename=, metadata=)`` and
    inspects the signature for those keywords. Without the method, opening a
    workflow from the Hub dashboard did nothing.
    """
    from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel

    panel = destroy_after(SynBioPanel())
    params = inspect.signature(panel.load_workflow).parameters
    assert {"filename", "metadata"} <= set(params)


# ── Payload format ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_payload_round_trip_and_accepted_shapes():
    state = _state_with_design()
    payload = build_payload(state)
    assert payload["schema"] == WORKFLOW_SCHEMA
    assert payload["version"] == WORKFLOW_SCHEMA_VERSION

    assert extract_state_dict(payload) == state.to_dict()
    # Untagged shape from SynBioPanel.export_state before versioning.
    assert extract_state_dict({"synbio_state": state.to_dict()}) == state.to_dict()
    # A bare state dict, as a session snapshot carries it.
    assert extract_state_dict(state.to_dict()) == state.to_dict()


@pytest.mark.unit
@pytest.mark.parametrize(
    "payload",
    [
        {},
        None,
        {"schema": "karcytics.flow_cytometry.workspace", "synbio_state": {"data": {}}},
        {
            "schema": WORKFLOW_SCHEMA,
            "version": WORKFLOW_SCHEMA_VERSION + 1,
            "synbio_state": {"data": {}},
        },
        {"schema": WORKFLOW_SCHEMA, "version": 1, "synbio_state": {}},
    ],
)
def test_unreadable_payloads_are_refused(payload):
    with pytest.raises(UnsupportedWorkflowError):
        extract_state_dict(payload)


@pytest.mark.unit
def test_refused_payload_leaves_the_workspace_untouched():
    state = _state_with_design()
    before = state.to_dict()
    persistence = WorkspacePersistence(state, MODULE_ID, lambda: None)

    with pytest.raises(UnsupportedWorkflowError):
        persistence.apply_payload({"schema": "something.else"})
    assert state.to_dict() == before


# ── Save / open through the project ────────────────────────────────────────


@pytest.mark.unit
def test_save_needs_a_project_and_a_name():
    state = _state_with_design()
    with pytest.raises(NoProjectOpenError):
        WorkspacePersistence(state, MODULE_ID, lambda: None).save({"name": "x"})

    pm = FakeProjectManager()
    with pytest.raises(ValueError):
        WorkspacePersistence(state, MODULE_ID, lambda: pm).save()


@pytest.mark.unit
def test_save_then_update_overwrites_the_same_workflow():
    pm = FakeProjectManager()
    state = _state_with_design()
    persistence = WorkspacePersistence(state, MODULE_ID, lambda: pm)

    first = persistence.save({"name": "Week 3 design", "tags": ["biol341"]})
    assert first == "week_3_design.json"
    assert pm.store[first]["metadata"]["module"] == MODULE_ID

    state.add_design_part(CDS(id="lacI", name="LacI", sequence="ATGAAA", product="LacI"))
    second = persistence.save()  # "update", no dialog
    assert second == first
    assert len(pm.store) == 1
    saved_ids = [p["id"] for p in pm.store[first]["payload"]["synbio_state"]["data"]["parts"]]
    assert saved_ids == ["pTet", "gfp", "lacI"]
    assert pm.store[first]["metadata"]["name"] == "Week 3 design"


@pytest.mark.unit
def test_unsaved_changes_tracking():
    pm = FakeProjectManager()
    state = _state_with_design()
    persistence = WorkspacePersistence(state, MODULE_ID, lambda: pm)
    changes: list[bool] = []
    persistence.dirty_changed.connect(changes.append)

    assert not persistence.check_dirty()
    state.add_design_part(CDS(id="x", name="X", sequence="ATG", product="X"))
    assert persistence.check_dirty()
    persistence.save({"name": "tracked"})
    assert not persistence.is_dirty()
    assert changes == [True, False]


@pytest.mark.unit
def test_quiet_save_follows_the_sdk_autosave_contract():
    pm = FakeProjectManager()
    persistence = WorkspacePersistence(_state_with_design(), MODULE_ID, lambda: pm)
    results: list[bool] = []

    persistence.quiet_save(results.append)  # never named: cannot save quietly
    persistence.save({"name": "named"})
    persistence.quiet_save(results.append)
    assert results == [False, True]


@pytest.mark.unit
def test_list_workflows_shows_only_this_module():
    pm = FakeProjectManager()
    pm.save_workflow("flow_cytometry", {}, {"name": "gating", "timestamp": "2026-11-01"})
    persistence = WorkspacePersistence(_state_with_design(), MODULE_ID, lambda: pm)
    persistence.save({"name": "mine"})

    listed = persistence.list_workflows()
    assert [w["filename"] for w in listed] == ["mine.json"]


# ── Through the real panel ─────────────────────────────────────────────────


def _panel_with_project(destroy_after, pm: FakeProjectManager):
    from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel

    panel = destroy_after(SynBioPanel())
    panel._persistence._project_manager = lambda: pm
    # The demo kicks off a Tellurium run on a worker thread; these tests are
    # about persistence, not that solver.
    panel._simulate_view.plot_time_series = lambda *a, **k: None
    return panel


@pytest.mark.unit
def test_demo_saves_and_reopens_identically_in_a_fresh_panel(destroy_after):
    """The end-to-end claim: close the app, reopen the workflow, same workspace."""
    pm = FakeProjectManager()
    first = _panel_with_project(destroy_after, pm)
    first.demo_showcase_view._on_load_demo_clicked()

    filename = first.save_demo_workspace()
    assert filename == "biol341_demo_repressilator.json"
    # Re-running the tour overwrites rather than piling up copies.
    assert first.save_demo_workspace() == filename
    assert list(pm.store) == [filename]

    second = _panel_with_project(destroy_after, pm)
    rendered: dict[str, Any] = {}
    second.circuit_view.render_simulation_results = lambda result, announce=True: rendered.update(
        sim=result, announce=announce
    )
    second.crispr_view.render_grna_results = lambda c, announce=True: rendered.update(
        grnas=c, grnas_announce=announce
    )

    second.load_workflow(
        pm.load_workflow_payload(filename),
        filename=filename,
        metadata=pm.store[filename]["metadata"],
    )

    assert second.state.to_dict() == first.state.to_dict()
    kinds = {e["kind"] for e in second.state.methods_log}
    assert {"design", "assembly", "crispr_scan", "circuit_ode"} <= kinds
    # Saved results are redrawn, and a reopen does not claim a run just finished.
    assert rendered["sim"].species_concentrations
    assert rendered["announce"] is False
    assert len(rendered["grnas"]) == 2
    assert rendered["grnas_announce"] is False
    # Linked to the workflow it came from, with nothing unsaved.
    assert second._persistence.filename == filename
    assert not second._persistence.check_dirty()
    assert second._save_button.has_workflow


@pytest.mark.unit
def test_demo_save_without_a_project_reports_instead_of_failing(destroy_after):
    from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel

    panel = destroy_after(SynBioPanel())
    assert panel._project_manager() is None  # no Hub window around it
    assert panel.save_demo_workspace() is None


@pytest.mark.unit
def test_replacing_the_workspace_unlinks_it_from_its_workflow(destroy_after):
    """Load the demo over an opened workflow, press Save: the opened workflow
    must not be overwritten with demo data.
    """
    pm = FakeProjectManager()
    panel = _panel_with_project(destroy_after, pm)
    panel.state.copy_from(_state_with_design())
    panel._persistence.save({"name": "Student design"})
    student_payload = copy.deepcopy(pm.store["student_design.json"]["payload"])

    panel.demo_showcase_view._on_load_demo_clicked()  # clean, so no prompt

    assert panel._persistence.filename is None
    assert pm.store["student_design.json"]["payload"] == student_payload


@pytest.mark.unit
def test_autosave_does_not_nag_without_a_project(destroy_after):
    from karcytics_plugins.synthetic_biology.ui.main_panel import SynBioPanel

    panel = destroy_after(SynBioPanel())
    panel.state.add_design_part(CDS(id="x", name="X", sequence="ATG", product="X"))
    panel._persistence.check_dirty()

    callbacks = panel.autosave_callbacks
    assert panel._persistence.is_dirty()
    assert callbacks["has_unsaved_changes"]() is False
    assert callbacks["has_saved_once"]() is False

"""Save and reopen a Synthetic Biology workspace as a Karcytics workflow.

Persistence goes through the Hub's project, not through files the plugin picks
itself: ``window().project_manager`` is the Hub's ``ProjectManager`` when this
plugin runs in-process, and the SDK's ``RemoteProjectManager`` (which forwards
to it over ``CoreServicesServer``) when it runs isolated. Only the methods both
share are used — ``save_workflow``, ``load_workflow_payload`` and
``workflows.list_all()`` — so the same code works under either process model.

Reopening has two entry points that must agree:

* the Hub's workflow dashboard, which hands the payload to the panel through
  ``load_workflow(payload, filename=..., metadata=...)`` — directly when
  in-process, via the SDK daemon's ``inject_workflow`` RPC when isolated;
* this module's own ``open`` action.

Both end in :meth:`WorkspacePersistence.apply_payload`, which mutates the one
``SynBioState`` in place so every view and controller already holding it sees
the restored workspace.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal

WORKFLOW_SCHEMA = "karcytics.synthetic_biology.workspace"
WORKFLOW_SCHEMA_VERSION = 1


class NoProjectOpenError(RuntimeError):
    """Raised when a workflow operation needs a Hub project and none is open."""


class UnsupportedWorkflowError(ValueError):
    """Raised for a payload this version of the module cannot restore."""


def build_payload(state: Any) -> dict[str, Any]:
    """The workflow payload for ``state``.

    Keeps the ``synbio_state`` key that ``SynBioPanel.export_state`` has always
    used, so there is one serialized shape, and adds a schema tag and version
    so a future format change can be detected rather than misread.
    """
    return {
        "schema": WORKFLOW_SCHEMA,
        "version": WORKFLOW_SCHEMA_VERSION,
        "synbio_state": state.to_dict(),
    }


def extract_state_dict(payload: Any) -> dict[str, Any]:
    """Pull the serialized ``SynBioState`` out of a workflow payload.

    Accepts the current shape, the untagged ``{"synbio_state": ...}`` shape
    ``export_state`` produced before versioning, and a bare state dict
    (``{"data": ..., "view": ...}``) as a session snapshot carries it.

    Raises:
        UnsupportedWorkflowError: the payload is empty, malformed, belongs to
            another module, or was written by a newer schema version.
    """
    if not isinstance(payload, dict) or not payload:
        raise UnsupportedWorkflowError("The workflow is empty or unreadable.")

    schema = payload.get("schema")
    if schema is not None and schema != WORKFLOW_SCHEMA:
        raise UnsupportedWorkflowError(f"This workflow was saved by another module ({schema!r}).")

    version = payload.get("version", WORKFLOW_SCHEMA_VERSION)
    if isinstance(version, int) and version > WORKFLOW_SCHEMA_VERSION:
        raise UnsupportedWorkflowError(
            f"This workflow was saved by a newer version of the module (format "
            f"{version}; this version reads up to {WORKFLOW_SCHEMA_VERSION}). "
            "Update the Synthetic Biology module to open it."
        )

    state_dict = payload.get("synbio_state")
    if state_dict is None and ("data" in payload or "view" in payload):
        state_dict = payload
    if not isinstance(state_dict, dict) or not state_dict:
        raise UnsupportedWorkflowError("The workflow has no Synthetic Biology state in it.")
    return state_dict


def fingerprint(state: Any) -> str:
    """A content hash of the workspace, for unsaved-changes tracking.

    Hashing the serialized state catches every way the state can change —
    setters, direct list edits, a demo load — without each mutation site having
    to remember to flag itself.
    """
    blob = json.dumps(state.to_dict(), sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8"), usedforsecurity=False).hexdigest()


class WorkspacePersistence(QObject):
    """Tracks one workspace's link to a saved workflow and its unsaved changes."""

    dirty_changed = Signal(bool)
    saved = Signal(str)  # workflow filename
    loaded = Signal(str)  # workflow filename, or "" when opened without one

    def __init__(
        self,
        state: Any,
        module_id: str,
        project_manager: Callable[[], Any],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.state = state
        self.module_id = module_id
        self._project_manager = project_manager
        self.filename: str | None = None
        self.metadata: dict[str, Any] = {}
        self._clean_fingerprint = fingerprint(state)
        self._dirty = False

    # ── Project access ──────────────────────────────────────────────────

    def project_manager(self) -> Any:
        try:
            return self._project_manager()
        except Exception:
            return None

    def has_project(self) -> bool:
        return self.project_manager() is not None

    def _require_project(self) -> Any:
        pm = self.project_manager()
        if pm is None:
            raise NoProjectOpenError(
                "No Karcytics project is open. Open or create a project in the Hub "
                "to save workflows."
            )
        return pm

    # ── Unsaved changes ─────────────────────────────────────────────────

    def is_dirty(self) -> bool:
        return self._dirty

    def check_dirty(self) -> bool:
        """Recompute the unsaved-changes flag; emits ``dirty_changed`` on a change."""
        dirty = fingerprint(self.state) != self._clean_fingerprint
        if dirty != self._dirty:
            self._dirty = dirty
            self.dirty_changed.emit(dirty)
        return dirty

    def mark_clean(self) -> None:
        self._clean_fingerprint = fingerprint(self.state)
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)

    # ── Save ────────────────────────────────────────────────────────────

    def save(self, metadata: dict[str, Any] | None = None, filename: str | None = None) -> str:
        """Write the workspace to the open project as a workflow.

        With neither argument, overwrites the workflow this workspace was last
        saved to or opened from. Returns the workflow's filename.

        Raises:
            NoProjectOpenError: no Hub project is open.
            ValueError: no name to save under (first save needs ``metadata``).
        """
        pm = self._require_project()

        target = filename if filename is not None else self.filename
        meta = dict(self.metadata)
        if metadata:
            meta.update(metadata)
        if not meta.get("name"):
            raise ValueError("A workflow needs a name before it can be saved.")

        from datetime import datetime

        meta["timestamp"] = datetime.now().isoformat()
        result = pm.save_workflow(
            module_id=self.module_id,
            payload=build_payload(self.state),
            metadata=meta,
            filename=target,
        )
        self.filename = str(result)
        meta["module"] = self.module_id
        self.metadata = meta
        self.mark_clean()
        self.saved.emit(self.filename)
        return self.filename

    def quiet_save(self, on_done: Callable[[bool], None]) -> None:
        """The SDK autosave contract: save without dialogs, report success."""
        try:
            self.save()
        except Exception:
            on_done(False)
            return
        on_done(True)

    # ── Open ────────────────────────────────────────────────────────────

    def list_workflows(self) -> list[dict[str, Any]]:
        """This module's saved workflows in the open project, newest first."""
        pm = self._require_project()
        try:
            entries = list(pm.workflows.list_all())
        except Exception:
            return []
        mine = [e for e in entries if e.get("module") == self.module_id]
        mine.sort(key=lambda e: str(e.get("timestamp", "")), reverse=True)
        return mine

    def fetch_payload(self, filename: str) -> dict[str, Any]:
        pm = self._require_project()
        return dict(pm.load_workflow_payload(filename) or {})

    def apply_payload(
        self,
        payload: Any,
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Restore ``payload`` into the shared state, in place.

        Validates before touching anything, so a payload that cannot be read
        leaves the current workspace exactly as it was.
        """
        state_dict = extract_state_dict(payload)
        self.state.load_from_dict(state_dict)
        self.filename = filename
        self.metadata = dict(metadata or {})
        self.mark_clean()
        self.loaded.emit(filename or "")

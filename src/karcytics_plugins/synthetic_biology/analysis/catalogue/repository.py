"""Persistence for the parts catalogue, split read-only shipped vs writable user.

The catalogue used to be a single file inside the signed plugin payload, which
meant every part a student saved rewrote a file listed in ``security.json`` and
invalidated the plugin signature. Reads now come from two layers and writes go
to exactly one:

* **shipped** — ``<payload>/catalogue.json``, inside the signature. Read-only.
* **user** — ``~/.karcytics/plugin_configs/<plugin_id>/catalogue.json``. The
  only file this class ever writes.

A user part shadows a shipped part with the same ID, so editing a shipped part
is possible without touching the payload. See ``analysis/user_paths.py`` for
why that directory.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any, Protocol

from ..parts.base import BiologicalPart
from ..parts.components import part_from_dict
from ..user_paths import ensure_user_data_dir, shipped_catalogue_path, user_catalogue_path

#: Distinguishes "caller said nothing about a shipped layer" from "caller
#: explicitly asked for no shipped layer" (``shipped_path=None``).
_UNSET = object()

#: Holds IDs of shipped parts the user deleted. Without it a deletion would be
#: undone on the next launch, because the shipped layer is reloaded verbatim
#: and the user file cannot represent an absence.
TOMBSTONE_FILENAME = "deleted_parts.json"


class PartRepository(Protocol):
    """Protocol defining the interface for a parts catalogue repository.

    Adheres to the Dependency Inversion Principle (DIP) and
    Interface Segregation Principle (ISP).
    """

    def save(self, part: BiologicalPart) -> None:
        """Save or update a part."""
        ...

    def get(self, part_id: str) -> BiologicalPart | None:
        """Retrieve a part by its ID."""
        ...

    def get_all(self) -> list[BiologicalPart]:
        """Retrieve all parts in the repository."""
        ...

    def delete(self, part_id: str) -> None:
        """Delete a part by its ID."""
        ...


class JsonPartRepository:
    """A JSON-file backed implementation of PartRepository.

    Adheres to the Single Responsibility Principle (SRP) by solely
    managing serialization and persistence of parts.
    """

    def __init__(
        self,
        file_path: str | Path | None = None,
        *,
        shipped_path: str | Path | None | Any = _UNSET,
    ):
        """Open the catalogue.

        Args:
            file_path: The writable catalogue. Defaults to the per-user path.
                A relative path is resolved against the user data directory,
                never against the plugin payload — resolving it into the
                payload is the bug this split exists to fix.
            shipped_path: The read-only layer. Left unspecified it defaults to
                the shipped catalogue when ``file_path`` is also unspecified
                (the production case), and to no shipped layer when the caller
                named an exact file — a caller that points at one file means
                that file. Pass ``None`` to force a single-layer repository or
                a path to choose the layer explicitly.
        """
        if file_path is None:
            resolved_user = user_catalogue_path()
            default_shipped: Path | None = shipped_catalogue_path()
        else:
            candidate = Path(file_path).expanduser()
            resolved_user = (
                candidate if candidate.is_absolute() else user_catalogue_path().parent / candidate
            )
            default_shipped = None

        self.file_path = str(resolved_user)
        self.shipped_path = (
            default_shipped if shipped_path is _UNSET else _as_optional_path(shipped_path)
        )

        self._cache: dict[str, BiologicalPart] = {}
        #: Shipped parts re-serialized through the model, keyed by ID, so
        #: ``_save_to_disk`` can tell an untouched shipped part from one the
        #: user edited. Normalized rather than stored raw: ``to_dict`` emits
        #: fields a hand-written catalogue file may omit (``source_organism``,
        #: say), so comparing against the raw file would call every shipped
        #: part "edited" — which is how the shipped catalogue got rewritten
        #: with empty fields in the first place.
        self._shipped_dicts: dict[str, dict] = {}
        self._deleted_shipped_ids: set[str] = set()
        self._load()

    # ── Loading ────────────────────────────────────────────────────────

    @property
    def tombstone_path(self) -> Path:
        """Where deletions of shipped parts are recorded."""
        return Path(self.file_path).parent / TOMBSTONE_FILENAME

    def _read_parts_file(self, path: str | Path) -> list[dict]:
        """Return the raw part dicts in a catalogue file, or [] if unusable."""
        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return []
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def _load(self) -> None:
        """Populate the cache from shipped then user, with the user winning."""
        self._cache = {}
        self._shipped_dicts = {}
        self._deleted_shipped_ids = self._load_tombstones()

        if self.shipped_path is not None:
            for part_dict in self._read_parts_file(self.shipped_path):
                part = self._deserialize_part(part_dict)
                if part is None:
                    continue
                self._shipped_dicts[part.id] = part.to_dict()
                if part.id not in self._deleted_shipped_ids:
                    self._cache[part.id] = part

        # Loaded second, so a user part of the same ID shadows the shipped one.
        for part_dict in self._read_parts_file(self.file_path):
            part = self._deserialize_part(part_dict)
            if part is not None:
                self._cache[part.id] = part

    def _load_tombstones(self) -> set[str]:
        try:
            with open(self.tombstone_path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return set()
        return {str(item) for item in data} if isinstance(data, list) else set()

    # ── Writing ────────────────────────────────────────────────────────

    def _user_owned(self) -> list[dict]:
        """Return the parts the user file is responsible for.

        A shipped part the user never touched is left out, so a later plugin
        update to the shipped catalogue is not masked by a stale copy.
        """
        owned = []
        for part in self._cache.values():
            part_dict = part.to_dict()
            if self._shipped_dicts.get(part.id) != part_dict:
                owned.append(part_dict)
        return owned

    def _save_to_disk(self) -> None:
        """Write the user layer. Never writes inside the signed payload."""
        target = Path(self.file_path)
        if target.parent == user_catalogue_path().parent:
            ensure_user_data_dir()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "w", encoding="utf-8") as handle:
            json.dump(self._user_owned(), handle, indent=2)
            # A trailing newline keeps the file well-formed for text tooling
            # (and is what end-of-file-fixer expects of any JSON we write).
            handle.write("\n")

    def _save_tombstones(self) -> None:
        path = self.tombstone_path
        if not self._deleted_shipped_ids:
            # Nothing suppressed: remove the file rather than leave an empty one.
            with contextlib.suppress(OSError):
                os.remove(path)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(sorted(self._deleted_shipped_ids), handle, indent=2)
            handle.write("\n")

    def _deserialize_part(self, data: dict) -> BiologicalPart | None:
        return part_from_dict(data)

    # ── PartRepository ─────────────────────────────────────────────────

    def save(self, part: BiologicalPart) -> None:
        self._cache[part.id] = part
        if part.id in self._deleted_shipped_ids:
            # Re-adding a previously deleted shipped ID clears its tombstone.
            self._deleted_shipped_ids.discard(part.id)
            self._save_tombstones()
        self._save_to_disk()

    def get(self, part_id: str) -> BiologicalPart | None:
        return self._cache.get(part_id)

    def get_all(self) -> list[BiologicalPart]:
        return list(self._cache.values())

    def delete(self, part_id: str) -> None:
        if part_id not in self._cache:
            return
        del self._cache[part_id]
        if part_id in self._shipped_dicts:
            self._deleted_shipped_ids.add(part_id)
            self._save_tombstones()
        self._save_to_disk()


def _as_optional_path(value: str | Path | None) -> Path | None:
    return None if value is None else Path(value).expanduser()

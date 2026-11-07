"""Filesystem locations for data this plugin writes at runtime.

The signed plugin payload is read-only. Every file under
``src/karcytics_plugins/synthetic_biology/`` is hashed into ``security.json``,
so a single runtime write invalidates the plugin signature and the Hub may
refuse to load the plugin on the next launch. Anything the user creates
therefore has to live *outside* the payload.

Where outside
-------------
This follows the convention ``karcytics_sdk`` already uses rather than
inventing a location:

* ``PluginConfig`` stores settings in
  ``~/.karcytics/plugin_configs/<plugin_id>.json``
* academy progress is persisted under
  ``~/.karcytics/plugin_configs/<plugin_id>/academy``

so the established per-plugin *writable directory* is
``~/.karcytics/plugin_configs/<plugin_id>/``. The SDK exposes no public helper
for it — its own resolver, ``runtime_services._academy_persistence_dir``, is
private — so this module mirrors that construction, including reading
``KARCYTICS_PLUGIN_ID`` from the environment the same way the SDK does.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

import os
from pathlib import Path

#: The Hub sets this for a plugin process; the SDK's own resolver reads it too.
PLUGIN_ID_ENV = "KARCYTICS_PLUGIN_ID"

#: Overrides the whole writable directory. Exists so tests never touch the
#: developer's real home directory, and so a lab machine can point student
#: data at shared or temporary storage.
USER_DIR_ENV = "KARCYTICS_SYNBIO_USER_DIR"

#: Used when the Hub has not set PLUGIN_ID_ENV (standalone runs, tests). Must
#: match `plugin_id` in pyproject.toml's [tool.karcytics.plugin].
DEFAULT_PLUGIN_ID = "synthetic_biology"

#: Name shared by the shipped catalogue and the user's overlay file.
CATALOGUE_FILENAME = "catalogue.json"

#: Subdirectory holding part structure images, under both roots.
IMAGES_DIRNAME = "images"


def plugin_id() -> str:
    """Return this plugin's id, preferring what the Hub set for the process."""
    return os.environ.get(PLUGIN_ID_ENV) or DEFAULT_PLUGIN_ID


def user_data_dir() -> Path:
    """Return the per-user writable directory, without creating it.

    Read from the environment on every call rather than cached at import, so a
    test (or a relaunch under a different plugin id) takes effect immediately.
    """
    override = os.environ.get(USER_DIR_ENV)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".karcytics" / "plugin_configs" / plugin_id()


def ensure_user_data_dir() -> Path:
    """Create the writable directory if needed and return it."""
    path = user_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_catalogue_path() -> Path:
    """Return the user's own parts file — the only catalogue ever written to."""
    return user_data_dir() / CATALOGUE_FILENAME


def user_images_dir() -> Path:
    """Return the directory for images downloaded at runtime."""
    return user_data_dir() / IMAGES_DIRNAME


def payload_dir() -> Path:
    """Return the signed plugin payload root. Treat everything under it as read-only."""
    return Path(__file__).resolve().parents[1]


def shipped_catalogue_path() -> Path:
    """Return the read-only catalogue that ships inside the signed payload."""
    return payload_dir() / CATALOGUE_FILENAME


def shipped_images_dir() -> Path:
    """Return the read-only image directory inside the signed payload."""
    return payload_dir() / "analysis" / "catalogue" / IMAGES_DIRNAME


def resolve_part_image(relative_path: str | os.PathLike[str]) -> Path | None:
    """Resolve a part's stored ``image_path`` to a file that exists, or None.

    Images downloaded at runtime land in the user directory while a handful
    ship inside the payload, and a stored path such as ``images/QacR.jpeg``
    does not say which. The user directory is searched first so a freshly
    downloaded image wins over a stale shipped one of the same name.
    """
    name = Path(relative_path).name
    for root in (user_images_dir(), shipped_images_dir()):
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None

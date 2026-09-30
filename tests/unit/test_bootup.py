"""Unit tests verifying standard Karcytics SDK boot-up process compliance."""

import tomllib
from pathlib import Path

import pytest
from karcytics_sdk.plugin import PluginBase
from karcytics_plugins.synthetic_biology import (
    BioProPlugin,
    SyntheticBiologyPlugin,
    get_plugin,
    initialize,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
TOML_PATH = ROOT_DIR / "pyproject.toml"


def test_initialize_returns_synthetic_biology_plugin():
    """initialize() must return a SyntheticBiologyPlugin instance inheriting from PluginBase."""
    plugin = initialize()
    assert isinstance(plugin, SyntheticBiologyPlugin)
    assert isinstance(plugin, PluginBase)
    assert plugin.plugin_id == "synthetic_biology"


def test_get_plugin_delegates_to_initialize():
    """get_plugin() must return a SyntheticBiologyPlugin instance matching initialize()."""
    plugin = get_plugin()
    assert isinstance(plugin, SyntheticBiologyPlugin)
    assert plugin.plugin_id == "synthetic_biology"


def test_biopro_plugin_alias():
    """BioProPlugin must remain as an alias to SyntheticBiologyPlugin for backwards compatibility."""
    assert BioProPlugin is SyntheticBiologyPlugin


def test_plugin_panel_creation():
    """SyntheticBiologyPlugin must instantiate SynBioPanel via create_panel()."""
    plugin = SyntheticBiologyPlugin()
    panel_class = plugin.get_panel_class()
    assert panel_class.__name__ == "SynBioPanel"

    panel = plugin.create_panel()
    assert panel.__class__.__name__ == "SynBioPanel"


def test_entry_points_in_pyproject_toml():
    """pyproject.toml must configure karcytics.plugins entry point to initialize."""
    with open(TOML_PATH, "rb") as f:
        data = tomllib.load(f)

    entry_points = data.get("project", {}).get("entry-points", {})
    assert "karcytics.plugins" in entry_points, "karcytics.plugins entry point section must exist"
    assert "biopro.plugins" not in entry_points, "biopro.plugins entry point section must be removed"

    synbio_ep = entry_points["karcytics.plugins"].get("synthetic_biology")
    assert synbio_ep == "karcytics_plugins.synthetic_biology:initialize"

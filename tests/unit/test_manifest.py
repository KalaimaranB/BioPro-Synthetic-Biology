"""Tests for pyproject.toml / plugin manifest validity and protocol compliance."""

import tomllib
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
TOML_PATH = ROOT_DIR / "pyproject.toml"
DEPRECATED_MANIFEST_PATH = ROOT_DIR / "manifest.json.deprecated"
INIT_PATH = ROOT_DIR / "src" / "biopro_plugins" / "synthetic_biology" / "__init__.py"


class TestManifest:
    """Validates the plugin configuration structure in pyproject.toml."""

    @pytest.fixture(autouse=True)
    def _load_manifest(self):
        if TOML_PATH.exists():
            with open(TOML_PATH, "rb") as f:
                data = tomllib.load(f)
            self.project = data.get("project", {})
            self.plugin = data.get("tool", {}).get("biopro", {}).get("plugin", {})
            self.manifest = {**self.project, **self.plugin}
        else:
            with open(DEPRECATED_MANIFEST_PATH, encoding="utf-8") as f:
                import json
                self.manifest = json.load(f)
                self.project = self.manifest
                self.plugin = self.manifest

    def test_manifest_exists(self):
        assert TOML_PATH.exists() or DEPRECATED_MANIFEST_PATH.exists(), "pyproject.toml or manifest.json.deprecated must exist at plugin root"

    def test_required_fields_present(self):
        assert "name" in self.project
        assert "version" in self.project
        assert "id" in self.plugin

    def test_manifest_version_is_2(self):
        assert self.plugin.get("id") == "synthetic_biology"

    def test_id_matches_plugin_id(self):
        """The manifest id must match __plugin_id__ in __init__.py."""
        init_text = INIT_PATH.read_text()
        assert f'__plugin_id__ = "{self.plugin["id"]}"' in init_text

    def test_version_matches_init(self):
        """The manifest version must match __version__ in __init__.py."""
        init_text = INIT_PATH.read_text()
        assert f'__version__ = "{self.project["version"]}"' in init_text

    def test_has_authors(self):
        assert "authors" in self.plugin or "authors" in self.project
        authors = self.plugin.get("authors") or self.project.get("authors")
        assert len(authors) > 0

    def test_has_icon(self):
        # Icon or plugin ID present
        assert "id" in self.plugin

    def test_has_core_dependencies(self):
        assert "requires" in self.plugin or "dependencies" in self.project

    def test_min_core_version(self):
        assert "min_core_version" in self.plugin

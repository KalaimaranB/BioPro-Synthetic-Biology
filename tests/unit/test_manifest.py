"""Tests for manifest.json validity and protocol compliance."""

import json
from pathlib import Path

import pytest

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "manifest.json"
INIT_PATH = Path(__file__).resolve().parents[2] / "__init__.py"


class TestManifest:
    """Validates the plugin manifest structure."""

    @pytest.fixture(autouse=True)
    def _load_manifest(self):
        with open(MANIFEST_PATH) as f:
            self.manifest = json.load(f)

    def test_manifest_exists(self):
        assert MANIFEST_PATH.exists(), "manifest.json must exist at plugin root"

    def test_required_fields_present(self):
        required = ["id", "name", "version", "manifest_version"]
        for field in required:
            assert field in self.manifest, f"Missing required field: {field}"

    def test_manifest_version_is_2(self):
        assert self.manifest["manifest_version"] == 2

    def test_id_matches_plugin_id(self):
        """The manifest id must match __plugin_id__ in __init__.py."""
        init_text = INIT_PATH.read_text()
        assert f'__plugin_id__ = "{self.manifest["id"]}"' in init_text

    def test_version_matches_init(self):
        """The manifest version must match __version__ in __init__.py."""
        init_text = INIT_PATH.read_text()
        assert f'__version__ = "{self.manifest["version"]}"' in init_text

    def test_has_authors(self):
        assert "authors" in self.manifest
        assert len(self.manifest["authors"]) > 0

    def test_has_icon(self):
        assert "icon" in self.manifest
        assert len(self.manifest["icon"]) > 0

    def test_has_core_dependencies(self):
        assert "core_dependencies" in self.manifest
        assert isinstance(self.manifest["core_dependencies"], list)

    def test_min_core_version(self):
        assert "min_core_version" in self.manifest

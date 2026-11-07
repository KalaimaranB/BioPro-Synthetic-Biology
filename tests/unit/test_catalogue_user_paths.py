"""Runtime catalogue writes must never land inside the signed plugin payload.

Every file under ``src/karcytics_plugins/synthetic_biology/`` is hashed into
``security.json``. A single runtime write invalidates the plugin signature and
the Hub may refuse to load the plugin on the next launch, so for a class of 24
students each install breaks on first use. The first test here is the one that
matters: it watches the whole payload, not just ``catalogue.json``, because the
next accidental write will be to some other file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from karcytics_plugins.synthetic_biology.analysis.catalogue.repository import (
    TOMBSTONE_FILENAME,
    JsonPartRepository,
)
from karcytics_plugins.synthetic_biology.analysis.catalogue.service import PartsCatalogueService
from karcytics_plugins.synthetic_biology.analysis.parts.components import CDS, Promoter
from karcytics_plugins.synthetic_biology.analysis.user_paths import (
    USER_DIR_ENV,
    payload_dir,
    resolve_part_image,
    shipped_catalogue_path,
    user_catalogue_path,
    user_data_dir,
    user_images_dir,
)

PAYLOAD = payload_dir()


@pytest.fixture
def user_dir(tmp_path, monkeypatch):
    """Point the writable directory at a temp dir, never the real home."""
    target = tmp_path / "user_data"
    monkeypatch.setenv(USER_DIR_ENV, str(target))
    return target


def _snapshot_payload() -> dict[str, str]:
    """Hash every file in the signed payload, the way the ledger does."""
    snapshot = {}
    for path in sorted(PAYLOAD.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        snapshot[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


# ── The defect this branch exists to fix ───────────────────────────────


@pytest.mark.unit
def test_a_runtime_save_modifies_no_file_in_the_signed_payload(user_dir):
    """Saving a part must leave every hashed file byte-identical."""
    before = _snapshot_payload()

    repo = JsonPartRepository()
    repo.save(Promoter(id="student_promoter", name="Student Promoter", y_max=12.0))

    after = _snapshot_payload()

    changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    assert changed == [], f"runtime save rewrote signed files: {changed}"
    assert added == [], f"runtime save created files inside the payload: {added}"
    assert removed == [], f"runtime save deleted signed files: {removed}"


@pytest.mark.unit
def test_a_runtime_save_lands_in_the_user_directory(user_dir):
    repo = JsonPartRepository()
    repo.save(Promoter(id="student_promoter", name="Student Promoter"))

    written = user_catalogue_path()
    assert written.is_file(), "the part was not persisted anywhere"
    assert str(written).startswith(str(user_dir))
    assert not str(written).startswith(str(PAYLOAD))
    assert [p["id"] for p in json.loads(written.read_text())] == ["student_promoter"]


@pytest.mark.unit
def test_deleting_a_runtime_part_also_leaves_the_payload_untouched(user_dir):
    repo = JsonPartRepository()
    repo.save(Promoter(id="doomed", name="Doomed"))

    before = _snapshot_payload()
    repo.delete("doomed")
    assert _snapshot_payload() == before


# ── Shadowing ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_a_user_part_shadows_a_shipped_part_of_the_same_id(user_dir):
    repo = JsonPartRepository()
    shipped = [p for p in repo.get_all() if isinstance(p, Promoter)]
    assert shipped, "expected the shipped catalogue to provide promoters"
    target = shipped[0]

    repo.save(Promoter(id=target.id, name="Edited By Student", y_max=999.0))

    reloaded = JsonPartRepository()
    got = reloaded.get(target.id)
    assert got is not None
    assert got.name == "Edited By Student"
    assert got.y_max == 999.0
    # Exactly one part per ID — shadowing replaces, it does not duplicate.
    assert [p.id for p in reloaded.get_all()].count(target.id) == 1


@pytest.mark.unit
def test_shipped_parts_are_visible_without_any_user_file(user_dir):
    assert not user_catalogue_path().exists()
    repo = JsonPartRepository()
    assert len(repo.get_all()) > 1
    assert shipped_catalogue_path().is_file()


@pytest.mark.unit
def test_an_untouched_shipped_part_is_not_copied_into_the_user_file(user_dir):
    """Copies would mask a later plugin update to the shipped catalogue."""
    repo = JsonPartRepository()
    shipped_ids = {p.id for p in repo.get_all()}

    repo.save(Promoter(id="mine_only", name="Mine"))

    written = {p["id"] for p in json.loads(user_catalogue_path().read_text())}
    assert written == {"mine_only"}
    assert not (written & shipped_ids - {"mine_only"})


# ── Round trip ─────────────────────────────────────────────────────────


@pytest.mark.unit
def test_round_trip_save_reload_part_still_present(user_dir):
    repo = JsonPartRepository()
    repo.save(CDS(id="rt_cds", name="Round Trip", product="RtProtein", sequence="ATGAAA"))

    reloaded = JsonPartRepository()
    got = reloaded.get("rt_cds")
    assert got is not None
    assert isinstance(got, CDS)
    assert got.name == "Round Trip"
    assert got.product == "RtProtein"
    assert got.sequence == "ATGAAA"


@pytest.mark.unit
def test_deleting_a_shipped_part_survives_a_reload(user_dir):
    """A deletion the user cannot see persist would look like the app ignoring them."""
    repo = JsonPartRepository()
    victim = repo.get_all()[0].id

    repo.delete(victim)
    assert repo.get(victim) is None

    reloaded = JsonPartRepository()
    assert reloaded.get(victim) is None, "the shipped part came back after reload"
    assert (user_data_dir() / TOMBSTONE_FILENAME).is_file()


@pytest.mark.unit
def test_re_adding_a_deleted_shipped_part_clears_its_tombstone(user_dir):
    repo = JsonPartRepository()
    victim = repo.get_all()[0].id
    repo.delete(victim)

    repo.save(Promoter(id=victim, name="Back Again"))

    reloaded = JsonPartRepository()
    got = reloaded.get(victim)
    assert got is not None
    assert got.name == "Back Again"


# ── Explicit paths keep their old single-file meaning ──────────────────


@pytest.mark.unit
def test_an_explicit_path_means_that_file_alone(tmp_path, user_dir):
    """Callers that name a file get only that file, not the shipped layer."""
    repo = JsonPartRepository(str(tmp_path / "only.json"))
    assert repo.get_all() == []

    repo.save(Promoter(id="solo", name="Solo"))
    assert [p.id for p in JsonPartRepository(str(tmp_path / "only.json")).get_all()] == ["solo"]


@pytest.mark.unit
def test_a_relative_path_resolves_into_the_user_dir_not_the_payload(user_dir):
    """The old code anchored relative paths to the payload — that was the bug."""
    repo = JsonPartRepository("nested/custom.json")
    repo.save(Promoter(id="rel", name="Rel"))

    assert not str(Path(repo.file_path)).startswith(str(PAYLOAD))
    assert str(Path(repo.file_path)).startswith(str(user_dir))
    assert Path(repo.file_path).is_file()


# ── Images ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_enriched_images_are_written_outside_the_payload(user_dir):
    assert not str(user_images_dir()).startswith(str(PAYLOAD))


@pytest.mark.unit
def test_image_lookup_prefers_the_user_copy(user_dir):
    images = user_images_dir()
    images.mkdir(parents=True, exist_ok=True)
    (images / "QacR.jpeg").write_bytes(b"user-copy")

    resolved = resolve_part_image("images/QacR.jpeg")
    assert resolved is not None
    assert resolved.read_bytes() == b"user-copy"


@pytest.mark.unit
def test_image_lookup_falls_back_to_the_shipped_copy(user_dir):
    """The two images already in the payload must still render."""
    shipped = payload_dir() / "analysis" / "catalogue" / "images" / "QacR.jpeg"
    if not shipped.is_file():
        pytest.skip("no shipped image to fall back to")

    resolved = resolve_part_image("images/QacR.jpeg")
    assert resolved == shipped


@pytest.mark.unit
def test_image_lookup_returns_none_when_nothing_matches(user_dir):
    assert resolve_part_image("images/does_not_exist.jpeg") is None


# ── Service layer ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_service_add_and_delete_do_not_touch_the_payload(user_dir):
    service = PartsCatalogueService(JsonPartRepository())
    before = _snapshot_payload()

    service.add_part(Promoter(id="svc_part", name="Service Part"))
    service.delete_part("svc_part")

    assert _snapshot_payload() == before


@pytest.mark.unit
def test_initialize_cello_parts_writes_nothing_when_shipped_parts_exist(user_dir):
    """The shipped catalogue is already populated, so seeding must be a no-op."""
    service = PartsCatalogueService(JsonPartRepository())
    before = _snapshot_payload()

    service.initialize_cello_parts()

    assert _snapshot_payload() == before
    assert not user_catalogue_path().exists(), "seeding wrote a redundant user file"


# ── Hermetic seeding ───────────────────────────────────────────────────


@pytest.mark.unit
def test_seeding_makes_no_network_calls_by_default(tmp_path, monkeypatch):
    """The unit suite must pass offline.

    Seeding used to call UniProt and RCSB PDB for every CDS, two blocking
    requests each, and downloaded ~150 KB of JPEGs during a test run.
    """
    import urllib.request

    def explode(*args, **kwargs):
        raise AssertionError("seeding attempted a network call")

    monkeypatch.setattr(urllib.request, "urlopen", explode)

    service = PartsCatalogueService(JsonPartRepository(str(tmp_path / "seed.json")))
    service.initialize_cello_parts()

    assert service.get_all_parts(), "seeding should still populate the catalogue"


@pytest.mark.unit
def test_enrichment_is_opt_in_and_off_by_default(tmp_path):
    assert PartsCatalogueService(JsonPartRepository())._enrich_from_network is False
    opted_in = PartsCatalogueService(JsonPartRepository(), enrich_from_network=True)
    assert opted_in._enrich_from_network is True


@pytest.mark.unit
def test_seeding_downloads_no_images_into_the_user_dir(user_dir, tmp_path):
    """The images that used to appear under ~/.karcytics came from seeding."""
    service = PartsCatalogueService(JsonPartRepository(str(tmp_path / "seed.json")))
    service.initialize_cello_parts()

    assert not user_images_dir().exists() or not list(user_images_dir().iterdir())

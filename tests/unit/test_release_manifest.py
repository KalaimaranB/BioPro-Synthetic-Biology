"""What the release zip ships, and what the back-merge workflow does on refusal.

Two CI defects are pinned here.

The release zip shipped CLAUDE.md, CONTRIBUTING.md, note.md,
DEMO_PRESENTATION.md and two feature design notes to everyone who installed
v0.2.0. The packaging list lives in ``.github/workflows/release.yml`` as
``EXCLUDE_PATTERNS``; ``custom_exclusions`` in ``pyproject.toml`` is a separate
knob that governs the signed ledger, not the payload. The two can desync in a
way that bricks installation, because the host's integrity check fails with
"Missing File" for any ``security.json`` entry the zip does not carry. That
agreement is the test worth having, and it is checked here rather than trusted.

The back-merge workflow reported an API refusal as "no changes needed" and
exited 0. Its runtime behaviour cannot be tested from pytest: it needs a real
``gh`` against a real repository with a real token being refused, which means
running GitHub Actions. What IS tested is the workflow source -- that no exit
path goes green off a bare ``gh`` failure, and that each green skip is backed by
its own query. That is a static check, and it guards against the pattern being
reinstated rather than proving the live behaviour.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
BACK_MERGE_WORKFLOW = ROOT / ".github" / "workflows" / "back-merge.yml"

#: Written by the signing steps that run before `zip`, so they exist in the
#: release job's tree but not in `git ls-files`.
SIGNING_ARTIFACTS = (
    "security.json",
    "signature.bin",
    "trust_chain.json",
    "project_signature.bin",
)

#: Contributor documents. Each is about building this plugin, not using it.
INTERNAL_DOCUMENTS = (
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "DEMO_PRESENTATION.md",
    "note.md",
    "feature_literature_importer.md",
    "feature_theoretical_predictor.md",
    "SynBio Gate Construction Plan.md",
)

#: Must survive: the host reads the ledger and both signatures at install time.
SIGNED_PAYLOAD = ("security.json", "signature.bin", "trust_chain.json")


def _exclude_patterns() -> list[str]:
    """The EXCLUDE_PATTERNS array as release.yml actually declares it.

    Read out of the workflow rather than duplicated, so this file cannot
    quietly agree with a copy of the list while the real one drifts.
    """
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    block = re.search(r"EXCLUDE_PATTERNS=\((.*?)\n\s*\)\n", text, re.DOTALL)
    assert block, "release.yml no longer declares an EXCLUDE_PATTERNS array"
    return re.findall(r'^\s*"([^"]+)"\s*$', block.group(1), re.MULTILINE)


def _tracked_files() -> list[str]:
    out = subprocess.run(  # noqa: S603
        ["git", "-C", str(ROOT), "ls-files"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def _is_excluded(rel_path: str, patterns: list[str]) -> bool:
    """Apply one `zip --exclude` pattern set the way zip does.

    zip matches its patterns against the whole archive-relative name and lets
    ``*`` cross directory separators, which is exactly fnmatch's behaviour.
    """
    return any(fnmatch.fnmatch(rel_path, pattern) for pattern in patterns)


@pytest.fixture(scope="module")
def shipped() -> frozenset[str]:
    """The paths the release zip would contain, for this commit's tree."""
    patterns = _exclude_patterns()
    candidates = [*_tracked_files(), *SIGNING_ARTIFACTS]
    return frozenset(p for p in candidates if not _is_excluded(p, patterns))


@pytest.fixture(scope="module")
def signed_paths() -> frozenset[str]:
    ledger = json.loads((ROOT / "security.json").read_text(encoding="utf-8"))
    return frozenset(ledger["hashes"])


# ── Defect 2: internal documents shipped to end users ──────────────────


@pytest.mark.unit
@pytest.mark.parametrize("document", INTERNAL_DOCUMENTS)
def test_an_internal_document_does_not_ship(document, shipped):
    assert (ROOT / document).exists(), (
        f"{document} is no longer in the repo; drop it from INTERNAL_DOCUMENTS "
        "rather than leaving a test that asserts nothing"
    )
    assert document not in shipped


@pytest.mark.unit
def test_developer_tool_config_does_not_ship(shipped):
    for config in (".coderabbit.yaml", ".pre-commit-config.yaml", "ruff.toml"):
        assert config not in shipped


@pytest.mark.unit
def test_the_stray_r_history_does_not_ship(shipped):
    assert "docs/.Rhistory" not in shipped


@pytest.mark.unit
def test_the_signed_payload_still_ships(shipped):
    for artifact in SIGNED_PAYLOAD:
        assert artifact in shipped, f"the host cannot verify an install without {artifact}"


@pytest.mark.unit
def test_the_plugin_itself_still_ships(shipped):
    """The exclusions are a list of names; a wrong one could take src/ with it."""
    assert "pyproject.toml" in shipped, "the manifest is how the host identifies the plugin"
    assert "src/karcytics_plugins/synthetic_biology/__init__.py" in shipped
    assert "catalogue.json" in shipped, "the shipped read-only part catalogue"
    assert "README.md" in shipped and "LICENSE" in shipped
    source_files = [p for p in shipped if p.startswith("src/") and p.endswith(".py")]
    assert len(source_files) > 50, f"only {len(source_files)} source files would ship"


@pytest.mark.unit
def test_no_test_file_ships(shipped):
    assert not [p for p in shipped if p.startswith("tests/")]


# ── The ledger and the payload must agree ──────────────────────────────


@pytest.mark.unit
def test_every_signed_file_is_in_the_release_zip(shipped, signed_paths):
    """The desync that bricks an install.

    ``_check_integrity`` walks the installed tree and then fails the whole
    verification with "Missing File" for any ``security.json`` entry it did not
    find. So excluding a hashed file from the zip without also adding it to
    ``custom_exclusions`` does not ship a smaller plugin -- it ships one that
    refuses to load.
    """
    missing = sorted(signed_paths - shipped)
    assert not missing, (
        "security.json lists files the release zip would not contain, so the "
        f"host would reject the install with 'Missing File': {missing}. Add "
        "them to custom_exclusions in pyproject.toml, or stop excluding them "
        "from the zip."
    )


@pytest.mark.unit
def test_custom_exclusions_holds_only_entries_that_do_something(signed_paths):
    """A no-op entry reads like protection it is not providing.

    The SDK hashes only MANDATORY_EXTENSIONS -- ``.py .pyw .json .yml .yaml
    .fcs .png .jpg`` -- so ``.md`` and ``.pdf`` are never in the ledger and
    naming one here changes nothing. The brief that produced this change asked
    for the contributor documents to be added to ``custom_exclusions``; they
    are deliberately not, because it would have been a silent no-op.
    """
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    exclusions = manifest["tool"]["karcytics"]["plugin"]["custom_exclusions"]

    hashable = {".py", ".pyw", ".json", ".yml", ".yaml", ".fcs", ".png", ".jpg"}
    for entry in exclusions:
        suffix = Path(entry).suffix
        if not suffix:
            continue  # a directory name, e.g. "tests"
        assert suffix in hashable, (
            f"{entry!r} in custom_exclusions has no effect: the signer never "
            f"hashes {suffix} files, so excluding it protects nothing. Exclude "
            "it from the release zip instead."
        )


@pytest.mark.unit
def test_an_excluded_hashed_file_is_also_out_of_the_ledger(signed_paths):
    """The same agreement from the other side, named explicitly.

    Both .yaml files are hashable and are excluded from the zip, so both must
    be in custom_exclusions. This fails if someone removes one from the list
    while leaving the zip exclusion in place.
    """
    for config in (".coderabbit.yaml", ".pre-commit-config.yaml"):
        assert config not in signed_paths


# ── Defect 1: a refusal must not be reported as a no-op ────────────────


@pytest.mark.unit
def test_the_back_merge_fallback_is_not_a_bare_skip():
    """The exact string that went green having opened nothing."""
    text = BACK_MERGE_WORKFLOW.read_text(encoding="utf-8")

    assert "PR already exists or no changes needed, skipping" not in text, (
        "this message was printed for an API refusal and the job exited 0"
    )


@pytest.mark.unit
def test_the_back_merge_failure_path_can_fail_the_job():
    text = BACK_MERGE_WORKFLOW.read_text(encoding="utf-8")

    assert "exit 1" in text, "no path out of this workflow fails"
    assert "::error::" in text, "a failure must annotate the run, not only exit nonzero"


@pytest.mark.unit
def test_each_green_skip_is_backed_by_its_own_query():
    """A no-op is established, never inferred from the create failing."""
    text = BACK_MERGE_WORKFLOW.read_text(encoding="utf-8")

    assert "gh pr list" in text, "an 'already open' skip must confirm the PR is open"
    assert "rev-list" in text, "a 'nothing to carry' skip must confirm develop is current"


@pytest.mark.unit
def test_the_refusal_message_names_both_remedies():
    """The API says the token was refused; it does not say which fix to apply."""
    text = BACK_MERGE_WORKFLOW.read_text(encoding="utf-8")

    assert "create and approve pull requests" in text, "the repo-settings remedy"
    assert "BOT_TOKEN" in text, "the PAT remedy"


@pytest.mark.unit
def test_the_workflow_still_prefers_a_pat_when_one_exists():
    """The token line is a repo-settings decision, not a code change."""
    text = BACK_MERGE_WORKFLOW.read_text(encoding="utf-8")

    assert "secrets.BOT_TOKEN || github.token" in text

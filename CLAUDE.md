# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`synthetic-biology-module` — a Karcytics plugin for designing, validating, and simulating biological logic gates and synthetic genetic circuits. Unlike the other plugin repos in this ecosystem, it runs **in-process** (`process_model = "in_process"` in `pyproject.toml`'s `[tool.karcytics.plugin]`) rather than isolated — it still only depends on `karcytics_sdk` (sibling `Karcytics-SDK` repo, editable local path via `[tool.uv.sources]`) and should not import `karcytics.*` from the Hub even though it happens to share a process with it. Entry point: `karcytics_plugins.synthetic_biology:initialize`. It also exposes an isolated-process UI daemon entry (`ui_daemon.py`) even though the default process model is in-process.

> The README's clone URL and CI badge still say `BioPro-SyntheticBiology` — a naming holdover from before the project's rename to Karcytics; the actual directory/remote is `Karcytics-SyntheticBiology`.

See `../Karcytics/ECOSYSTEM.md` for the full map of all 7 Karcytics repos and their relationships.

## Commands

```bash
uv run pytest tests/unit/ --tb=short -q   # what pre-commit runs (only unit/ dir exists currently)
uv run ruff check src/ tests/ --fix
uv run ruff format src/ tests/
uv run mypy --explicit-package-bases src/
```

Pre-commit runs ruff, mypy, pip-audit, license compliance, `tests/unit/`, plugin re-signing, and security-ledger verification. Don't pre-run the full suite before committing.

## Structure

`src/karcytics_plugins/synthetic_biology/`:
- `analysis/` — `state.py` (`SynBioState`: circuit + view layers), `config.py` (simulation/workspace config), `events.py` (`CentralEventBus` topic constants). No PyQt6 imports.
- `models/` — circuit/gate domain models.
- `ui/` — PyQt6 interface.
- `utils/` — shared helpers.

Same `PluginBase`/`AnalysisBase` split as the other Karcytics plugins — see [Karcytics-SDK](../Karcytics-SDK)'s `CLAUDE.md` for the pattern.

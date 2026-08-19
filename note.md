# ⚠️ Core Dependency Installation Reminder — likely obsolete, needs confirmation

> This file predates the plugin's move to `process_model = "isolated"`
> (see `pyproject.toml`'s `[tool.karcytics.plugin]` and `ui_daemon.py`): an
> isolated plugin runs in its own subprocess with its own `.venv`/interpreter
> and never imports into the Hub's process, so its dependencies should no
> longer need installing into Karcytics core's own environment at all — that
> requirement only applied under the old in-process execution model. Confirm
> against Karcytics core's current plugin-loading code before assuming any of
> the steps below are still needed; if isolated plugins now fully manage their
> own dependencies, this file can likely be deleted.

## Dependencies (if still needed by Karcytics core)

This plugin's actual dependencies, per `pyproject.toml`:

| Package | Purpose |
|---------|---------|
| `karcytics-sdk` | Plugin base classes, UI kit, signing/trust |
| `PyQt6` | UI framework |
| `numpy`, `scipy`, `pandas`, `matplotlib` | Numerical computation, ODE solving, plotting |
| `networkx` | Circuit graph representation & orthogonality checking |
| `sbol3` | SBOL3 standard biological parts data format |
| `biopython` | Sequence/codon utilities |
| `pyqtgraph` | Additional plotting widgets |
| `tellurium` | Systems biology simulation engine (Antimony/SBML) |
| `requests` | HTTP client |

(Note: `mesa`, previously listed here for agent-based modeling, is not currently
a declared dependency — either it was removed, or that integration never shipped.)

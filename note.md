# ⚠️ Core Dependency Installation Reminder

## Dependencies to install into BioPro Core

The Synthetic Biology plugin declares the following `core_dependencies` in its `manifest.json`.
These must also be installed into the **BioPro core** application's environment so they are
available at runtime when the plugin is loaded.

### Required packages:

| Package | Purpose | Install Command |
|---------|---------|-----------------|
| `numpy` | Numerical computation | Already in core ✅ |
| `scipy` | ODE solver for kinetic simulation | Already in core ✅ |
| `pandas` | Data handling | Already in core ✅ |
| `matplotlib` | Plotting & visualization | Already in core ✅ |
| `networkx` | Circuit graph representation & orthogonality checking | `uv pip install networkx` |
| `sbol3` | SBOL3 standard biological parts data format | `uv pip install sbol3` |
| `tellurium` | Systems biology simulation engine (Antimony/SBML) | `uv pip install tellurium` |
| `mesa` | Agent-based modeling for intercellular communication | `uv pip install mesa` |

### Steps:

1. Open the **BioPro** core project:
   ```bash
   cd ~/GitHub\ Projects/BioPro
   source .venv/bin/activate
   ```

2. Install the new dependencies:
   ```bash
   uv pip install networkx sbol3 tellurium mesa
   ```

3. Add them to BioPro's `requirements.in`:
   ```
   networkx>=3.1
   sbol3>=1.1
   tellurium>=2.2
   mesa>=2.0
   ```

4. Recompile the lock file:
   ```bash
   uv pip compile requirements.in -o requirements.txt
   ```

5. If using PyInstaller, add them to `BioPro.spec` hidden imports:
   ```python
   hiddenimports += ["networkx", "sbol3", "tellurium", "mesa"]
   ```

### Also update BioPro-Distribution

When registering the plugin in `registry.json`, ensure the `core_dependencies`
array matches so the auto-updater can pre-install them before loading the plugin.

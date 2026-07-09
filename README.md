# 🧬 BioPro — Synthetic Biology Module

A BioPro plugin for designing, validating, and simulating biological logic gates and synthetic genetic circuits.

## Quick Start

```bash
# Clone the repo
git clone https://github.com/KalaimaranB/BioPro-SyntheticBiology.git
cd BioPro-SyntheticBiology

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies (including dev tools)
uv pip install -e ".[dev]"

# Install BioPro SDK
uv pip install git+https://github.com/KalaimaranB/BioPro-SDK.git

# Run tests
pytest tests/unit/ -v

# Lint
ruff check analysis/ ui/ tests/
```

## Project Structure

```
BioPro-SyntheticBiology/
├── __init__.py              # BioProPlugin entry point
├── manifest.json            # Plugin manifest (id, version, deps)
├── pyproject.toml           # Python project config
├── analysis/                # Domain model & computation
│   ├── state.py             # SynBioState (circuit + view layers)
│   ├── config.py            # Simulation & workspace config
│   └── events.py            # CentralEventBus topic constants
├── ui/                      # PyQt6 user interface
│   ├── main_panel.py        # SynBioPanel (root widget)
│   └── composition_root.py  # ServiceFactory (DI container)
├── tests/                   # Test suite
│   ├── conftest.py          # SDK mocking infrastructure
│   └── unit/                # Unit tests
├── docs/                    # MkDocs documentation
├── .github/workflows/       # CI/CD pipelines
│   ├── ci.yml               # Tests & lint
│   └── release.yml          # Auto-release & signing
├── security.json            # File integrity hashes (generated)
├── signature.bin            # Cryptographic signature (generated)
├── dev_cert.bin             # Developer certificate (generated)
├── delegation.json          # CI pipeline delegation
└── trust_chain.json         # Trust chain certificates
```

## Security

This plugin follows BioPro's cryptographic trust model:

1. All source files are SHA-256 hashed into `security.json`
2. The manifest is signed with an Ed25519 key → `signature.bin`
3. The developer certificate is stored in `dev_cert.bin`
4. BioPro core verifies all three before loading the plugin

To sign locally:
```bash
biopro-sdk sign .
```

## Documentation

```bash
# Serve docs locally
uv pip install mkdocs-material
mkdocs serve
```

## License

Part of the BioPro ecosystem. See the main BioPro repository for license details.

# 🧬 Karcytics Synthetic Biology

Welcome to the **Synthetic Biology Workspace** documentation — a Karcytics plugin for designing, validating, and simulating biological logic gates and synthetic genetic circuits.

## Overview

This module bridges the gap between computer science and biology by providing tools to:

- **Design** biological logic gates (AND, OR, NOT) from standardized genetic parts
- **Validate** circuit orthogonality to prevent signal crosstalk
- **Simulate** circuit kinetics using ODE-based models with real biochemical parameters
- **Visualize** protein concentrations over time with oscilloscope-style graphs

## Architecture

The plugin follows Karcytics's standard plugin architecture, running as an isolated
process (`process_model = "isolated"`) with its own PyQt6 UI daemon:

| Layer | Directory | Purpose |
|-------|-----------|---------|
| **Analysis** | `src/karcytics_plugins/synthetic_biology/analysis/` | Domain model, state, circuit engine, simulation (no PyQt6 imports) |
| **UI** | `src/karcytics_plugins/synthetic_biology/ui/` | PyQt6 widgets, panels, canvas |
| **Tests** | `tests/` | Unit tests |

## Getting Started

See the main [README](https://github.com/KalaimaranB/BioPro-SyntheticBiology) for setup instructions.

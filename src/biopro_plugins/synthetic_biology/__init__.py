"""Synthetic Biology Workspace — BioPro plugin entry point.

A scientist-centric environment for designing, validating, and simulating
biological logic gates and synthetic genetic circuits.
"""

__version__ = "0.1.0"
__plugin_id__ = "synthetic_biology"

import os
import sys

# Ensure the plugin's root directory is in sys.path so absolute imports like 'from analysis import ...' work
plugin_dir = os.path.dirname(os.path.abspath(__file__))
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)


def initialize(context=None):
    """V3 Architecture Entry Point."""

    class SyntheticBiologyPlugin:
        def __init__(self, ctx=None):
            self.context = ctx

        def get_panel_class(self):
            from .ui.main_panel import SynBioPanel

            return SynBioPanel

    return SyntheticBiologyPlugin(context)


def get_panel_class():
    """Returns the main QWidget class that should be injected into the UI.

    Standard BioPro entry point.  The core ``ModuleManager`` calls this
    function to obtain the class (not an instance) and then instantiates it
    into the central workspace container.
    """
    from .ui.main_panel import SynBioPanel

    return SynBioPanel


def cleanup():
    """Module-level cleanup."""
    pass


def shutdown():
    """Module-level shutdown."""
    pass

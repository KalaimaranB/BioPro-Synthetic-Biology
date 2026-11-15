"""The unit the simulators report in, and the axis labels derived from it.

Why this module exists
----------------------
The circuit simulator's output unit is a property of the *model*, not of
whichever widget happens to draw it. Before this module the string
``"Protein concentration (RPU)"`` was written out by hand in three views and
``"Output Expression (RPU)"`` in a fourth, so a change to what the engine
actually returns could not reach the axis that claimed to describe it. It did
not reach it: the engine integrated

    d[P]/dt = y_min + (y_max - y_min) * Prod Hill(R) - gamma * [P]

whose steady state is ``production / gamma``. ``y_min`` and ``y_max`` come from
the Cello UCF and are *relative promoter units* -- a dimensionless
steady-state output level, not a synthesis rate -- so dividing RPU by a rate in
min^-1 yields RPU x min. Four axes called that RPU, and the repressilator
preset peaked at 24.5 on an axis whose promoters cap at 10.

The engine now scales production by ``gamma``, so ``[P]* = y`` and the unit is
genuinely RPU. Keeping the unit here, beside the quantity names, is what makes
the next such change land on the axis as well as in the solver.

``SimulationResult.unit`` carries this value out with each result, so a view
labels an axis from the result it was handed rather than from a constant it
hopes still applies.

No Qt imports: ``analysis/`` stays free of PySide6.
"""

from __future__ import annotations

#: Relative promoter units. The Cello UCF's ``signal_carrier_units``, and the
#: unit of ``CircuitComponent.y_min``/``y_max``, hence of the deterministic
#: trace now that production is scaled by the degradation rate.
OUTPUT_UNIT = "RPU"

#: What the deterministic circuit simulators report: a protein level.
PROTEIN_QUANTITY = "Protein concentration"

#: What a steady-state transfer curve reports: the promoter's own output.
PROMOTER_OUTPUT_QUANTITY = "Output Expression"

#: The Gillespie path reports molecules, not RPU, so it is deliberately not
#: expressed in ``OUTPUT_UNIT`` and carries no unit suffix.
MOLECULE_COUNT_LABEL = "Molecule count"


def axis_label(quantity: str, unit: str = OUTPUT_UNIT) -> str:
    """Render an axis label as ``quantity (unit)``.

    Args:
        quantity: What is plotted, e.g. ``PROTEIN_QUANTITY``.
        unit: The unit it is plotted in. Defaults to :data:`OUTPUT_UNIT`.

    Returns:
        The label, or just the quantity when ``unit`` is empty -- a trace with
        no meaningful unit must not be given a parenthesised empty one.
    """
    return f"{quantity} ({unit})" if unit else quantity


#: The deterministic time-series axis. Derived, not spelled out again.
PROTEIN_AXIS_LABEL = axis_label(PROTEIN_QUANTITY)

#: The steady-state transfer-curve axis.
PROMOTER_OUTPUT_AXIS_LABEL = axis_label(PROMOTER_OUTPUT_QUANTITY)


__all__ = [
    "MOLECULE_COUNT_LABEL",
    "OUTPUT_UNIT",
    "PROMOTER_OUTPUT_AXIS_LABEL",
    "PROMOTER_OUTPUT_QUANTITY",
    "PROTEIN_AXIS_LABEL",
    "PROTEIN_QUANTITY",
    "axis_label",
]

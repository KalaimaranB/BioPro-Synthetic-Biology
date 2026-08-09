"""Event topic constants for the Synthetic Biology CentralEventBus.

These string constants define the pub/sub channels used for decoupled
communication between the analysis engine, the UI layer, and other
BioPro plugins.
"""

# ── Circuit Lifecycle ─────────────────────────────────────────────────
CIRCUIT_CHANGED = "synbio.circuit.changed"
PART_ADDED = "synbio.circuit.part_added"
PART_REMOVED = "synbio.circuit.part_removed"
CONNECTION_ADDED = "synbio.circuit.connection_added"
CONNECTION_REMOVED = "synbio.circuit.connection_removed"

# ── Simulation ────────────────────────────────────────────────────────
SIMULATION_STARTED = "synbio.simulation.started"
SIMULATION_PROGRESS = "synbio.simulation.progress"
SIMULATION_COMPLETED = "synbio.simulation.completed"
SIMULATION_FAILED = "synbio.simulation.failed"

# ── Validation ────────────────────────────────────────────────────────
ORTHOGONALITY_CHECK_STARTED = "synbio.validation.orthogonality_started"
ORTHOGONALITY_CHECK_COMPLETED = "synbio.validation.orthogonality_completed"
CROSSTALK_ERROR = "synbio.validation.crosstalk_error"

# ── Part Library ──────────────────────────────────────────────────────
LIBRARY_LOADED = "synbio.library.loaded"
LIBRARY_SEARCH_COMPLETED = "synbio.library.search_completed"

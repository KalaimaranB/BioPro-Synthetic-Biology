"""Shared Hill-kinetics parameter resolution for the circuit simulators.

Two code paths simulate the same circuit: the SciPy engine
(``circuit_engine.CircuitSimulationEngine``) integrates the ODE system
directly, while the Simulate tab compiles an Antimony model string for
Tellurium. Both need identical regulation terms, or the same design plots
differently in different tabs — so the fallback rules live here, once.
"""

from __future__ import annotations

import dataclasses

from ..models.domain import CircuitComponent, CircuitEdge

# Floor for K_d: the Hill terms divide by it.
MIN_K_D = 1e-6


def _component_default(field_name: str, fallback: float) -> float:
    """Read a default straight off ``CircuitComponent``.

    Mirroring the numbers by hand is how the two simulators drifted apart in
    the first place, so they are derived instead of copied.
    """
    for f in dataclasses.fields(CircuitComponent):
        if f.name == field_name and f.default is not dataclasses.MISSING:
            return float(f.default)  # type: ignore[arg-type]
    return fallback


DEFAULT_K_D = _component_default("K_d", 1.0)
DEFAULT_N = _component_default("n", 2.0)
DEFAULT_Y_MIN = _component_default("y_min", 0.001)
DEFAULT_Y_MAX = _component_default("y_max", 5.0)
DEFAULT_DEGRADATION_RATE = _component_default("degradation_rate", 0.1)


def resolve_edge_params(
    edge: CircuitEdge,
    target: CircuitComponent | None,
) -> tuple[float, float]:
    """Resolve the binding affinity (K_d) and Hill coefficient (n) for one edge.

    Operator-specific values on the edge win. When the edge leaves them unset
    — which is the dataclass default, so it is the common case — they fall back
    to the **target** node, the gene being regulated, matching the documented
    behaviour of ``CircuitSimulationEngine.simulate_circuit``.

    Args:
        edge: The regulatory connection.
        target: The component the edge points at, or ``None`` if unresolved.

    Returns:
        ``(K_d, n)``, with K_d floored at ``MIN_K_D``.
    """
    k_d = edge.K_d
    if k_d is None:
        k_d = getattr(target, "K_d", None)
    if k_d is None:
        k_d = DEFAULT_K_D

    n = edge.n
    if n is None:
        n = getattr(target, "n", None)
    if n is None:
        n = DEFAULT_N

    return max(MIN_K_D, float(k_d)), float(n)


def regulation_factor(
    interaction_type: str,
    source_concentration: float,
    k_d: float,
    n: float,
) -> float | None:
    """Evaluate one regulatory Hill term numerically.

    Returns ``None`` for an interaction type that is neither repression nor
    activation, so callers can skip it rather than silently treating it as 1.0.
    """
    itype = (interaction_type or "").lower()
    ratio = (source_concentration / max(MIN_K_D, k_d)) ** n

    if itype == "repression":
        return 1.0 / (1.0 + ratio)
    if itype == "activation":
        return ratio / (1.0 + ratio)
    return None


def regulation_expression(
    interaction_type: str,
    source_var: str,
    k_d: float,
    n: float,
) -> str | None:
    """Render one regulatory Hill term as an Antimony expression.

    The algebraic twin of ``regulation_factor``: same rule, same parameters,
    emitted as text for Tellurium instead of evaluated.
    """
    itype = (interaction_type or "").lower()
    ratio = f"({source_var} / {k_d})^{n}"

    if itype == "repression":
        return f"(1 / (1 + {ratio}))"
    if itype == "activation":
        return f"({ratio} / (1 + {ratio}))"
    return None

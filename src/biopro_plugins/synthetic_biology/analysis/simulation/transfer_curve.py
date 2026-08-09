"""Steady-state transfer curve calculation for synthetic promoters.

Implements the standard repressive Hill equation to model promoter output activity
as a function of input repressor concentration.
"""

from typing import Dict, Any
import numpy as np


def calculate_steady_state_curve(
    K_d: float,
    y_max: float,
    y_min: float = 0.0,
    n: float = 2.0,
    r_min: float = 0.001,
    r_max: float = 100.0,
    num_points: int = 500,
) -> Dict[str, Any]:
    """Calculate the steady-state transfer curve for a repressor-regulated promoter.

    Mathematical Model (Repressive Hill Equation):
        y = y_min + (y_max - y_min) / (1 + (R / K_d)^n)

    Args:
        K_d: Dissociation constant / repression threshold (concentration units/RPU).
        y_max: Maximum promoter output expression (fully ON state).
        y_min: Minimum promoter output expression (basal leakiness / OFF state).
        n: Hill coefficient (cooperativity / gate steepness).
        r_min: Minimum repressor concentration for evaluation.
        r_max: Maximum repressor concentration for evaluation.
        num_points: Number of evaluation points along the concentration axis.

    Returns:
        Dict containing:
            - "R": np.ndarray of input repressor concentrations.
            - "y": np.ndarray of output promoter activity.
            - "K_d": Dissociation constant.
            - "y_max": Maximum expression.
            - "y_min": Minimum expression.
            - "n": Hill coefficient.
            - "y_half": Output expression at R = K_d.
    """
    # Sanitize parameters
    safe_kd = max(1e-6, float(K_d))
    safe_ymax = float(y_max)
    safe_ymin = max(0.0, float(y_min))
    safe_n = max(0.1, float(n))

    # Span repressor concentration across K_d if r_max is lower than 10 * K_d
    upper_bound = max(float(r_max), safe_kd * 100.0)
    lower_bound = max(1e-4, min(float(r_min), safe_kd / 1000.0))

    # Logarithmic concentration axis
    R = np.logspace(np.log10(lower_bound), np.log10(upper_bound), num_points)

    # Repressive Hill equation calculation
    y = safe_ymin + (safe_ymax - safe_ymin) / (1.0 + (R / safe_kd) ** safe_n)

    y_half = safe_ymin + (safe_ymax - safe_ymin) / 2.0

    return {
        "R": R,
        "y": y,
        "K_d": safe_kd,
        "y_max": safe_ymax,
        "y_min": safe_ymin,
        "n": safe_n,
        "y_half": y_half,
    }

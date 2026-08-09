"""Unit tests for steady-state transfer curve calculation."""

import numpy as np
from analysis.simulation.transfer_curve import calculate_steady_state_curve


def test_steady_state_boundary_values():
    """Test boundary conditions for repressive Hill function:
    y = y_min + (y_max - y_min) / (1 + (R / K_d)^n)
    """
    K_d = 40.0
    y_max = 250.0
    y_min = 0.5
    n = 2.0

    res = calculate_steady_state_curve(
        K_d=K_d, y_max=y_max, y_min=y_min, n=n, r_min=1e-4, r_max=1e4
    )

    R = res["R"]
    y = res["y"]

    # At R -> 0 (min concentration index 0), y should approach y_max
    assert np.isclose(y[0], y_max, rtol=1e-2)

    # At R -> infinity (max concentration index -1), y should approach y_min
    assert np.isclose(y[-1], y_min, rtol=1e-2)

    # At R == K_d, y should equal y_half = y_min + (y_max - y_min) / 2
    expected_half = y_min + (y_max - y_min) / 2.0
    idx_kd = np.argmin(np.abs(np.log(R) - np.log(K_d)))
    assert np.isclose(y[idx_kd], expected_half, rtol=3e-2)


def test_steady_state_monotonicity():
    """Test that a repressive promoter output decreases monotonically with increasing repressor."""
    res = calculate_steady_state_curve(K_d=0.07, y_max=3.8, y_min=0.06, n=1.6)
    y = res["y"]

    # Diff should be strictly negative (monotonically decreasing)
    diffs = np.diff(y)
    assert np.all(diffs <= 0)


def test_hill_coefficient_effect():
    """Test that higher Hill coefficient n creates a steeper transition curve around K_d."""
    res_n1 = calculate_steady_state_curve(K_d=1.0, y_max=10.0, y_min=0.0, n=1.0)
    res_n4 = calculate_steady_state_curve(K_d=1.0, y_max=10.0, y_min=0.0, n=4.0)

    # At R = 2 * K_d (double K_d):
    # n=1: y = 10 / (1 + 2) = 3.333
    # n=4: y = 10 / (1 + 2^4) = 10 / 17 = 0.588
    # So higher n represses much more sharply past K_d
    idx1 = np.argmin(np.abs(res_n1["R"] - 2.0))
    idx4 = np.argmin(np.abs(res_n4["R"] - 2.0))

    assert res_n4["y"][idx4] < res_n1["y"][idx1]

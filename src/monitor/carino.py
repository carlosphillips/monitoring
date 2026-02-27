"""Carino-linked contribution computation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from monitor import DataError

EPSILON = 1e-12


@dataclass
class Contributions:
    """Carino-linked contributions for a single window."""

    # Linked contribution per (layer, factor) pair
    layer_factor: dict[tuple[str, str], float]
    # Linked residual contribution
    residual: float
    # Geometric total portfolio return for the window
    total_return: float


def compute(
    portfolio_returns: np.ndarray,
    exposures: dict[tuple[str, str], np.ndarray],
    factor_returns: dict[str, np.ndarray],
) -> Contributions:
    """Compute Carino-linked contributions over a window.

    Args:
        portfolio_returns: 1D array of daily portfolio returns (length D)
        exposures: {(layer, factor): array[D]} of daily exposures
        factor_returns: {factor: array[D]} of daily factor returns

    Returns:
        Contributions dataclass with linked contributions per (layer, factor) and residual.

    Raises:
        DataError: if any portfolio return <= -1.0
    """
    r_p = np.asarray(portfolio_returns, dtype=np.float64)

    # Validate: reject total loss or worse
    bad_mask = r_p <= -1.0
    if bad_mask.any():
        bad_idx = np.where(bad_mask)[0]
        raise DataError(
            f"Portfolio return <= -1.0 at indices {bad_idx.tolist()}. "
            "Carino linking is undefined for these values."
        )

    # Geometric total return
    R_p = np.prod(1.0 + r_p) - 1.0

    # Per-day Carino coefficients: k_t = log(1 + r_p_t) / r_p_t
    # When |r_p_t| < epsilon, k_t = 1.0 (via L'Hôpital)
    small = np.abs(r_p) < EPSILON
    safe_r_p = np.where(small, 1.0, r_p)  # avoid division by zero in np.where
    k = np.where(small, 1.0, np.log1p(safe_r_p) / safe_r_p)

    # Full-window Carino coefficient: K = log(1 + R_p) / R_p
    if abs(R_p) < EPSILON:
        K = 1.0
    else:
        K = np.log1p(R_p) / R_p

    # Linking weights
    w = k / K  # shape: (D,)

    # Compute linked contributions per (layer, factor)
    contributions: dict[tuple[str, str], float] = {}
    daily_contrib_sum = np.zeros_like(r_p)

    for (layer, factor), exp_arr in exposures.items():
        exp = np.asarray(exp_arr, dtype=np.float64)
        f_ret = np.asarray(factor_returns[factor], dtype=np.float64)

        # daily_contrib[t] = exposure[t] * factor_return[t]
        daily_contrib = exp * f_ret
        daily_contrib_sum += daily_contrib

        # linked contribution = sum(w_t * daily_contrib[t])
        linked = float(np.sum(w * daily_contrib))
        contributions[(layer, factor)] = linked

    # Residual: daily_residual = portfolio_return - sum(all daily contributions)
    daily_residual = r_p - daily_contrib_sum
    linked_residual = float(np.sum(w * daily_residual))

    return Contributions(
        layer_factor=contributions,
        residual=linked_residual,
        total_return=float(R_p),
    )

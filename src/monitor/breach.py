"""Breach detection logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from monitor.carino import Contributions
from monitor.thresholds import ThresholdConfig


@dataclass
class Breach:
    end_date: date
    layer: str
    factor: str | None  # None for residual
    window: str
    value: float
    threshold_min: float | None
    threshold_max: float | None


def detect(
    contributions: Contributions,
    config: ThresholdConfig,
    end_date: date,
    window_name: str,
) -> list[Breach]:
    """Detect threshold breaches for a set of contributions.

    Uses strict inequality: value > max or value < min.
    Only checks bounds that exist (asymmetric bounds).

    Returns list of Breach instances.
    """
    breaches: list[Breach] = []

    # Check each (layer, factor) contribution
    for (layer, factor), value in contributions.layer_factor.items():
        bounds = config.get_threshold(layer, factor, window_name)
        if bounds is None:
            continue

        if _is_breach(value, bounds.min, bounds.max):
            breaches.append(
                Breach(
                    end_date=end_date,
                    layer=layer,
                    factor=factor,
                    window=window_name,
                    value=value,
                    threshold_min=bounds.min,
                    threshold_max=bounds.max,
                )
            )

    # Check residual
    residual_bounds = config.get_threshold("residual", None, window_name)
    if residual_bounds is not None:
        if _is_breach(contributions.residual, residual_bounds.min, residual_bounds.max):
            breaches.append(
                Breach(
                    end_date=end_date,
                    layer="residual",
                    factor=None,
                    window=window_name,
                    value=contributions.residual,
                    threshold_min=residual_bounds.min,
                    threshold_max=residual_bounds.max,
                )
            )

    return breaches


def _is_breach(value: float, min_bound: float | None, max_bound: float | None) -> bool:
    """Check if value breaches bounds using strict inequality."""
    if min_bound is not None and value < min_bound:
        return True
    if max_bound is not None and value > max_bound:
        return True
    return False

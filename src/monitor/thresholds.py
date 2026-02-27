"""YAML threshold config loading and lookup."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from monitor import DataError

logger = logging.getLogger(__name__)

KNOWN_WINDOWS = {"daily", "monthly", "quarterly", "annual", "3-year"}


@dataclass
class ThresholdBounds:
    min: float | None = None
    max: float | None = None


@dataclass
class ThresholdConfig:
    layers: list[str]
    thresholds: dict[tuple[str, str | None, str], ThresholdBounds] = field(default_factory=dict)

    def get_threshold(
        self, layer: str, factor: str | None, window: str
    ) -> ThresholdBounds | None:
        """Look up threshold bounds for (layer, factor, window).

        For residual, factor should be None.
        """
        return self.thresholds.get((layer, factor, window))

    def windows_for(self, layer: str, factor: str | None) -> list[str]:
        """Return window names that have thresholds defined for this (layer, factor)."""
        return [w for (l, f, w), _ in self.thresholds.items() if l == layer and f == factor]


def load(path: Path) -> ThresholdConfig:
    """Load a threshold YAML config file.

    Expected structure:
        layers:
          - benchmark
          - tactical
        thresholds:
          tactical:
            HML:
              daily: {min: -0.01, max: 0.01}
          residual:
            annual: {min: -0.001, max: 0.001}
    """
    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise DataError(f"Threshold config {path} is not a valid YAML mapping")

    layers = raw.get("layers", [])
    if not layers:
        raise DataError(f"Threshold config {path} missing 'layers' key or empty layer list")

    for layer_name in layers:
        if "_" in layer_name:
            raise DataError(
                f"Layer name '{layer_name}' in {path} contains underscore; "
                "layer names must not contain underscores"
            )

    thresholds_raw = raw.get("thresholds", {})
    if not isinstance(thresholds_raw, dict):
        raise DataError(f"Threshold config {path}: 'thresholds' must be a mapping")

    config = ThresholdConfig(layers=layers)

    for layer_key, layer_data in thresholds_raw.items():
        if not isinstance(layer_data, dict):
            raise DataError(f"Threshold config {path}: layer '{layer_key}' must be a mapping")

        if layer_key == "residual":
            # residual: window > {min, max} — no factor level
            for window_name, bounds_raw in layer_data.items():
                _validate_window_name(window_name, path)
                bounds = _parse_bounds(bounds_raw, f"residual.{window_name}", path)
                config.thresholds[("residual", None, window_name)] = bounds
        else:
            # layer > factor > window > {min, max}
            if layer_key not in layers:
                logger.warning("Threshold layer '%s' not in layer registry of %s", layer_key, path)
            for factor_name, factor_data in layer_data.items():
                if not isinstance(factor_data, dict):
                    raise DataError(
                        f"Threshold config {path}: {layer_key}.{factor_name} must be a mapping"
                    )
                for window_name, bounds_raw in factor_data.items():
                    _validate_window_name(window_name, path)
                    bounds = _parse_bounds(
                        bounds_raw, f"{layer_key}.{factor_name}.{window_name}", path
                    )
                    config.thresholds[(layer_key, factor_name, window_name)] = bounds

    return config


def _validate_window_name(name: str, path: Path) -> None:
    if name not in KNOWN_WINDOWS:
        logger.warning("Unknown window name '%s' in %s", name, path)


def _parse_bounds(raw: dict, context: str, path: Path) -> ThresholdBounds:
    if not isinstance(raw, dict):
        raise DataError(f"Threshold config {path}: {context} must be a mapping with min/max keys")

    bounds = ThresholdBounds(
        min=raw.get("min"),
        max=raw.get("max"),
    )

    if bounds.min is not None and bounds.max is not None and bounds.min > bounds.max:
        raise DataError(f"Threshold config {path}: {context} has inverted range (min > max)")

    return bounds

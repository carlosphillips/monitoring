"""Tests for breach detection."""

from datetime import date

from monitor.breach import Breach, detect
from monitor.carino import Contributions
from monitor.thresholds import ThresholdBounds, ThresholdConfig


def _make_config(thresholds_dict):
    return ThresholdConfig(layers=["tactical"], thresholds=thresholds_dict)


class TestDetect:
    def test_breach_above_max(self):
        contrib = Contributions(
            layer_factor={("tactical", "market"): 0.006},
            residual=0.0,
            total_return=0.006,
        )
        config = _make_config({
            ("tactical", "market", "daily"): ThresholdBounds(min=-0.005, max=0.005),
        })

        breaches = detect(contrib, config, date(2024, 1, 15), "daily")
        assert len(breaches) == 1
        assert breaches[0].value == 0.006
        assert breaches[0].layer == "tactical"
        assert breaches[0].factor == "market"

    def test_breach_below_min(self):
        contrib = Contributions(
            layer_factor={("tactical", "market"): -0.006},
            residual=0.0,
            total_return=-0.006,
        )
        config = _make_config({
            ("tactical", "market", "daily"): ThresholdBounds(min=-0.005, max=0.005),
        })

        breaches = detect(contrib, config, date(2024, 1, 15), "daily")
        assert len(breaches) == 1
        assert breaches[0].value == -0.006

    def test_no_breach_at_boundary(self):
        """Exactly at the boundary should NOT breach (strict inequality)."""
        contrib = Contributions(
            layer_factor={("tactical", "market"): 0.005},
            residual=0.0,
            total_return=0.005,
        )
        config = _make_config({
            ("tactical", "market", "daily"): ThresholdBounds(min=-0.005, max=0.005),
        })

        breaches = detect(contrib, config, date(2024, 1, 15), "daily")
        assert len(breaches) == 0

    def test_asymmetric_bounds_max_only(self):
        contrib = Contributions(
            layer_factor={("tactical", "market"): -0.1},
            residual=0.0,
            total_return=-0.1,
        )
        config = _make_config({
            ("tactical", "market", "daily"): ThresholdBounds(min=None, max=0.005),
        })

        # value = -0.1, max = 0.005, but min is None -> no breach
        breaches = detect(contrib, config, date(2024, 1, 15), "daily")
        assert len(breaches) == 0

    def test_asymmetric_bounds_min_only(self):
        contrib = Contributions(
            layer_factor={("tactical", "market"): 0.1},
            residual=0.0,
            total_return=0.1,
        )
        config = _make_config({
            ("tactical", "market", "daily"): ThresholdBounds(min=-0.005, max=None),
        })

        # value = 0.1, min = -0.005, max is None -> no breach
        breaches = detect(contrib, config, date(2024, 1, 15), "daily")
        assert len(breaches) == 0

    def test_residual_breach(self):
        contrib = Contributions(
            layer_factor={("tactical", "market"): 0.001},
            residual=0.005,
            total_return=0.006,
        )
        config = ThresholdConfig(
            layers=["tactical"],
            thresholds={
                ("residual", None, "daily"): ThresholdBounds(min=-0.001, max=0.001),
            },
        )

        breaches = detect(contrib, config, date(2024, 1, 15), "daily")
        assert len(breaches) == 1
        assert breaches[0].layer == "residual"
        assert breaches[0].factor is None

    def test_no_threshold_defined(self):
        """No breach if no threshold is defined for the combination."""
        contrib = Contributions(
            layer_factor={("tactical", "market"): 999.0},
            residual=0.0,
            total_return=999.0,
        )
        config = _make_config({})  # No thresholds

        breaches = detect(contrib, config, date(2024, 1, 15), "daily")
        assert len(breaches) == 0

    def test_multiple_breaches(self):
        contrib = Contributions(
            layer_factor={
                ("tactical", "market"): 0.01,
                ("tactical", "HML"): -0.01,
            },
            residual=0.005,
            total_return=0.005,
        )
        config = ThresholdConfig(
            layers=["tactical"],
            thresholds={
                ("tactical", "market", "daily"): ThresholdBounds(min=-0.005, max=0.005),
                ("tactical", "HML", "daily"): ThresholdBounds(min=-0.005, max=0.005),
                ("residual", None, "daily"): ThresholdBounds(min=-0.001, max=0.001),
            },
        )

        breaches = detect(contrib, config, date(2024, 1, 15), "daily")
        assert len(breaches) == 3

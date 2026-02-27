"""Tests for Carino-linked contribution computation."""

import numpy as np
import pytest

from monitor import DataError
from monitor.carino import compute


class TestCompute:
    def test_invariant_single_day(self):
        """Contributions + residual must equal portfolio return for a single day."""
        r_p = np.array([0.005])
        exposures = {
            ("benchmark", "market"): np.array([0.8]),
            ("tactical", "HML"): np.array([0.05]),
        }
        factor_returns = {
            "market": np.array([0.01]),
            "HML": np.array([-0.003]),
        }

        result = compute(r_p, exposures, factor_returns)

        total_contrib = sum(result.layer_factor.values()) + result.residual
        assert abs(total_contrib - result.total_return) < 1e-10

    def test_invariant_multi_day(self):
        """Carino invariant over multiple days with realistic data."""
        np.random.seed(42)
        n_days = 50

        factor_rets = {
            "market": np.random.normal(0.001, 0.01, n_days),
            "HML": np.random.normal(0.0005, 0.005, n_days),
        }

        exposures = {
            ("benchmark", "market"): np.random.normal(0.8, 0.05, n_days),
            ("benchmark", "HML"): np.random.normal(0.1, 0.02, n_days),
            ("tactical", "market"): np.random.normal(0.05, 0.02, n_days),
            ("tactical", "HML"): np.random.normal(0.03, 0.01, n_days),
        }

        # Portfolio return = sum of contributions + residual
        daily_contrib = np.zeros(n_days)
        for (layer, factor), exp in exposures.items():
            daily_contrib += exp * factor_rets[factor]
        residual = np.random.normal(0, 0.0003, n_days)
        r_p = daily_contrib + residual

        result = compute(r_p, exposures, factor_rets)

        total_contrib = sum(result.layer_factor.values()) + result.residual
        assert abs(total_contrib - result.total_return) < 1e-10

    def test_zero_portfolio_return(self):
        """Edge case: portfolio return exactly zero on a day."""
        r_p = np.array([0.0, 0.005])
        exposures = {("benchmark", "market"): np.array([0.8, 0.8])}
        factor_returns = {"market": np.array([0.001, 0.01])}

        result = compute(r_p, exposures, factor_returns)

        total_contrib = sum(result.layer_factor.values()) + result.residual
        assert abs(total_contrib - result.total_return) < 1e-10

    def test_all_zero_returns(self):
        """Edge case: all portfolio returns are zero."""
        r_p = np.array([0.0, 0.0, 0.0])
        exposures = {("benchmark", "market"): np.array([0.8, 0.8, 0.8])}
        factor_returns = {"market": np.array([0.0, 0.0, 0.0])}

        result = compute(r_p, exposures, factor_returns)

        assert abs(result.total_return) < 1e-12
        assert abs(result.residual) < 1e-12

    def test_total_loss_raises(self):
        """Portfolio return <= -1.0 should raise DataError."""
        r_p = np.array([0.01, -1.5, 0.02])
        exposures = {("benchmark", "market"): np.array([0.8, 0.8, 0.8])}
        factor_returns = {"market": np.array([0.01, -0.02, 0.01])}

        with pytest.raises(DataError, match="<= -1.0"):
            compute(r_p, exposures, factor_returns)

    def test_single_day_window(self):
        """Single day window produces correct result."""
        r_p = np.array([0.01])
        exposures = {
            ("benchmark", "market"): np.array([1.0]),
        }
        factor_returns = {"market": np.array([0.008])}

        result = compute(r_p, exposures, factor_returns)

        # Single day: linked contrib = exposure * factor_return
        assert abs(result.layer_factor[("benchmark", "market")] - 0.008) < 1e-10
        # Residual = 0.01 - 0.008 = 0.002
        assert abs(result.residual - 0.002) < 1e-10
        # Total return = 0.01
        assert abs(result.total_return - 0.01) < 1e-10

    def test_negative_returns(self):
        """Handles negative returns correctly (but > -1.0)."""
        np.random.seed(7)
        r_p = np.array([-0.02, -0.01, 0.005])
        exposures = {("benchmark", "market"): np.array([0.8, 0.9, 0.85])}
        factor_returns = {"market": np.array([-0.025, -0.012, 0.006])}

        result = compute(r_p, exposures, factor_returns)

        total_contrib = sum(result.layer_factor.values()) + result.residual
        assert abs(total_contrib - result.total_return) < 1e-10

    def test_large_window_invariant(self):
        """Carino invariant holds for a large (250-day) window."""
        np.random.seed(99)
        n_days = 250

        factor_rets = {
            "market": np.random.normal(0.0004, 0.012, n_days),
            "HML": np.random.normal(0.0002, 0.006, n_days),
            "SMB": np.random.normal(0.0001, 0.004, n_days),
        }

        exposures = {}
        for layer in ["benchmark", "structural", "tactical"]:
            for factor in ["market", "HML", "SMB"]:
                exposures[(layer, factor)] = np.random.normal(
                    {"benchmark": 0.5, "structural": 0.2, "tactical": 0.05}[layer],
                    0.05,
                    n_days,
                )

        daily_contrib = np.zeros(n_days)
        for (layer, factor), exp in exposures.items():
            daily_contrib += exp * factor_rets[factor]
        residual = np.random.normal(0, 0.0003, n_days)
        r_p = daily_contrib + residual

        result = compute(r_p, exposures, factor_rets)

        total_contrib = sum(result.layer_factor.values()) + result.residual
        assert abs(total_contrib - result.total_return) < 1e-10

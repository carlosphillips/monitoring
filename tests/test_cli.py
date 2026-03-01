"""Tests for CLI entry point and end-to-end integration."""

import csv

import numpy as np
import pandas as pd
import pytest
import yaml
from click.testing import CliRunner

from monitor.cli import main


@pytest.fixture
def e2e_input(tmp_path):
    """Create a complete input structure for end-to-end testing."""
    input_dir = tmp_path / "input"
    (input_dir / "portfolios" / "alpha").mkdir(parents=True)
    (input_dir / "portfolios" / "beta").mkdir(parents=True)
    (input_dir / "thresholds").mkdir()

    np.random.seed(42)
    dates = pd.bdate_range("2024-01-02", periods=60)
    n = len(dates)

    # Factor returns
    fr_df = pd.DataFrame({
        "date": dates.strftime("%Y-%m-%d"),
        "market": np.random.normal(0.001, 0.01, n),
        "HML": np.random.normal(0.0005, 0.005, n),
    })
    fr_df.to_csv(input_dir / "factor_returns.csv", index=False)

    # Generate exposures for both portfolios
    for name in ["alpha", "beta"]:
        np.random.seed({"alpha": 1, "beta": 2}[name])
        exposures = {
            "benchmark_market": np.random.normal(0.8, 0.05, n),
            "benchmark_HML": np.random.normal(0.1, 0.02, n),
            "tactical_market": np.random.normal(0.05, 0.02, n),
            "tactical_HML": np.random.normal(0.03, 0.01, n),
        }

        # Compute portfolio return
        fr_market = fr_df["market"].values
        fr_hml = fr_df["HML"].values
        daily_contrib = (
            exposures["benchmark_market"] * fr_market
            + exposures["benchmark_HML"] * fr_hml
            + exposures["tactical_market"] * fr_market
            + exposures["tactical_HML"] * fr_hml
        )
        residual = np.random.normal(0, 0.0002, n)
        portfolio_return = daily_contrib + residual

        data = {
            "date": dates.strftime("%Y-%m-%d"),
            "portfolio_return": np.round(portfolio_return, 8),
        }
        data.update({k: np.round(v, 6) for k, v in exposures.items()})
        cols = ["date", "portfolio_return"] + list(exposures.keys())
        pd.DataFrame(data)[cols].to_csv(
            input_dir / "portfolios" / name / "exposures.csv", index=False
        )

    # Threshold configs
    for name in ["alpha", "beta"]:
        config = {
            "layers": ["benchmark", "tactical"],
            "thresholds": {
                "tactical": {
                    "market": {
                        "daily": {"min": -0.001, "max": 0.001},
                        "monthly": {"min": -0.01, "max": 0.01},
                    },
                    "HML": {
                        "daily": {"min": -0.0005, "max": 0.0005},
                    },
                },
                "residual": {
                    "daily": {"min": -0.0005, "max": 0.0005},
                },
            },
        }
        with open(input_dir / "thresholds" / f"{name}_thresholds.yaml", "w") as f:
            yaml.dump(config, f, default_flow_style=False)

    return input_dir


class TestCLI:
    def test_end_to_end(self, e2e_input, tmp_path):
        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(main, ["--input", str(e2e_input), "--output", str(output_dir)])

        assert result.exit_code == 0
        # Consolidated parquet (replaced summary.csv)
        assert (output_dir / "all_breaches.parquet").exists()
        # HTML reports (retained)
        assert (output_dir / "summary.html").exists()
        assert (output_dir / "alpha" / "report.html").exists()
        assert (output_dir / "beta" / "report.html").exists()
        # No CSV files should be generated (replaced with parquet)
        assert not (output_dir / "summary.csv").exists()
        assert not (output_dir / "alpha" / "breaches.csv").exists()
        assert not (output_dir / "beta" / "breaches.csv").exists()

        # Parquet attribution and breach files
        for portfolio in ["alpha", "beta"]:
            attr_dir = output_dir / portfolio / "attributions"
            assert attr_dir.exists()
            for window in ["daily", "monthly", "quarterly", "annual", "3-year"]:
                assert (attr_dir / f"{window}_attribution.parquet").exists()
                assert (attr_dir / f"{window}_breach.parquet").exists()

    def test_consolidated_breaches_parquet_exists(self, e2e_input, tmp_path):
        """Consolidated breaches parquet must be created with all portfolio data."""
        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(main, ["--input", str(e2e_input), "--output", str(output_dir)])

        assert result.exit_code == 0
        assert (output_dir / "all_breaches.parquet").exists()

        # Load and verify parquet has data from both portfolios
        import pandas as pd
        df = pd.read_parquet(output_dir / "all_breaches.parquet")
        assert len(df) > 0, "Consolidated parquet should have breach records"
        assert set(df["portfolio"].unique()) == {"alpha", "beta"}, "Should have both portfolios"
        assert len(df.columns) > 0, "Should have columns"

    def test_exit_code_zero_on_success(self, e2e_input, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, ["--input", str(e2e_input), "--output", str(tmp_path / "out")])
        assert result.exit_code == 0

    def test_exit_code_one_on_error(self, tmp_path):
        runner = CliRunner()
        result = runner.invoke(main, ["--input", str(tmp_path)])
        assert result.exit_code != 0

    def test_partial_failure(self, e2e_input, tmp_path):
        """One portfolio with bad data should not prevent the other from processing."""
        # Corrupt beta's exposures
        bad_path = e2e_input / "portfolios" / "beta" / "exposures.csv"
        bad_path.write_text("date,bad_column\n2024-01-02,0.1\n")

        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(main, ["--input", str(e2e_input), "--output", str(output_dir)])

        # Should exit 1 due to error, but alpha should still be processed
        assert result.exit_code == 1
        # Consolidated parquet should contain alpha's data (despite beta error)
        assert (output_dir / "all_breaches.parquet").exists()
        # Error is logged to stderr; with CliRunner it may be in output or not
        assert (output_dir / "alpha" / "report.html").exists()

    def test_custom_thresholds_dir(self, e2e_input, tmp_path):
        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(main, [
            "--input", str(e2e_input),
            "--thresholds", str(e2e_input / "thresholds"),
            "--output", str(output_dir),
        ])
        assert result.exit_code == 0

    def test_no_parquet_flag_skips_parquet(self, e2e_input, tmp_path):
        output_dir = tmp_path / "output"
        runner = CliRunner()
        result = runner.invoke(
            main, ["--input", str(e2e_input), "--output", str(output_dir), "--no-parquet"]
        )

        assert result.exit_code == 0
        # HTML reports still generated
        assert (output_dir / "summary.html").exists()
        assert (output_dir / "alpha" / "report.html").exists()
        # No consolidated breaches parquet when --no-parquet is used
        assert not (output_dir / "all_breaches.parquet").exists()
        # Parquet files not generated
        assert not (output_dir / "alpha" / "attributions").exists()
        assert not (output_dir / "beta" / "attributions").exists()

    def test_carino_invariant_in_e2e(self, e2e_input, tmp_path):
        """Integration test: Carino contributions sum to portfolio return."""
        from monitor import data as data_mod
        from monitor import thresholds as thresholds_mod
        from monitor.carino import compute
        from monitor.windows import WINDOWS, slice_window

        factor_returns = data_mod.load_factor_returns(e2e_input)
        config = thresholds_mod.load(e2e_input / "thresholds" / "alpha_thresholds.yaml")
        exp = data_mod.load_exposures(
            e2e_input / "portfolios" / "alpha" / "exposures.csv",
            factor_returns,
            config.layers,
        )

        # Test invariant for first 10 dates across all windows
        for end_date in exp.dates[:10]:
            for window_def in WINDOWS:
                ws = slice_window(exp.dates, end_date, window_def, exp.dates[0])
                if ws is None:
                    continue

                mask = ws.mask
                r_p = exp.portfolio_returns[mask].values
                exposures_slice = {k: s[mask].values for k, s in exp.exposures.items()}
                fr_slice = {c: factor_returns[c][mask].values for c in factor_returns.columns}

                result = compute(r_p, exposures_slice, fr_slice)
                total = sum(result.layer_factor.values()) + result.residual
                assert abs(total - result.total_return) < 1e-10, (
                    f"Carino invariant violated: {total} != {result.total_return}"
                )

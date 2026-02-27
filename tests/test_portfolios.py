"""Tests for portfolio discovery."""

import pytest
import yaml

from monitor import DataError
from monitor.portfolios import discover


class TestDiscover:
    def test_basic_discovery(self, tmp_input, sample_threshold_config, sample_exposures):
        portfolios = discover(tmp_input, tmp_input / "thresholds")
        assert len(portfolios) == 1
        assert portfolios[0].name == "test_portfolio"
        assert portfolios[0].exposures_path.exists()
        assert portfolios[0].thresholds_path.exists()

    def test_multiple_portfolios(self, tmp_path):
        (tmp_path / "portfolios").mkdir()
        (tmp_path / "thresholds").mkdir()
        for name in ["alpha", "beta"]:
            (tmp_path / "portfolios" / name).mkdir(parents=True, exist_ok=True)
            (tmp_path / "portfolios" / name / "exposures.csv").write_text("date,portfolio_return\n")
            config = {"layers": ["benchmark"], "thresholds": {}}
            with open(tmp_path / "thresholds" / f"{name}_thresholds.yaml", "w") as f:
                yaml.dump(config, f)

        portfolios = discover(tmp_path, tmp_path / "thresholds")
        assert len(portfolios) == 2
        assert [p.name for p in portfolios] == ["alpha", "beta"]  # sorted

    def test_missing_threshold_raises(self, tmp_input, sample_exposures):
        # Exposures exist but no threshold file
        with pytest.raises(DataError, match="No threshold config found"):
            discover(tmp_input, tmp_input / "thresholds")

    def test_no_portfolios_dir_raises(self, tmp_path):
        with pytest.raises(DataError, match="not found"):
            discover(tmp_path, tmp_path / "thresholds")

    def test_empty_portfolios_dir_raises(self, tmp_path):
        (tmp_path / "portfolios").mkdir()
        with pytest.raises(DataError, match="No portfolio subdirectories"):
            discover(tmp_path, tmp_path / "thresholds")

    def test_missing_exposures_raises(self, tmp_path):
        (tmp_path / "portfolios").mkdir()
        (tmp_path / "thresholds").mkdir()
        name = "empty_portfolio"
        (tmp_path / "portfolios" / name).mkdir(parents=True)
        config = {"layers": ["benchmark"], "thresholds": {}}
        with open(tmp_path / "thresholds" / f"{name}_thresholds.yaml", "w") as f:
            yaml.dump(config, f)

        with pytest.raises(DataError, match="No exposures file found"):
            discover(tmp_path, tmp_path / "thresholds")

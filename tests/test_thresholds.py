"""Tests for threshold config loading."""

import pytest
import yaml

from monitor import DataError
from monitor.thresholds import load


class TestLoad:
    def test_basic_loading(self, sample_threshold_config):
        config = load(sample_threshold_config)
        assert config.layers == ["benchmark", "tactical"]
        assert ("tactical", "market", "daily") in config.thresholds
        assert ("tactical", "HML", "daily") in config.thresholds

    def test_residual_special_case(self, sample_threshold_config):
        config = load(sample_threshold_config)
        bounds = config.get_threshold("residual", None, "daily")
        assert bounds is not None
        assert bounds.min == -0.001
        assert bounds.max == 0.001

    def test_get_threshold_returns_none_for_missing(self, sample_threshold_config):
        config = load(sample_threshold_config)
        assert config.get_threshold("benchmark", "market", "daily") is None
        assert config.get_threshold("tactical", "market", "annual") is None

    def test_asymmetric_bounds(self, tmp_path):
        config_data = {
            "layers": ["tactical"],
            "thresholds": {
                "tactical": {
                    "market": {
                        "daily": {"max": 0.01},  # min omitted
                    }
                }
            },
        }
        path = tmp_path / "test.yaml"
        with open(path, "w") as f:
            yaml.dump(config_data, f)

        config = load(path)
        bounds = config.get_threshold("tactical", "market", "daily")
        assert bounds.min is None
        assert bounds.max == 0.01

    def test_inverted_range_raises(self, tmp_path):
        config_data = {
            "layers": ["tactical"],
            "thresholds": {
                "tactical": {
                    "market": {
                        "daily": {"min": 0.05, "max": -0.05},
                    }
                }
            },
        }
        path = tmp_path / "test.yaml"
        with open(path, "w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(DataError, match="inverted range"):
            load(path)

    def test_missing_layers_raises(self, tmp_path):
        config_data = {"thresholds": {}}
        path = tmp_path / "test.yaml"
        with open(path, "w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(DataError, match="missing 'layers'"):
            load(path)

    def test_underscore_in_layer_name_raises(self, tmp_path):
        config_data = {
            "layers": ["bad_layer"],
            "thresholds": {},
        }
        path = tmp_path / "test.yaml"
        with open(path, "w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(DataError, match="contains underscore"):
            load(path)

    def test_windows_for(self, sample_threshold_config):
        config = load(sample_threshold_config)
        windows = config.windows_for("tactical", "market")
        assert set(windows) == {"daily", "monthly"}

    def test_unknown_window_warns(self, tmp_path, caplog):
        config_data = {
            "layers": ["tactical"],
            "thresholds": {
                "tactical": {
                    "market": {
                        "biweekly": {"min": -0.01, "max": 0.01},
                    }
                }
            },
        }
        path = tmp_path / "test.yaml"
        with open(path, "w") as f:
            yaml.dump(config_data, f)

        import logging

        with caplog.at_level(logging.WARNING):
            load(path)
        assert "Unknown window name 'biweekly'" in caplog.text

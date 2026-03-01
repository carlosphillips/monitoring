"""Unit tests for dimension validators and SQL injection prevention."""

from __future__ import annotations

import pytest

from monitor.dashboard.validators import DimensionValidator, SQLInjectionValidator


class TestDimensionValidator:
    """Test dimension allow-list validation."""

    def test_validate_valid_dimension(self) -> None:
        """Valid dimensions should pass validation."""
        assert DimensionValidator.validate_dimension("portfolio")
        assert DimensionValidator.validate_dimension("layer")
        assert DimensionValidator.validate_dimension("factor")
        assert DimensionValidator.validate_dimension("window")
        assert DimensionValidator.validate_dimension("date")
        assert DimensionValidator.validate_dimension("direction")

    def test_validate_invalid_dimension(self) -> None:
        """Invalid dimension names should fail."""
        assert not DimensionValidator.validate_dimension("invalid_dim")
        assert not DimensionValidator.validate_dimension("layer'; DROP TABLE--")
        assert not DimensionValidator.validate_dimension("")

    def test_validate_direction(self) -> None:
        """Direction values should be 'upper' or 'lower'."""
        assert DimensionValidator.validate_direction("upper")
        assert DimensionValidator.validate_direction("lower")
        assert not DimensionValidator.validate_direction("upper'; DROP--")
        assert not DimensionValidator.validate_direction("invalid")
        assert not DimensionValidator.validate_direction("")

    def test_validate_layer(self) -> None:
        """Layer values should match allow-list."""
        assert DimensionValidator.validate_layer("benchmark")
        assert DimensionValidator.validate_layer("tactical")
        assert DimensionValidator.validate_layer("structural")
        assert DimensionValidator.validate_layer("residual")
        assert not DimensionValidator.validate_layer("invalid_layer")

    def test_validate_factor(self) -> None:
        """Factor values should match allow-list."""
        assert DimensionValidator.validate_factor("HML")
        assert DimensionValidator.validate_factor("SMB")
        assert DimensionValidator.validate_factor("MOM")
        assert DimensionValidator.validate_factor("QMJ")
        assert DimensionValidator.validate_factor("BAB")
        assert not DimensionValidator.validate_factor("invalid_factor")
        assert not DimensionValidator.validate_factor("hml")  # Case sensitive

    def test_validate_window(self) -> None:
        """Window values should match allow-list."""
        assert DimensionValidator.validate_window("daily")
        assert DimensionValidator.validate_window("monthly")
        assert DimensionValidator.validate_window("quarterly")
        assert DimensionValidator.validate_window("annual")
        assert DimensionValidator.validate_window("3year")
        assert not DimensionValidator.validate_window("invalid_window")

    def test_validate_group_by_valid(self) -> None:
        """Valid GROUP BY dimensions should pass."""
        assert DimensionValidator.validate_group_by(["layer"])
        assert DimensionValidator.validate_group_by(["layer", "factor"])
        assert DimensionValidator.validate_group_by(["portfolio", "layer", "factor"])

    def test_validate_group_by_invalid_dimension(self) -> None:
        """GROUP BY with invalid dimension should fail."""
        assert not DimensionValidator.validate_group_by(["invalid_dim"])
        assert not DimensionValidator.validate_group_by(["layer", "invalid_dim"])

    def test_validate_filter_values_direction(self) -> None:
        """Filter values for direction must be valid."""
        assert DimensionValidator.validate_filter_values("direction", ["upper"])
        assert DimensionValidator.validate_filter_values("direction", ["upper", "lower"])
        assert not DimensionValidator.validate_filter_values("direction", ["invalid"])
        assert not DimensionValidator.validate_filter_values("direction", ["upper'; DROP--"])

    def test_validate_filter_values_layer(self) -> None:
        """Filter values for layer must match allow-list."""
        assert DimensionValidator.validate_filter_values("layer", ["tactical"])
        assert DimensionValidator.validate_filter_values("layer", ["tactical", "residual"])
        assert not DimensionValidator.validate_filter_values("layer", ["invalid_layer"])

    def test_validate_filter_values_invalid_dimension(self) -> None:
        """Filter with invalid dimension should fail regardless of values."""
        assert not DimensionValidator.validate_filter_values("invalid_dim", ["any_value"])

    def test_validate_all_filters(self) -> None:
        """Validate multiple filters together."""
        filters = {
            "direction": ["upper"],
            "layer": ["tactical"],
        }
        assert DimensionValidator.validate_all_filters(filters)

        # Mix of valid and invalid
        invalid_filters = {
            "direction": ["upper"],
            "invalid_dim": ["value"],
        }
        assert not DimensionValidator.validate_all_filters(invalid_filters)


class TestSQLInjectionValidator:
    """Test SQL injection pattern detection."""

    def test_safe_strings(self) -> None:
        """Safe strings should pass validation."""
        assert SQLInjectionValidator.validate_safe_string("portfolio_a")
        assert SQLInjectionValidator.validate_safe_string("2026-01-01")
        assert SQLInjectionValidator.validate_safe_string("tactical")
        assert SQLInjectionValidator.validate_safe_string("123")

    def test_detect_sql_keywords(self) -> None:
        """SQL keywords should be detected as suspicious."""
        assert SQLInjectionValidator.is_suspicious("DROP TABLE users")
        assert SQLInjectionValidator.is_suspicious("DELETE FROM breaches")
        assert SQLInjectionValidator.is_suspicious("UNION SELECT")
        assert SQLInjectionValidator.is_suspicious("INSERT INTO")
        assert SQLInjectionValidator.is_suspicious("UPDATE breaches SET")

    def test_detect_sql_comments(self) -> None:
        """SQL comments should be detected."""
        assert SQLInjectionValidator.is_suspicious("value -- comment")
        assert SQLInjectionValidator.is_suspicious("value /* comment */")

    def test_detect_statement_terminator(self) -> None:
        """Semicolon should be detected."""
        assert SQLInjectionValidator.is_suspicious("value;")
        assert SQLInjectionValidator.is_suspicious("tactical'; DROP TABLE--")

    def test_classic_sql_injection(self) -> None:
        """Classic SQL injection patterns should be detected."""
        assert SQLInjectionValidator.is_suspicious("' OR 1=1")
        assert SQLInjectionValidator.is_suspicious("' OR '1'='1")

    def test_case_insensitive_detection(self) -> None:
        """Detection should be case-insensitive."""
        assert SQLInjectionValidator.is_suspicious("select * from users")
        assert SQLInjectionValidator.is_suspicious("DROP table")
        assert SQLInjectionValidator.is_suspicious("union all select")

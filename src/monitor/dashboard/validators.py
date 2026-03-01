"""Security validators to prevent SQL injection and data corruption.

All user-supplied inputs are validated against allow-lists before being used
in SQL queries or stored in application state.
"""

from __future__ import annotations

from typing import Any

from monitor.dashboard.dimensions import DIMENSIONS, is_valid_dimension


class DimensionValidator:
    """Validates dimensions, directions, and other discrete values against allow-lists.

    Prevents SQL injection via malicious GROUP BY, WHERE, or filter values.
    """

    # All valid dimension names
    ALLOWED_DIMENSIONS = set(DIMENSIONS.keys())

    # Breach direction values
    ALLOWED_DIRECTIONS = {"upper", "lower"}

    # Layer names (from domain knowledge)
    ALLOWED_LAYERS = {"benchmark", "tactical", "structural", "residual"}

    # Factor names (from domain knowledge - 5 factors in Fama-French)
    ALLOWED_FACTORS = {"HML", "SMB", "MOM", "QMJ", "BAB"}

    # Window names (from windows.py WINDOW_NAMES)
    ALLOWED_WINDOWS = {"daily", "monthly", "quarterly", "annual", "3year"}

    @staticmethod
    def validate_dimension(dimension: str) -> bool:
        """Check if a dimension name is whitelisted.

        Args:
            dimension: Dimension name to validate

        Returns:
            True if valid, False otherwise
        """
        return is_valid_dimension(dimension)

    @staticmethod
    def validate_direction(direction: str) -> bool:
        """Check if a breach direction is valid.

        Args:
            direction: Direction value ('upper' or 'lower')

        Returns:
            True if valid, False otherwise
        """
        return direction in DimensionValidator.ALLOWED_DIRECTIONS

    @staticmethod
    def validate_layer(layer: str) -> bool:
        """Check if a layer name is valid.

        Args:
            layer: Layer name to validate

        Returns:
            True if valid, False otherwise
        """
        return layer in DimensionValidator.ALLOWED_LAYERS

    @staticmethod
    def validate_factor(factor: str) -> bool:
        """Check if a factor name is valid.

        Args:
            factor: Factor name to validate

        Returns:
            True if valid, False otherwise
        """
        return factor in DimensionValidator.ALLOWED_FACTORS

    @staticmethod
    def validate_window(window: str) -> bool:
        """Check if a window name is valid.

        Args:
            window: Window name to validate

        Returns:
            True if valid, False otherwise
        """
        return window in DimensionValidator.ALLOWED_WINDOWS

    @staticmethod
    def validate_group_by(dimensions: list[str]) -> bool:
        """Ensure all GROUP BY dimensions are whitelisted.

        Args:
            dimensions: List of dimension names for GROUP BY

        Returns:
            True if all are valid, False otherwise
        """
        return all(DimensionValidator.validate_dimension(d) for d in dimensions)

    @staticmethod
    def validate_filter_values(dimension: str, values: list[Any]) -> bool:
        """Validate filter values for a given dimension.

        Checks that:
        1. Dimension name is valid
        2. Values match dimension-specific allow-list (if applicable)

        Args:
            dimension: Dimension name
            values: Values to filter by

        Returns:
            True if all are valid, False otherwise
        """
        if not DimensionValidator.validate_dimension(dimension):
            return False

        # Dimension-specific validation
        validators = {
            "direction": DimensionValidator.validate_direction,
            "layer": DimensionValidator.validate_layer,
            "factor": DimensionValidator.validate_factor,
            "window": DimensionValidator.validate_window,
        }

        validator = validators.get(dimension)
        if validator:
            return all(validator(str(v)) for v in values)

        # For portfolio and date, we don't have a predefined allow-list
        # (portfolios and dates can be arbitrary)
        # Just ensure values are non-empty strings
        return all(str(v).strip() for v in values)

    @staticmethod
    def validate_all_filters(filters: dict[str, list[Any]]) -> bool:
        """Validate all filters at once.

        Args:
            filters: Dict mapping dimension name to list of values

        Returns:
            True if all are valid, False otherwise
        """
        return all(
            DimensionValidator.validate_filter_values(dim, values)
            for dim, values in filters.items()
        )


class SQLInjectionValidator:
    """Additional validation layer to catch potential SQL injection patterns."""

    # Patterns that suggest SQL injection attempts
    SUSPICIOUS_PATTERNS = [
        ";",  # Semicolon (statement terminator)
        "--",  # SQL comment
        "/*",  # Multi-line comment start
        "*/",  # Multi-line comment end
        "DROP",  # DDL
        "DELETE",  # DML
        "TRUNCATE",  # DDL
        "CREATE",  # DDL
        "ALTER",  # DDL
        "UNION",  # Query composition
        "SELECT",  # Nested query
        "INSERT",  # DML
        "UPDATE",  # DML
        "EXEC",  # Execution
        "OR 1=1",  # Classic injection
    ]

    @staticmethod
    def is_suspicious(value: str) -> bool:
        """Check if a value contains suspicious SQL patterns.

        Args:
            value: Value to check

        Returns:
            True if suspicious, False otherwise
        """
        value_upper = str(value).upper()
        return any(pattern in value_upper for pattern in SQLInjectionValidator.SUSPICIOUS_PATTERNS)

    @staticmethod
    def validate_safe_string(value: str) -> bool:
        """Check if a string is safe from SQL injection.

        This is a defense-in-depth check; parameterized queries are the
        primary defense.

        Args:
            value: Value to check

        Returns:
            True if safe, False if suspicious
        """
        return not SQLInjectionValidator.is_suspicious(value)

"""Type-safe dashboard state management with Pydantic validation."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, field_validator


class FilterSpec(BaseModel):
    """Single dimension filter specification."""

    dimension: str
    values: list[str]

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, v: str) -> str:
        """Dimension name must be non-empty."""
        if not v or not v.strip():
            raise ValueError("Dimension name cannot be empty")
        return v.lower()

    @field_validator("values")
    @classmethod
    def validate_values(cls, v: list[str]) -> list[str]:
        """Filter values must be non-empty."""
        if not v:
            raise ValueError("Filter values cannot be empty")
        return v


class DashboardState(BaseModel):
    """Canonical application state for the Breach Pivot Dashboard.

    Single-source-of-truth for all user selections (filters, hierarchy, brush).
    Validated and immutable once created. All callback inputs converge to
    state changes, preventing race conditions and state desynchronization.
    """

    # Primary filter: which portfolios to analyze
    selected_portfolios: list[str] = ["All"]

    # Date range filter (inclusive)
    date_range: tuple[date, date] | None = None

    # Hierarchy configuration: ordered dimensions for grouping (1-3 levels)
    hierarchy_dimensions: list[str] = ["layer", "factor"]

    # Secondary date filter from box-select on timeline x-axis
    brush_selection: dict[str, str] | None = None

    # Hierarchy expansion state: set of expanded group keys (for expand/collapse triangles)
    # Empty set means all collapsed, None means all expanded (default)
    expanded_groups: set[str] | None = None

    # Additional filters: layer, factor, window, direction
    # These are complementary to hierarchy_dimensions
    layer_filter: list[str] | None = None
    factor_filter: list[str] | None = None
    window_filter: list[str] | None = None
    direction_filter: list[str] | None = None

    @field_validator("selected_portfolios")
    @classmethod
    def validate_portfolios(cls, v: list[str]) -> list[str]:
        """Portfolio list must be non-empty."""
        if not v:
            raise ValueError("selected_portfolios cannot be empty")
        return v

    @field_validator("date_range")
    @classmethod
    def validate_date_range(cls, v: tuple[date, date] | None) -> tuple[date, date] | None:
        """Date range must have start <= end."""
        if v:
            start, end = v
            if start > end:
                raise ValueError(f"Start date {start} > end date {end}")
        return v

    @field_validator("hierarchy_dimensions")
    @classmethod
    def validate_hierarchy_dimensions(cls, v: list[str]) -> list[str]:
        """Hierarchy dimensions must be valid and unique.

        Max 3 levels, no duplicates, and must be from allowed dimensions.
        """
        if len(v) > 3:
            raise ValueError(f"Max 3 hierarchy levels, got {len(v)}")

        if len(v) != len(set(v)):
            raise ValueError("Duplicate dimensions in hierarchy not allowed")

        allowed = {"portfolio", "layer", "factor", "window", "end_date", "direction"}
        invalid = [d for d in v if d not in allowed]
        if invalid:
            raise ValueError(f"Invalid dimensions: {invalid}. Allowed: {allowed}")

        return v

    def to_dict(self) -> dict:
        """Serialize to dict for dcc.Store."""
        data = self.model_dump(mode="json")
        # Convert set to list for JSON serialization
        if self.expanded_groups is not None:
            data["expanded_groups"] = list(self.expanded_groups)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> DashboardState:
        """Deserialize from dict from dcc.Store."""
        # Parse date strings back to date objects if needed
        if data.get("date_range"):
            start, end = data["date_range"]
            if isinstance(start, str):
                start = date.fromisoformat(start)
            if isinstance(end, str):
                end = date.fromisoformat(end)
            data["date_range"] = (start, end)

        # Convert list back to set for expanded_groups
        if "expanded_groups" in data and data["expanded_groups"] is not None:
            data["expanded_groups"] = set(data["expanded_groups"])

        return cls(**data)

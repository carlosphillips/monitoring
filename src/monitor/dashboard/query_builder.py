"""Query building utilities for the breach explorer dashboard.

Functions in this module construct parameterised SQL fragments (WHERE clauses,
selection filters) used by the Dash callbacks.  They are intentionally free of
any Dash or Flask imports so they can be unit-tested without an application
context.
"""

from __future__ import annotations

from monitor.dashboard.constants import (
    COLUMN_AXIS_DIMENSIONS,
    GROUPABLE_DIMENSIONS,
    NO_FACTOR_LABEL,
    TIME_GRANULARITIES,
    granularity_to_trunc,
)

# Allow-list of column names that may be interpolated as SQL identifiers.
# Dash stores and inputs are client-side JSON that can be tampered with;
# all values used as SQL identifiers MUST be validated against this set.
VALID_SQL_COLUMNS = frozenset(GROUPABLE_DIMENSIONS) | frozenset(COLUMN_AXIS_DIMENSIONS)


def validate_sql_dimensions(
    hierarchy: list[str] | None,
    column_axis: str | None,
) -> None:
    """Validate that hierarchy and column_axis values are known dimensions.

    Raises ValueError if any value is not in the allow-list.
    """
    if hierarchy:
        for dim in hierarchy:
            if dim not in VALID_SQL_COLUMNS:
                raise ValueError(f"Invalid hierarchy dimension: {dim!r}")
    if column_axis is not None and column_axis not in VALID_SQL_COLUMNS:
        raise ValueError(f"Invalid column axis: {column_axis!r}")


def build_where_clause(
    portfolios: list[str] | None,
    layers: list[str] | None,
    factors: list[str] | None,
    windows: list[str] | None,
    directions: list[str] | None,
    start_date: str | None,
    end_date: str | None,
    abs_value_range: list[float] | None,
    distance_range: list[float] | None,
) -> tuple[str, list[str | float]]:
    """Build a WHERE clause from filter values.

    Empty/None multi-selects mean "no filter" (show all).

    Returns:
        (where_clause_sql, params) tuple. The SQL string starts with "WHERE"
        if any conditions exist, otherwise empty string.
    """
    conditions: list[str] = []
    params: list[str | float] = []

    if portfolios:
        placeholders = ", ".join("?" for _ in portfolios)
        conditions.append(f"portfolio IN ({placeholders})")
        params.extend(portfolios)

    if layers:
        placeholders = ", ".join("?" for _ in layers)
        conditions.append(f"layer IN ({placeholders})")
        params.extend(layers)

    if factors:
        # Handle "(no factor)" label -> NULL factor in DB
        has_no_factor = NO_FACTOR_LABEL in factors
        real_factors = [f for f in factors if f != NO_FACTOR_LABEL]

        factor_conditions = []
        if real_factors:
            placeholders = ", ".join("?" for _ in real_factors)
            factor_conditions.append(f"factor IN ({placeholders})")
            params.extend(real_factors)
        if has_no_factor:
            factor_conditions.append("(factor IS NULL OR factor = '')")

        if factor_conditions:
            conditions.append(f"({' OR '.join(factor_conditions)})")

    if windows:
        placeholders = ", ".join("?" for _ in windows)
        conditions.append(f'"window" IN ({placeholders})')
        params.extend(windows)

    if directions:
        placeholders = ", ".join("?" for _ in directions)
        conditions.append(f"direction IN ({placeholders})")
        params.extend(directions)

    if start_date:
        conditions.append("end_date >= ?")
        params.append(start_date)

    if end_date:
        conditions.append("end_date <= ?")
        params.append(end_date)

    if abs_value_range and len(abs_value_range) == 2:
        conditions.append("abs_value >= ? AND abs_value <= ?")
        params.extend(abs_value_range)

    if distance_range and len(distance_range) == 2:
        conditions.append("distance >= ? AND distance <= ?")
        params.extend(distance_range)

    if conditions:
        return "WHERE " + " AND ".join(conditions), params
    return "", []


def append_where(
    where_sql: str,
    params: list[str | float],
    extra_sql: str,
    extra_params: list[str],
) -> tuple[str, list[str | float]]:
    """Append an AND-joined SQL fragment to an existing WHERE clause.

    If *extra_sql* is empty the inputs are returned unchanged.
    """
    if not extra_sql:
        return where_sql, params
    if where_sql:
        where_sql += " AND " + extra_sql
    else:
        where_sql = "WHERE " + extra_sql
    params.extend(extra_params)
    return where_sql, params


def _parse_group_key_conditions(
    group_key: str,
    conditions: list[str],
    params: list[str],
) -> None:
    """Parse a pipe-delimited group key into SQL conditions and params.

    Each segment has the form ``dim=value``.  Dimensions are validated
    against the allow-list; unknown dimensions are silently skipped.
    """
    for part in group_key.split("|"):
        if "=" not in part:
            continue
        dim, val = part.split("=", 1)
        if dim not in GROUPABLE_DIMENSIONS:
            continue
        if dim == "factor" and val == NO_FACTOR_LABEL:
            conditions.append("(factor IS NULL OR factor = '')")
        else:
            conditions.append(f'"{dim}" = ?')
            params.append(val)


def build_selection_where(
    selections: list[dict] | dict | None,
    granularity_override: str | None,
    column_axis: str | None,
) -> tuple[str, list[str]]:
    """Build additional WHERE conditions from pivot selection(s).

    Accepts a list of selection dicts (multi-select) or a single dict
    (backward-compatible).  Multiple selections are OR'd together so the
    detail view shows the union of all selected cells.

    Returns:
        (sql_fragment, params) -- the SQL does NOT include "WHERE" prefix.
    """
    # Normalise input: single dict → one-element list, None/empty → []
    if selections is None:
        selections = []
    elif isinstance(selections, dict):
        selections = [selections]

    if not selections:
        return "", []

    parts: list[str] = []
    all_params: list[str] = []
    for sel in selections:
        sql, params = _build_single_selection_where(
            sel, granularity_override, column_axis,
        )
        if sql:
            parts.append(f"({sql})")
            all_params.extend(params)

    if not parts:
        return "", []
    if len(parts) == 1:
        # Avoid unnecessary parentheses for single selection
        return parts[0].strip("()"), all_params
    return " OR ".join(parts), all_params


def _build_single_selection_where(
    selection: dict,
    granularity_override: str | None,
    column_axis: str | None,
) -> tuple[str, list[str]]:
    """Build WHERE conditions from a single pivot selection dict."""
    if not selection:
        return "", []

    sel_type = selection.get("type")
    conditions: list[str] = []
    params: list[str] = []

    if sel_type == "timeline":
        time_bucket = selection.get("time_bucket")
        direction = selection.get("direction")
        if time_bucket and direction:
            # Determine granularity for bucket matching
            granularity = granularity_override or "Monthly"
            trunc = granularity_to_trunc(granularity)
            bucket_expr = f"DATE_TRUNC('{trunc}', end_date::DATE)"
            conditions.append(f"{bucket_expr}::VARCHAR = ?")
            params.append(time_bucket)
            conditions.append("direction = ?")
            params.append(direction)

    elif sel_type == "category":
        col_dim = selection.get("column_dim")
        col_value = selection.get("column_value")
        group_key = selection.get("group_key")

        if col_dim and col_value:
            # Validate col_dim against allow-list before SQL interpolation
            if col_dim not in VALID_SQL_COLUMNS:
                return "", []
            # Handle factor "(no factor)" special case
            if col_dim == "factor" and col_value == NO_FACTOR_LABEL:
                conditions.append("(factor IS NULL OR factor = '')")
            else:
                conditions.append(f'"{col_dim}" = ?')
                params.append(col_value)

        if group_key and group_key != "__flat__":
            _parse_group_key_conditions(group_key, conditions, params)

    elif sel_type == "group":
        group_key = selection.get("group_key")
        if group_key:
            _parse_group_key_conditions(group_key, conditions, params)

    if conditions:
        return " AND ".join(conditions), params
    return "", []

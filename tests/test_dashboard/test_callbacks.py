"""Tests for dashboard callbacks: filter, hierarchy, column axis, pivot selection."""

from __future__ import annotations

import pytest

from monitor.dashboard.callbacks import (
    _build_selected_cells_set,
    _get_available_dimensions,
    _get_column_axis_options,
)
from monitor.dashboard.callbacks import _extract_brush_range
from monitor.dashboard.query_builder import (
    append_where,
    build_brush_where,
    build_selection_where,
    build_where_clause,
    validate_sql_dimensions,
)
from monitor.dashboard.constants import (
    COLUMN_AXIS_DIMENSIONS,
    GROUPABLE_DIMENSIONS,
    NO_FACTOR_LABEL,
    TIME,
)
from monitor.dashboard.data import load_breaches


class TestBuildWhereClause:
    """Tests for build_where_clause()."""

    def test_empty_filters_no_where(self):
        sql, params = build_where_clause(None, None, None, None, None, None, None, None, None)
        assert sql == ""
        assert params == []

    def test_empty_lists_no_where(self):
        sql, params = build_where_clause([], [], [], [], [], None, None, None, None)
        assert sql == ""
        assert params == []

    def test_single_portfolio(self):
        sql, params = build_where_clause(
            ["portfolio_a"], None, None, None, None, None, None, None, None
        )
        assert "portfolio IN (?)" in sql
        assert params == ["portfolio_a"]

    def test_multiple_portfolios(self):
        sql, params = build_where_clause(
            ["portfolio_a", "portfolio_b"], None, None, None, None, None, None, None, None
        )
        assert "portfolio IN (?, ?)" in sql
        assert params == ["portfolio_a", "portfolio_b"]

    def test_layer_filter(self):
        sql, params = build_where_clause(
            None, ["structural", "tactical"], None, None, None, None, None, None, None
        )
        assert "layer IN (?, ?)" in sql
        assert params == ["structural", "tactical"]

    def test_factor_with_no_factor_label(self):
        sql, params = build_where_clause(
            None, None, [NO_FACTOR_LABEL], None, None, None, None, None, None
        )
        assert "factor IS NULL OR factor = ''" in sql
        assert params == []

    def test_factor_with_real_and_no_factor(self):
        sql, params = build_where_clause(
            None, None, ["market", NO_FACTOR_LABEL], None, None, None, None, None, None
        )
        assert "factor IN (?)" in sql
        assert "factor IS NULL OR factor = ''" in sql
        assert params == ["market"]

    def test_factor_real_only(self):
        sql, params = build_where_clause(
            None, None, ["market", "HML"], None, None, None, None, None, None
        )
        assert "factor IN (?, ?)" in sql
        assert NO_FACTOR_LABEL not in sql
        assert params == ["market", "HML"]

    def test_window_filter(self):
        sql, params = build_where_clause(None, None, None, ["daily"], None, None, None, None, None)
        assert '"window" IN (?)' in sql
        assert params == ["daily"]

    def test_direction_filter(self):
        sql, params = build_where_clause(None, None, None, None, ["upper"], None, None, None, None)
        assert "direction IN (?)" in sql
        assert params == ["upper"]

    def test_date_range(self):
        sql, params = build_where_clause(
            None, None, None, None, None, "2024-01-01", "2024-03-31", None, None
        )
        assert "end_date >= ?" in sql
        assert "end_date <= ?" in sql
        assert params == ["2024-01-01", "2024-03-31"]

    def test_abs_value_range(self):
        sql, params = build_where_clause(
            None, None, None, None, None, None, None, [0.001, 0.01], None
        )
        assert "abs_value >= ? AND abs_value <= ?" in sql
        assert params == [0.001, 0.01]

    def test_distance_range(self):
        sql, params = build_where_clause(
            None, None, None, None, None, None, None, None, [0.0, 0.005]
        )
        assert "distance >= ? AND distance <= ?" in sql
        assert params == [0.0, 0.005]

    def test_combined_filters(self):
        sql, params = build_where_clause(
            ["portfolio_a"],
            ["structural"],
            ["market"],
            ["daily"],
            ["upper"],
            "2024-01-01",
            "2024-01-31",
            [0.001, 0.01],
            [0.0, 0.005],
        )
        assert sql.startswith("WHERE ")
        assert "portfolio IN (?)" in sql
        assert "layer IN (?)" in sql
        assert "factor IN (?)" in sql
        assert '"window" IN (?)' in sql
        assert "direction IN (?)" in sql
        assert "end_date >= ?" in sql
        assert "end_date <= ?" in sql
        assert "abs_value >= ?" in sql
        assert "distance >= ?" in sql
        assert len(params) == 11


class TestFilterWithDuckDB:
    """Integration tests: run build_where_clause against real DuckDB data."""

    def test_filter_by_portfolio(self, sample_output):
        conn = load_breaches(sample_output)
        where_sql, params = build_where_clause(
            ["portfolio_a"], None, None, None, None, None, None, None, None
        )
        count = conn.execute(f"SELECT COUNT(*) FROM breaches {where_sql}", params).fetchone()[0]
        assert count == 5  # portfolio_a has 5 breaches

    def test_filter_by_direction(self, sample_output):
        conn = load_breaches(sample_output)
        where_sql, params = build_where_clause(
            None, None, None, None, ["upper"], None, None, None, None
        )
        count = conn.execute(f"SELECT COUNT(*) FROM breaches {where_sql}", params).fetchone()[0]
        # Upper: portfolio_a rows 0,4 + portfolio_b row 0 = 3
        assert count == 3

    def test_filter_no_factor_label(self, sample_output):
        conn = load_breaches(sample_output)
        where_sql, params = build_where_clause(
            None, None, [NO_FACTOR_LABEL], None, None, None, None, None, None
        )
        count = conn.execute(f"SELECT COUNT(*) FROM breaches {where_sql}", params).fetchone()[0]
        assert count == 1  # Only the residual breach

    def test_filter_date_range(self, sample_output):
        conn = load_breaches(sample_output)
        where_sql, params = build_where_clause(
            None, None, None, None, None, "2024-01-03", "2024-01-05", None, None
        )
        count = conn.execute(f"SELECT COUNT(*) FROM breaches {where_sql}", params).fetchone()[0]
        # Jan 3: 2 breaches (portfolio_a), Jan 4: 1 (portfolio_a), Jan 5: 1 (portfolio_b)
        assert count == 4

    def test_empty_filter_returns_all(self, sample_output):
        conn = load_breaches(sample_output)
        where_sql, params = build_where_clause(
            None, None, None, None, None, None, None, None, None
        )
        count = conn.execute(f"SELECT COUNT(*) FROM breaches {where_sql}", params).fetchone()[0]
        assert count == 7

    def test_zero_match_filter(self, sample_output):
        conn = load_breaches(sample_output)
        where_sql, params = build_where_clause(
            ["nonexistent_portfolio"], None, None, None, None, None, None, None, None
        )
        count = conn.execute(f"SELECT COUNT(*) FROM breaches {where_sql}", params).fetchone()[0]
        assert count == 0


class TestGetAvailableDimensions:
    """Tests for _get_available_dimensions() -- dimension exclusivity."""

    def test_empty_hierarchy_returns_all(self):
        options = _get_available_dimensions([])
        values = [o["value"] for o in options]
        assert values == list(GROUPABLE_DIMENSIONS)

    def test_one_dimension_used(self):
        options = _get_available_dimensions(["portfolio"])
        values = [o["value"] for o in options]
        assert "portfolio" not in values
        assert len(values) == len(GROUPABLE_DIMENSIONS) - 1

    def test_exclude_index_allows_own_value(self):
        # Level 0 has "portfolio" -- when computing options for level 0,
        # "portfolio" should still be available (excluded from "used" set)
        options = _get_available_dimensions(["portfolio", "layer"], exclude_index=0)
        values = [o["value"] for o in options]
        assert "portfolio" in values  # own value is available
        assert "layer" not in values  # other level's value is excluded

    def test_two_dimensions_used(self):
        options = _get_available_dimensions(["portfolio", "layer"])
        values = [o["value"] for o in options]
        assert "portfolio" not in values
        assert "layer" not in values
        assert len(values) == len(GROUPABLE_DIMENSIONS) - 2

    def test_all_dimensions_used(self):
        options = _get_available_dimensions(list(GROUPABLE_DIMENSIONS))
        assert len(options) == 0

    def test_options_have_labels(self):
        options = _get_available_dimensions([])
        for opt in options:
            assert "label" in opt
            assert "value" in opt
            assert opt["label"]  # non-empty label

    def test_column_axis_excludes_groupable(self):
        # When column_axis is "portfolio", it should be excluded from hierarchy options
        options = _get_available_dimensions([], column_axis="portfolio")
        values = [o["value"] for o in options]
        assert "portfolio" not in values

    def test_column_axis_time_not_excluded(self):
        # Time (end_date) is not groupable, so column_axis=TIME doesn't exclude anything
        options = _get_available_dimensions([], column_axis=TIME)
        values = [o["value"] for o in options]
        assert len(values) == len(GROUPABLE_DIMENSIONS)


class TestGetColumnAxisOptions:
    """Tests for _get_column_axis_options() -- column axis exclusivity."""

    def test_empty_hierarchy_returns_all(self):
        options = _get_column_axis_options([])
        values = [o["value"] for o in options]
        assert values == list(COLUMN_AXIS_DIMENSIONS)

    def test_hierarchy_excludes_from_column_axis(self):
        options = _get_column_axis_options(["portfolio"])
        values = [o["value"] for o in options]
        assert "portfolio" not in values
        assert TIME in values  # Time is never excluded

    def test_multiple_hierarchy_dims_excluded(self):
        options = _get_column_axis_options(["portfolio", "layer"])
        values = [o["value"] for o in options]
        assert "portfolio" not in values
        assert "layer" not in values
        assert TIME in values

    def test_direction_not_in_column_axis(self):
        # Direction is groupable but NOT a column axis dimension
        options = _get_column_axis_options(["direction"])
        values = [o["value"] for o in options]
        # direction was in hierarchy but isn't in COLUMN_AXIS_DIMENSIONS anyway
        assert "direction" not in values


class TestBuildSelectionWhere:
    """Tests for build_selection_where() -- pivot selection filtering."""

    def test_no_selection(self):
        sql, params = build_selection_where(None, None, None)
        assert sql == ""
        assert params == []

    def test_timeline_selection(self):
        selection = {
            "type": "timeline",
            "time_bucket": "2024-01-01",
            "direction": "lower",
        }
        sql, params = build_selection_where(selection, "Daily", TIME)
        assert "DATE_TRUNC" in sql
        assert "direction = ?" in sql
        assert "2024-01-01" in params
        assert "lower" in params

    def test_category_selection(self):
        selection = {
            "type": "category",
            "column_dim": "portfolio",
            "column_value": "portfolio_a",
            "group_key": "__flat__",
        }
        sql, params = build_selection_where(selection, None, "portfolio")
        assert '"portfolio" = ?' in sql
        assert params == ["portfolio_a"]

    def test_category_with_group_key(self):
        selection = {
            "type": "category",
            "column_dim": "portfolio",
            "column_value": "portfolio_a",
            "group_key": "layer=structural",
        }
        sql, params = build_selection_where(selection, None, "portfolio")
        assert '"portfolio" = ?' in sql
        assert '"layer" = ?' in sql
        assert "portfolio_a" in params
        assert "structural" in params

    def test_category_no_factor(self):
        selection = {
            "type": "category",
            "column_dim": "factor",
            "column_value": NO_FACTOR_LABEL,
            "group_key": "__flat__",
        }
        sql, params = build_selection_where(selection, None, "factor")
        assert "factor IS NULL OR factor = ''" in sql
        assert params == []

    def test_empty_selection_dict(self):
        sql, params = build_selection_where({}, None, None)
        assert sql == ""
        assert params == []

    def test_group_selection_single_level(self):
        selection = {"type": "group", "group_key": "portfolio=portfolio_a"}
        sql, params = build_selection_where(selection, None, None)
        assert '"portfolio" = ?' in sql
        assert params == ["portfolio_a"]

    def test_group_selection_multi_level(self):
        selection = {
            "type": "group",
            "group_key": "portfolio=portfolio_a|layer=structural",
        }
        sql, params = build_selection_where(selection, None, None)
        assert '"portfolio" = ?' in sql
        assert '"layer" = ?' in sql
        assert "portfolio_a" in params
        assert "structural" in params

    def test_group_selection_invalid_dim_skipped(self):
        selection = {"type": "group", "group_key": "invalid_dim=value"}
        sql, params = build_selection_where(selection, None, None)
        assert sql == ""
        assert params == []

    def test_group_selection_no_factor(self):
        selection = {"type": "group", "group_key": f"factor={NO_FACTOR_LABEL}"}
        sql, params = build_selection_where(selection, None, None)
        assert "factor IS NULL OR factor = ''" in sql
        assert params == []

    def test_group_selection_empty_key(self):
        selection = {"type": "group", "group_key": ""}
        sql, params = build_selection_where(selection, None, None)
        assert sql == ""
        assert params == []

    def test_group_selection_no_key(self):
        selection = {"type": "group"}
        sql, params = build_selection_where(selection, None, None)
        assert sql == ""
        assert params == []

    def test_empty_list(self):
        sql, params = build_selection_where([], None, None)
        assert sql == ""
        assert params == []

    def test_single_element_list(self):
        selections = [
            {
                "type": "category",
                "column_dim": "portfolio",
                "column_value": "portfolio_a",
                "group_key": "__flat__",
            }
        ]
        sql, params = build_selection_where(selections, None, "portfolio")
        assert '"portfolio" = ?' in sql
        assert params == ["portfolio_a"]
        # Single selection should not have OR
        assert "OR" not in sql

    def test_multi_select_two_categories(self):
        selections = [
            {
                "type": "category",
                "column_dim": "portfolio",
                "column_value": "portfolio_a",
                "group_key": "__flat__",
            },
            {
                "type": "category",
                "column_dim": "portfolio",
                "column_value": "portfolio_b",
                "group_key": "__flat__",
            },
        ]
        sql, params = build_selection_where(selections, None, "portfolio")
        assert "OR" in sql
        assert params == ["portfolio_a", "portfolio_b"]

    def test_multi_select_mixed_types(self):
        selections = [
            {
                "type": "category",
                "column_dim": "portfolio",
                "column_value": "portfolio_a",
                "group_key": "__flat__",
            },
            {
                "type": "group",
                "group_key": "layer=structural",
            },
        ]
        sql, params = build_selection_where(selections, None, "portfolio")
        assert "OR" in sql
        assert "portfolio_a" in params
        assert "structural" in params

    def test_multi_select_skips_invalid(self):
        selections = [
            {
                "type": "category",
                "column_dim": "portfolio",
                "column_value": "portfolio_a",
                "group_key": "__flat__",
            },
            {},  # invalid, should be skipped
        ]
        sql, params = build_selection_where(selections, None, "portfolio")
        assert '"portfolio" = ?' in sql
        assert params == ["portfolio_a"]
        # Only one valid selection, no OR
        assert "OR" not in sql


class TestAppendWhere:
    """Tests for append_where() -- WHERE clause composition."""

    def test_appends_to_existing_where(self):
        sql, params = append_where("WHERE a = ?", ["x"], "b = ?", ["y"])
        assert sql == "WHERE a = ? AND b = ?"
        assert params == ["x", "y"]

    def test_creates_where_from_empty(self):
        sql, params = append_where("", [], "a = ?", ["x"])
        assert sql == "WHERE a = ?"
        assert params == ["x"]

    def test_noop_when_extra_empty(self):
        sql, params = append_where("WHERE a = ?", ["x"], "", [])
        assert sql == "WHERE a = ?"
        assert params == ["x"]

    def test_noop_when_both_empty(self):
        sql, params = append_where("", [], "", [])
        assert sql == ""
        assert params == []


class TestValidateSqlDimensions:
    """Tests for validate_sql_dimensions() -- SQL injection prevention."""

    def test_valid_hierarchy(self):
        validate_sql_dimensions(["portfolio", "layer"], "end_date")

    def test_valid_empty_hierarchy(self):
        validate_sql_dimensions([], "end_date")

    def test_valid_none_hierarchy(self):
        validate_sql_dimensions(None, "portfolio")

    def test_invalid_hierarchy_dimension(self):
        with pytest.raises(ValueError, match="Invalid hierarchy dimension"):
            validate_sql_dimensions(["portfolio", "'; DROP TABLE breaches; --"], "end_date")

    def test_hierarchy_with_double_quote(self):
        with pytest.raises(ValueError, match="Invalid hierarchy dimension"):
            validate_sql_dimensions(['" FROM breaches; --'], "end_date")

    def test_invalid_column_axis(self):
        with pytest.raises(ValueError, match="Invalid column axis"):
            validate_sql_dimensions([], "'; DROP TABLE breaches; --")

    def test_column_axis_with_double_quote(self):
        with pytest.raises(ValueError, match="Invalid column axis"):
            validate_sql_dimensions([], '" FROM breaches; --')

    def test_all_groupable_dimensions_valid(self):
        for dim in GROUPABLE_DIMENSIONS:
            validate_sql_dimensions([dim], "end_date")

    def test_all_column_axis_dimensions_valid(self):
        for dim in COLUMN_AXIS_DIMENSIONS:
            validate_sql_dimensions([], dim)


class TestBuildSelectionWhereSecurity:
    """Tests for SQL injection prevention in build_selection_where()."""

    def test_invalid_col_dim_returns_empty(self):
        selection = {
            "type": "category",
            "column_dim": '"; DROP TABLE breaches; --',
            "column_value": "x",
            "group_key": "__flat__",
        }
        sql, params = build_selection_where(selection, None, "portfolio")
        assert sql == ""
        assert params == []

    def test_invalid_group_key_dim_skipped(self):
        selection = {
            "type": "category",
            "column_dim": "portfolio",
            "column_value": "portfolio_a",
            "group_key": '"; DROP TABLE breaches; --=value',
        }
        sql, params = build_selection_where(selection, None, "portfolio")
        # The invalid dim from group_key should be skipped
        assert '"portfolio" = ?' in sql
        assert "DROP" not in sql
        assert params == ["portfolio_a"]

    def test_valid_group_key_dim_accepted(self):
        selection = {
            "type": "category",
            "column_dim": "portfolio",
            "column_value": "portfolio_a",
            "group_key": "layer=structural|window=daily",
        }
        sql, params = build_selection_where(selection, None, "portfolio")
        assert '"layer" = ?' in sql
        assert '"window" = ?' in sql
        assert "structural" in params
        assert "daily" in params


class TestBuildSelectedCellsSet:
    """Tests for _build_selected_cells_set() -- visual highlighting."""

    def test_none_returns_none(self):
        assert _build_selected_cells_set(None) is None

    def test_empty_list_returns_none(self):
        assert _build_selected_cells_set([]) is None

    def test_single_category_selection(self):
        selections = [
            {
                "type": "category",
                "column_dim": "portfolio",
                "column_value": "portfolio_a",
                "group_key": "__flat__",
            }
        ]
        result = _build_selected_cells_set(selections)
        assert result == {("portfolio_a", "__flat__")}

    def test_multiple_category_selections(self):
        selections = [
            {"type": "category", "column_dim": "portfolio",
             "column_value": "portfolio_a", "group_key": "layer=structural"},
            {"type": "category", "column_dim": "portfolio",
             "column_value": "portfolio_b", "group_key": "layer=structural"},
        ]
        result = _build_selected_cells_set(selections)
        assert result == {
            ("portfolio_a", "layer=structural"),
            ("portfolio_b", "layer=structural"),
        }

    def test_non_category_selections_ignored(self):
        selections = [
            {"type": "timeline", "time_bucket": "2024-01-01", "direction": "lower"},
        ]
        assert _build_selected_cells_set(selections) is None

    def test_mixed_types_only_categories(self):
        selections = [
            {"type": "timeline", "time_bucket": "2024-01-01", "direction": "lower"},
            {"type": "category", "column_dim": "portfolio",
             "column_value": "portfolio_a", "group_key": "__flat__"},
        ]
        result = _build_selected_cells_set(selections)
        assert result == {("portfolio_a", "__flat__")}


class TestBuildBrushWhere:
    """Tests for build_brush_where() -- brush time range filtering."""

    def test_none_returns_empty(self):
        sql, params = build_brush_where(None)
        assert sql == ""
        assert params == []

    def test_empty_dict_returns_empty(self):
        sql, params = build_brush_where({})
        assert sql == ""
        assert params == []

    def test_missing_start_returns_empty(self):
        sql, params = build_brush_where({"end": "2024-01-31"})
        assert sql == ""
        assert params == []

    def test_missing_end_returns_empty(self):
        sql, params = build_brush_where({"start": "2024-01-01"})
        assert sql == ""
        assert params == []

    def test_valid_range(self):
        sql, params = build_brush_where({"start": "2024-01-01", "end": "2024-01-31"})
        assert "end_date >= ?" in sql
        assert "end_date <= ?" in sql
        assert params == ["2024-01-01", "2024-01-31"]


class TestBrushWhereIntegration:
    """Integration tests: brush range filtering with DuckDB."""

    def test_brush_filters_by_date(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        brush_sql, brush_params = build_brush_where(
            {"start": "2024-01-03", "end": "2024-01-04"}
        )
        where_sql = "WHERE " + brush_sql
        count = conn.execute(
            f"SELECT COUNT(*) FROM breaches {where_sql}", brush_params
        ).fetchone()[0]
        # Jan 3: 2 breaches, Jan 4: 1 breach = 3
        assert count == 3

    def test_brush_combined_with_filters(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        where_sql, params = build_where_clause(
            ["portfolio_a"], None, None, None, None, None, None, None, None
        )
        brush_sql, brush_params = build_brush_where(
            {"start": "2024-01-03", "end": "2024-01-03"}
        )
        where_sql, params = append_where(where_sql, params, brush_sql, brush_params)
        count = conn.execute(
            f"SELECT COUNT(*) FROM breaches {where_sql}", params
        ).fetchone()[0]
        # Jan 3 portfolio_a: 2 breaches
        assert count == 2


class TestExtractBrushRange:
    """Tests for _extract_brush_range() -- Plotly relayoutData parsing."""

    def test_zoom_range(self):
        result = _extract_brush_range({
            "xaxis.range[0]": "2024-01-01",
            "xaxis.range[1]": "2024-01-31",
        })
        assert result == {"start": "2024-01-01", "end": "2024-01-31"}

    def test_zoom_range_with_time(self):
        result = _extract_brush_range({
            "xaxis.range[0]": "2024-01-01 12:30:00",
            "xaxis.range[1]": "2024-01-31 23:59:59",
        })
        assert result == {"start": "2024-01-01", "end": "2024-01-31"}

    def test_autorange_clears(self):
        result = _extract_brush_range({"xaxis.autorange": True})
        assert result is None

    def test_irrelevant_event_no_update(self):
        from dash import no_update
        result = _extract_brush_range({"legend.click": True})
        assert result is no_update

    def test_empty_dict_no_update(self):
        from dash import no_update
        result = _extract_brush_range({})
        assert result is no_update


class TestCallbacksIntegration:
    """Test callbacks using the Dash test client."""

    def test_app_creates_with_layout(self, sample_output):
        from monitor.dashboard.app import create_app

        app = create_app(sample_output)
        # Layout should contain the filter dropdowns
        layout_str = str(app.layout)
        assert "filter-portfolio" in layout_str
        assert "filter-layer" in layout_str
        assert "detail-table" in layout_str
        assert "pivot-chart-container" in layout_str

    def test_app_has_hierarchy_controls(self, sample_output):
        from monitor.dashboard.app import create_app

        app = create_app(sample_output)
        layout_str = str(app.layout)
        assert "hierarchy-store" in layout_str
        assert "hierarchy-add-btn" in layout_str
        assert "hierarchy-level-0" in layout_str

    def test_app_has_column_axis_and_selection_store(self, sample_output):
        from monitor.dashboard.app import create_app

        app = create_app(sample_output)
        layout_str = str(app.layout)
        assert "column-axis" in layout_str
        assert "pivot-selection-store" in layout_str

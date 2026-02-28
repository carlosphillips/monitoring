"""Tests for pivot rendering: timeline, category, hierarchical grouping."""

from __future__ import annotations

from dash import html

from monitor.dashboard.pivot import (
    _aggregate_category_cells,
    _build_split_cell,
    _build_tree,
    _format_group_value,
    granularity_to_trunc,
    _render_category_html_table,
    _render_tree,
    auto_granularity,
    build_category_table,
    build_hierarchical_pivot,
    build_timeline_figure,
)


class TestAutoGranularity:
    """Tests for auto_granularity()."""

    def test_short_range_daily(self):
        # 30 days < 90 threshold -> Daily
        assert auto_granularity("2024-01-01", "2024-01-31") == "Daily"

    def test_medium_range_weekly(self):
        # ~180 days, between 90 and 365 -> Weekly
        assert auto_granularity("2024-01-01", "2024-06-30") == "Weekly"

    def test_long_range_monthly(self):
        # > 365 days -> Monthly
        assert auto_granularity("2024-01-01", "2025-06-30") == "Monthly"

    def test_exactly_90_days_weekly(self):
        # 90 days is >= threshold so should be Weekly
        assert auto_granularity("2024-01-01", "2024-03-31") == "Weekly"

    def test_single_day_daily(self):
        assert auto_granularity("2024-01-01", "2024-01-01") == "Daily"

    def test_exactly_365_days_monthly(self):
        # 365 days >= threshold -> Monthly
        assert auto_granularity("2024-01-01", "2024-12-31") == "Monthly"


class TestGranularityToTrunc:
    """Tests for granularity_to_trunc()."""

    def test_daily(self):
        assert granularity_to_trunc("Daily") == "day"

    def test_weekly(self):
        assert granularity_to_trunc("Weekly") == "week"

    def test_monthly(self):
        assert granularity_to_trunc("Monthly") == "month"

    def test_quarterly(self):
        assert granularity_to_trunc("Quarterly") == "quarter"

    def test_yearly(self):
        assert granularity_to_trunc("Yearly") == "year"

    def test_unknown_defaults_to_month(self):
        assert granularity_to_trunc("Invalid") == "month"


class TestBuildTimelineFigure:
    """Tests for build_timeline_figure()."""

    def test_empty_data(self):
        fig = build_timeline_figure([], "Monthly")
        # Should have 2 traces (lower and upper), both empty
        assert len(fig.data) == 2
        assert fig.data[0].name == "Lower"
        assert fig.data[1].name == "Upper"
        assert len(fig.data[0].x) == 0
        assert len(fig.data[1].x) == 0

    def test_lower_only(self):
        data = [
            {"time_bucket": "2024-01-01", "direction": "lower", "count": 3},
            {"time_bucket": "2024-01-02", "direction": "lower", "count": 1},
        ]
        fig = build_timeline_figure(data, "Daily")
        # Lower trace should have data, upper should be zeros
        assert list(fig.data[0].y) == [3, 1]  # lower
        assert list(fig.data[1].y) == [0, 0]  # upper

    def test_upper_only(self):
        data = [
            {"time_bucket": "2024-01-01", "direction": "upper", "count": 2},
        ]
        fig = build_timeline_figure(data, "Daily")
        assert list(fig.data[0].y) == [0]  # lower
        assert list(fig.data[1].y) == [2]  # upper

    def test_mixed_directions(self):
        data = [
            {"time_bucket": "2024-01-01", "direction": "lower", "count": 3},
            {"time_bucket": "2024-01-01", "direction": "upper", "count": 2},
            {"time_bucket": "2024-01-02", "direction": "lower", "count": 1},
        ]
        fig = build_timeline_figure(data, "Daily")
        assert list(fig.data[0].x) == ["2024-01-01", "2024-01-02"]
        assert list(fig.data[0].y) == [3, 1]  # lower
        assert list(fig.data[1].y) == [2, 0]  # upper

    def test_stacked_bar_mode(self):
        data = [
            {"time_bucket": "2024-01-01", "direction": "lower", "count": 1},
            {"time_bucket": "2024-01-01", "direction": "upper", "count": 1},
        ]
        fig = build_timeline_figure(data, "Daily")
        assert fig.layout.barmode == "stack"

    def test_color_scheme(self):
        data = [
            {"time_bucket": "2024-01-01", "direction": "lower", "count": 1},
            {"time_bucket": "2024-01-01", "direction": "upper", "count": 1},
        ]
        fig = build_timeline_figure(data, "Daily")
        assert fig.data[0].marker.color == "#d62728"  # lower = red
        assert fig.data[1].marker.color == "#1f77b4"  # upper = blue

    def test_buckets_sorted(self):
        data = [
            {"time_bucket": "2024-01-03", "direction": "lower", "count": 1},
            {"time_bucket": "2024-01-01", "direction": "lower", "count": 2},
            {"time_bucket": "2024-01-02", "direction": "upper", "count": 3},
        ]
        fig = build_timeline_figure(data, "Daily")
        assert list(fig.data[0].x) == ["2024-01-01", "2024-01-02", "2024-01-03"]


class TestTimelineBucketing:
    """Integration tests: verify DuckDB bucketing produces correct data for the chart."""

    def test_daily_bucketing(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        result = conn.execute("""
            SELECT
                DATE_TRUNC('day', end_date::DATE) AS time_bucket,
                direction,
                COUNT(*) AS count
            FROM breaches
            GROUP BY time_bucket, direction
            ORDER BY time_bucket
        """).fetchdf()

        assert len(result) > 0
        # Verify structure
        assert "time_bucket" in result.columns
        assert "direction" in result.columns
        assert "count" in result.columns

    def test_weekly_bucketing(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        result = conn.execute("""
            SELECT
                DATE_TRUNC('week', end_date::DATE) AS time_bucket,
                direction,
                COUNT(*) AS count
            FROM breaches
            GROUP BY time_bucket, direction
            ORDER BY time_bucket
        """).fetchdf()

        assert len(result) > 0
        # All dates are in the same week (Jan 2-5, 2024), so should have 1 bucket
        unique_buckets = result["time_bucket"].nunique()
        assert unique_buckets == 1

    def test_monthly_bucketing(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        result = conn.execute("""
            SELECT
                DATE_TRUNC('month', end_date::DATE) AS time_bucket,
                direction,
                COUNT(*) AS count
            FROM breaches
            GROUP BY time_bucket, direction
            ORDER BY time_bucket
        """).fetchdf()

        # All in January 2024
        assert result["time_bucket"].nunique() == 1


class TestFormatGroupValue:
    """Tests for _format_group_value()."""

    def test_normal_value(self):
        assert _format_group_value("portfolio", "portfolio_a") == "portfolio_a"

    def test_factor_empty_string(self):
        assert _format_group_value("factor", "") == "(no factor)"

    def test_factor_none_like(self):
        assert _format_group_value("factor", "") == "(no factor)"

    def test_factor_real_value(self):
        assert _format_group_value("factor", "market") == "market"

    def test_non_factor_dimension(self):
        assert _format_group_value("layer", "structural") == "structural"


class TestBuildTree:
    """Tests for _build_tree()."""

    def test_single_level(self):
        rows = [
            {"portfolio": "a", "time_bucket": "2024-01", "direction": "lower", "count": 3},
            {"portfolio": "a", "time_bucket": "2024-01", "direction": "upper", "count": 2},
            {"portfolio": "b", "time_bucket": "2024-01", "direction": "lower", "count": 1},
        ]
        tree = _build_tree(rows, ["portfolio"], level=0)

        assert "a" in tree
        assert "b" in tree
        assert tree["a"]["count"] == 5
        assert tree["b"]["count"] == 1
        assert len(tree["a"]["leaf_data"]) == 2
        assert len(tree["b"]["leaf_data"]) == 1

    def test_two_levels(self):
        rows = [
            {
                "portfolio": "a",
                "layer": "structural",
                "time_bucket": "2024-01",
                "direction": "lower",
                "count": 3,
            },
            {
                "portfolio": "a",
                "layer": "tactical",
                "time_bucket": "2024-01",
                "direction": "upper",
                "count": 2,
            },
            {
                "portfolio": "b",
                "layer": "structural",
                "time_bucket": "2024-01",
                "direction": "lower",
                "count": 1,
            },
        ]
        tree = _build_tree(rows, ["portfolio", "layer"], level=0)

        assert "a" in tree
        assert "b" in tree
        assert tree["a"]["count"] == 5
        assert "children" in tree["a"]
        assert "structural" in tree["a"]["children"]
        assert "tactical" in tree["a"]["children"]
        assert tree["a"]["children"]["structural"]["count"] == 3
        assert tree["a"]["children"]["tactical"]["count"] == 2

    def test_three_levels(self):
        rows = [
            {
                "portfolio": "a",
                "layer": "structural",
                "factor": "market",
                "time_bucket": "2024-01",
                "direction": "lower",
                "count": 3,
            },
            {
                "portfolio": "a",
                "layer": "structural",
                "factor": "HML",
                "time_bucket": "2024-01",
                "direction": "upper",
                "count": 1,
            },
        ]
        tree = _build_tree(rows, ["portfolio", "layer", "factor"], level=0)

        assert "a" in tree
        structural = tree["a"]["children"]["structural"]
        assert "children" in structural
        assert "market" in structural["children"]
        assert "HML" in structural["children"]
        assert structural["children"]["market"]["count"] == 3
        # Leaf level should have leaf_data
        assert "leaf_data" in structural["children"]["market"]


class TestBuildHierarchicalPivot:
    """Tests for build_hierarchical_pivot()."""

    def test_empty_data(self):
        result = build_hierarchical_pivot([], ["portfolio"], "Daily")
        assert result == []

    def test_empty_hierarchy(self):
        data = [
            {"portfolio": "a", "time_bucket": "2024-01", "direction": "lower", "count": 1},
        ]
        result = build_hierarchical_pivot(data, [], "Daily")
        assert result == []

    def test_single_level_returns_details_elements(self):
        data = [
            {"portfolio": "a", "time_bucket": "2024-01", "direction": "lower", "count": 3},
            {"portfolio": "a", "time_bucket": "2024-01", "direction": "upper", "count": 2},
            {"portfolio": "b", "time_bucket": "2024-01", "direction": "lower", "count": 1},
        ]
        result = build_hierarchical_pivot(data, ["portfolio"], "Daily")

        # Should return html.Details elements, one per group
        assert len(result) == 2
        for item in result:
            assert isinstance(item, html.Details)
            # Collapsed by default
            assert item.open is False

    def test_single_level_contains_summary_and_chart(self):
        data = [
            {"portfolio": "a", "time_bucket": "2024-01", "direction": "lower", "count": 5},
        ]
        result = build_hierarchical_pivot(data, ["portfolio"], "Daily")

        details = result[0]
        # First child should be Summary
        assert isinstance(details.children[0], html.Summary)
        # Summary should contain dimension label and count
        summary_children = details.children[0].children
        assert "Portfolio" in summary_children[0].children
        assert "5 breaches" in summary_children[1].children

    def test_two_level_nesting(self):
        data = [
            {
                "portfolio": "a",
                "layer": "structural",
                "time_bucket": "2024-01",
                "direction": "lower",
                "count": 3,
            },
            {
                "portfolio": "a",
                "layer": "tactical",
                "time_bucket": "2024-01",
                "direction": "upper",
                "count": 2,
            },
        ]
        result = build_hierarchical_pivot(data, ["portfolio", "layer"], "Daily")

        # Top level: 1 group (portfolio_a)
        assert len(result) == 1
        top_details = result[0]
        assert isinstance(top_details, html.Details)

        # Children div should contain nested Details for each layer
        children_div = top_details.children[1]
        nested_items = children_div.children
        assert len(nested_items) == 2  # structural, tactical
        for item in nested_items:
            assert isinstance(item, html.Details)

    def test_three_level_nesting(self):
        data = [
            {
                "portfolio": "a",
                "layer": "structural",
                "factor": "market",
                "time_bucket": "2024-01",
                "direction": "lower",
                "count": 3,
            },
            {
                "portfolio": "a",
                "layer": "structural",
                "factor": "HML",
                "time_bucket": "2024-01",
                "direction": "upper",
                "count": 1,
            },
            {
                "portfolio": "a",
                "layer": "tactical",
                "factor": "momentum",
                "time_bucket": "2024-01",
                "direction": "lower",
                "count": 2,
            },
        ]
        result = build_hierarchical_pivot(data, ["portfolio", "layer", "factor"], "Daily")

        # Top level: 1 group (portfolio_a)
        assert len(result) == 1
        # Second level: 2 groups (structural, tactical)
        level2 = result[0].children[1].children
        assert len(level2) == 2
        # Third level under structural: 2 groups (HML, market)
        level3 = level2[0].children[1].children
        assert len(level3) == 2

    def test_singular_breach_label(self):
        data = [
            {"portfolio": "a", "time_bucket": "2024-01", "direction": "lower", "count": 1},
        ]
        result = build_hierarchical_pivot(data, ["portfolio"], "Daily")
        summary_children = result[0].children[0].children
        assert "1 breach)" in summary_children[1].children


class TestHierarchicalPivotIntegration:
    """Integration tests: hierarchical pivot with real DuckDB data."""

    def test_group_by_portfolio(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        result = conn.execute("""
            SELECT
                portfolio,
                DATE_TRUNC('day', end_date::DATE) AS time_bucket,
                direction,
                COUNT(*) AS count
            FROM breaches
            GROUP BY portfolio, time_bucket, direction
            ORDER BY portfolio, time_bucket
        """).fetchdf()

        grouped_data = result.to_dict("records")
        components = build_hierarchical_pivot(grouped_data, ["portfolio"], "Daily")

        # Should have 2 groups: portfolio_a and portfolio_b
        assert len(components) == 2

    def test_group_by_portfolio_and_layer(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        result = conn.execute("""
            SELECT
                portfolio, layer,
                DATE_TRUNC('day', end_date::DATE) AS time_bucket,
                direction,
                COUNT(*) AS count
            FROM breaches
            GROUP BY portfolio, layer, time_bucket, direction
            ORDER BY portfolio, layer, time_bucket
        """).fetchdf()

        grouped_data = result.to_dict("records")
        components = build_hierarchical_pivot(grouped_data, ["portfolio", "layer"], "Daily")

        # Should have 2 top-level groups
        assert len(components) == 2


# --- Category Mode Tests ---


class TestBuildSplitCell:
    """Tests for _build_split_cell()."""

    def test_both_counts(self):
        cell = _build_split_cell(3, 2, 0.5)
        assert isinstance(cell, html.Div)
        children = cell.children
        assert len(children) == 2
        # Upper (blue) section
        assert children[0].children == "3"
        # Lower (red) section
        assert children[1].children == "2"

    def test_zero_upper(self):
        cell = _build_split_cell(0, 5, 0.5)
        assert cell.children[0].children == ""  # empty string for zero
        assert cell.children[1].children == "5"

    def test_zero_lower(self):
        cell = _build_split_cell(4, 0, 0.5)
        assert cell.children[0].children == "4"
        assert cell.children[1].children == ""

    def test_both_zero(self):
        cell = _build_split_cell(0, 0, 0.0)
        assert cell.children[0].children == ""
        assert cell.children[1].children == ""


class TestAggregateCategoryCells:
    """Tests for _aggregate_category_cells()."""

    def test_basic_aggregation(self):
        rows = [
            {"portfolio": "a", "direction": "upper", "count": 3},
            {"portfolio": "a", "direction": "lower", "count": 2},
            {"portfolio": "b", "direction": "upper", "count": 1},
        ]
        cells = _aggregate_category_cells(rows, "portfolio", ["a", "b"])
        assert cells["a"]["upper"] == 3
        assert cells["a"]["lower"] == 2
        assert cells["b"]["upper"] == 1
        assert cells["b"]["lower"] == 0

    def test_missing_col_value(self):
        rows = [
            {"portfolio": "a", "direction": "upper", "count": 1},
        ]
        cells = _aggregate_category_cells(rows, "portfolio", ["a", "b"])
        assert cells["b"]["upper"] == 0
        assert cells["b"]["lower"] == 0


class TestRenderCategoryHtmlTable:
    """Tests for _render_category_html_table()."""

    def test_basic_table_structure(self):
        cells = {
            "a": {"upper": 3, "lower": 2},
            "b": {"upper": 1, "lower": 0},
        }
        table = _render_category_html_table(cells, "portfolio", ["a", "b"])
        assert isinstance(table, html.Table)
        # Has thead and tbody
        assert isinstance(table.children[0], html.Thead)
        assert isinstance(table.children[1], html.Tbody)

    def test_header_contains_column_values(self):
        cells = {"structural": {"upper": 1, "lower": 0}}
        table = _render_category_html_table(cells, "layer", ["structural"])
        header_row = table.children[0].children  # Thead -> Tr
        # First header cell is empty, second is "structural"
        assert header_row.children[1].children == "structural"

    def test_cells_have_pattern_matching_ids(self):
        cells = {"a": {"upper": 1, "lower": 0}}
        table = _render_category_html_table(cells, "portfolio", ["a"])
        data_row = table.children[1].children  # Tbody -> Tr
        # Second cell (after label) should have cat-cell id
        cell = data_row.children[1]
        assert cell.id["type"] == "cat-cell"
        assert cell.id["col"] == "a"

    def test_cells_have_n_clicks(self):
        cells = {"a": {"upper": 1, "lower": 0}}
        table = _render_category_html_table(cells, "portfolio", ["a"])
        data_row = table.children[1].children
        cell = data_row.children[1]
        assert cell.n_clicks == 0


class TestBuildCategoryTable:
    """Tests for build_category_table()."""

    def test_empty_data(self):
        assert build_category_table([], "portfolio") == []

    def test_flat_category(self):
        data = [
            {"portfolio": "a", "direction": "upper", "count": 3},
            {"portfolio": "a", "direction": "lower", "count": 2},
            {"portfolio": "b", "direction": "lower", "count": 1},
        ]
        result = build_category_table(data, "portfolio")
        assert len(result) == 1  # single table
        assert isinstance(result[0], html.Table)

    def test_hierarchical_category(self):
        data = [
            {"layer": "structural", "portfolio": "a", "direction": "upper", "count": 3},
            {"layer": "structural", "portfolio": "b", "direction": "lower", "count": 2},
            {"layer": "tactical", "portfolio": "a", "direction": "lower", "count": 1},
        ]
        result = build_category_table(data, "portfolio", hierarchy=["layer"])
        # Should have Details elements for each layer group
        assert len(result) == 2
        for item in result:
            assert isinstance(item, html.Details)

    def test_two_level_hierarchical_category(self):
        data = [
            {
                "layer": "structural",
                "window": "daily",
                "portfolio": "a",
                "direction": "upper",
                "count": 3,
            },
            {
                "layer": "structural",
                "window": "monthly",
                "portfolio": "b",
                "direction": "lower",
                "count": 1,
            },
        ]
        result = build_category_table(data, "portfolio", hierarchy=["layer", "window"])
        # Top level: 1 group (structural)
        assert len(result) == 1
        # Nested: 2 window groups
        nested = result[0].children[1].children
        assert len(nested) == 2


class TestBuildCategoryTree:
    """Tests for _build_tree() in category mode."""

    def test_single_level(self):
        rows = [
            {"layer": "structural", "portfolio": "a", "direction": "upper", "count": 3},
            {"layer": "tactical", "portfolio": "a", "direction": "lower", "count": 1},
        ]
        tree = _build_tree(rows, ["layer"], level=0)
        assert "structural" in tree
        assert "tactical" in tree
        assert tree["structural"]["count"] == 3
        assert tree["tactical"]["count"] == 1
        # Leaf level should have leaf_data
        assert "leaf_data" in tree["structural"]


class TestCategoryIntegration:
    """Integration tests: category mode with real DuckDB data."""

    def test_category_by_portfolio(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        result = conn.execute("""
            SELECT portfolio, direction, COUNT(*) AS count
            FROM breaches
            GROUP BY portfolio, direction
            ORDER BY portfolio
        """).fetchdf()

        components = build_category_table(result.to_dict("records"), "portfolio")
        assert len(components) == 1  # single flat table

    def test_category_by_layer_with_portfolio_hierarchy(self, sample_output):
        from monitor.dashboard.data import load_breaches

        conn = load_breaches(sample_output)
        result = conn.execute("""
            SELECT portfolio, layer, direction, COUNT(*) AS count
            FROM breaches
            GROUP BY portfolio, layer, direction
            ORDER BY portfolio, layer
        """).fetchdf()

        components = build_category_table(
            result.to_dict("records"), "layer", hierarchy=["portfolio"]
        )
        # 2 portfolio groups
        assert len(components) == 2

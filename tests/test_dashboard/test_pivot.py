"""Tests for pivot rendering: timeline chart, time bucketing."""

from __future__ import annotations

from monitor.dashboard.pivot import (
    _granularity_to_trunc,
    auto_granularity,
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
    """Tests for _granularity_to_trunc()."""

    def test_daily(self):
        assert _granularity_to_trunc("Daily") == "day"

    def test_weekly(self):
        assert _granularity_to_trunc("Weekly") == "week"

    def test_monthly(self):
        assert _granularity_to_trunc("Monthly") == "month"

    def test_quarterly(self):
        assert _granularity_to_trunc("Quarterly") == "quarter"

    def test_yearly(self):
        assert _granularity_to_trunc("Yearly") == "year"

    def test_unknown_defaults_to_month(self):
        assert _granularity_to_trunc("Invalid") == "month"


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
        assert list(fig.data[0].y) == [0]   # lower
        assert list(fig.data[1].y) == [2]   # upper

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

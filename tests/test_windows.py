"""Tests for trailing window slicing."""

import pandas as pd
import pytest
from dateutil.relativedelta import relativedelta

from monitor.windows import WINDOWS, WindowDef, slice_window


@pytest.fixture
def trading_dates():
    """A year of business days."""
    return pd.DatetimeIndex(pd.bdate_range("2024-01-02", "2024-12-31"))


class TestSliceWindow:
    def test_daily_window(self, trading_dates):
        end_date = pd.Timestamp("2024-06-14")  # Friday
        daily = WindowDef("daily", relativedelta())
        ws = slice_window(trading_dates, end_date, daily, trading_dates[0])
        assert ws is not None
        assert ws.name == "daily"
        dates_in_window = trading_dates[ws.mask]
        assert len(dates_in_window) == 1
        assert dates_in_window[0] == end_date

    def test_monthly_window(self, trading_dates):
        end_date = pd.Timestamp("2024-06-14")
        monthly = WindowDef("monthly", relativedelta(months=1))
        ws = slice_window(trading_dates, end_date, monthly, trading_dates[0])
        assert ws is not None
        # Start = June 14 - 1 month + 1 day = May 15
        dates_in_window = trading_dates[ws.mask]
        assert dates_in_window[0] >= pd.Timestamp("2024-05-15")
        assert dates_in_window[-1] == end_date

    def test_annual_window(self, trading_dates):
        # start = Dec 31 - 1 year + 1 day = Jan 1, but first_date is Jan 2
        # Use Jan 1 2025 which gives start = Jan 2 2024 = first_date
        end_date = pd.Timestamp("2024-12-31")
        annual = WindowDef("annual", relativedelta(years=1))
        # End of Dec 31 means start = Jan 1 which is before first_date Jan 2 -> None
        ws = slice_window(trading_dates, end_date, annual, trading_dates[0])
        assert ws is None  # Off by one day

        # Use a date where the full year fits: end = Dec 30 -> start = Dec 31 2023 + 1 = Jan 1
        # Still before Jan 2. Try end = Jan 1 2025 (not in dates) with first_date = Jan 2 2024:
        # start = Jan 2 2024 = first_date -> should work. But Jan 1 2025 not in trading_dates.
        # Use extended dates for this test:
        extended = pd.DatetimeIndex(pd.bdate_range("2024-01-02", "2025-01-02"))
        end_date2 = pd.Timestamp("2025-01-02")
        ws2 = slice_window(extended, end_date2, annual, extended[0])
        assert ws2 is not None
        dates_in_window = extended[ws2.mask]
        assert len(dates_in_window) > 200  # ~250 trading days in a year

    def test_insufficient_history_returns_none(self, trading_dates):
        end_date = pd.Timestamp("2024-03-01")
        three_year = WindowDef("3-year", relativedelta(years=3))
        ws = slice_window(trading_dates, end_date, three_year, trading_dates[0])
        assert ws is None  # Data starts in Jan 2024, need 3 years back

    def test_first_day_daily_works(self, trading_dates):
        daily = WindowDef("daily", relativedelta())
        ws = slice_window(trading_dates, trading_dates[0], daily, trading_dates[0])
        assert ws is not None
        assert trading_dates[ws.mask][0] == trading_dates[0]

    def test_window_definitions_exist(self):
        names = [w.name for w in WINDOWS]
        assert names == ["daily", "monthly", "quarterly", "annual", "3-year"]

    def test_quarterly_window_span(self, trading_dates):
        end_date = pd.Timestamp("2024-06-14")
        quarterly = WindowDef("quarterly", relativedelta(months=3))
        ws = slice_window(trading_dates, end_date, quarterly, trading_dates[0])
        assert ws is not None
        dates_in_window = trading_dates[ws.mask]
        # Start = June 14 - 3 months + 1 day = March 15
        assert dates_in_window[0] >= pd.Timestamp("2024-03-15")

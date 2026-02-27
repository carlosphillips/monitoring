"""Trailing window slicing over exposure series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
from dateutil.relativedelta import relativedelta


@dataclass
class WindowDef:
    name: str
    delta: relativedelta


# Window definitions: the delta to subtract from end_date to get start_date (before +1 day).
# daily: start = end (delta of 0)
# monthly: start = end - 1 month + 1 day
# etc.
WINDOWS = [
    WindowDef("daily", relativedelta()),
    WindowDef("monthly", relativedelta(months=1)),
    WindowDef("quarterly", relativedelta(months=3)),
    WindowDef("annual", relativedelta(years=1)),
    WindowDef("3-year", relativedelta(years=3)),
]


@dataclass
class WindowSlice:
    """A slice of data for a specific trailing window."""

    name: str
    start_date: date
    end_date: date
    mask: pd.Series  # boolean mask over the full date index


def slice_window(
    dates: pd.DatetimeIndex,
    end_date: pd.Timestamp,
    window_def: WindowDef,
    first_date: pd.Timestamp,
) -> WindowSlice | None:
    """Compute a trailing window slice for a given end_date.

    Returns None if the window requires dates before the first available date.
    For daily window, start_date = end_date (single day).
    For others, start_date = end_date - period + 1 day.
    """
    if window_def.delta == relativedelta():
        # Daily: single day
        start = end_date
    else:
        # start_date = end_date - period + 1 day
        start = end_date - window_def.delta + relativedelta(days=1)

    # Skip if insufficient history
    if start < first_date:
        return None

    mask = (dates >= start) & (dates <= end_date)

    # Must have at least one date in the window
    if not mask.any():
        return None

    return WindowSlice(
        name=window_def.name,
        start_date=start.date() if hasattr(start, "date") else start,
        end_date=end_date.date() if hasattr(end_date, "date") else end_date,
        mask=mask,
    )

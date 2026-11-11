"""Futures curve maths: expiry calendars, roll-adjusted returns and carry.

EIA labels contracts by position (contract 1 = nearest unexpired), not by delivery month. On the
first trading day after an expiry every label shifts: yesterday's contract 2 is today's contract 1.
A return series that ignores this would book the price gap between two different contracts as
profit or loss, so returns are computed contract by contract using the exchange expiry rules.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.tseries.holiday import (AbstractHolidayCalendar, GoodFriday, Holiday, USLaborDay,
                                    USMartinLutherKingJr, USMemorialDay, USPresidentsDay,
                                    USThanksgivingDay, nearest_workday)
from pandas.tseries.offsets import CustomBusinessDay


class NymexCalendar(AbstractHolidayCalendar):
    """Full-day NYMEX closures (no Columbus Day or Veterans Day, unlike the federal calendar)."""
    rules = [
        Holiday("New Year", month=1, day=1, observance=nearest_workday),
        USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay,
        Holiday("Juneteenth", month=6, day=19, start_date="2022-01-01", observance=nearest_workday),
        Holiday("Independence Day", month=7, day=4, observance=nearest_workday),
        USLaborDay, USThanksgivingDay,
        Holiday("Christmas", month=12, day=25, observance=nearest_workday),
    ]


BDAY = CustomBusinessDay(calendar=NymexCalendar())


def expiry(root: str, year: int, month: int) -> pd.Timestamp:
    """Last trading day of the contract delivering in (year, month)."""
    first = pd.Timestamp(year, month, 1)
    if root == "CL":
        # 3 business days before the 25th of the prior month (or before the last business day before it)
        d25 = first - pd.DateOffset(months=1) + pd.DateOffset(days=24)
        anchor = d25 if BDAY.is_on_offset(d25) else d25 - BDAY
        return anchor - 3 * BDAY
    if root == "NG":
        return first - 3 * BDAY                     # 3 business days before the delivery month
    if root in ("RB", "HO"):
        return first - BDAY                         # last business day of the prior month
    raise ValueError(root)


def expiries(root: str, start: str, end: str) -> pd.DatetimeIndex:
    months = pd.period_range(pd.Period(start, "M"), pd.Period(end, "M") + 3, freq="M")
    return pd.DatetimeIndex(sorted(expiry(root, p.year, p.month) for p in months))


def roll_flags(dates: pd.DatetimeIndex, root: str) -> pd.Series:
    """True on the first observation after a contract expired (labels have shifted by one)."""
    exp = expiries(root, str(dates[0].date()), str(dates[-1].date()))
    prev = dates[:-1]
    # a roll happened between prev and today if some expiry e satisfies prev <= e < today
    idx = np.searchsorted(exp.values, prev.values, side="left")
    nxt = exp.values[np.minimum(idx, len(exp) - 1)]
    rolled = (nxt >= prev.values) & (nxt < dates[1:].values)
    return pd.Series(np.r_[False, rolled], index=dates)


def held_returns(prices: pd.DataFrame, root: str, k: int = 2) -> pd.Series:
    """Daily excess return from always holding contract k, rolling at expiry.

    Normal day: C_k(t) / C_k(t-1) - 1.  Roll day: the contract held yesterday as C_k is now C_{k-1}.
    Days where the needed prices are missing are skipped and the return spans the gap.
    """
    cols = [f"{root}{j}" for j in range(1, 5)]
    px = prices[cols].dropna(subset=[f"{root}{k - 1}", f"{root}{k}"] if k > 1 else [f"{root}{k}", f"{root}2"])
    rolled = roll_flags(px.index, root)
    today_same = px[f"{root}{k}"]
    today_shifted = px[f"{root}{k - 1}"] if k > 1 else px[f"{root}1"]
    yesterday = px[f"{root}{k}"].shift(1)
    if k == 1:  # the expired front contract was swapped into contract 2 at its last close
        yesterday = yesterday.where(~rolled, px[f"{root}2"].shift(1))
        today = today_same
    else:
        today = today_shifted.where(rolled, today_same)
    return (today / yesterday - 1).iloc[1:].rename(root)


def carry(prices: pd.DataFrame, root: str, near: int = 2, far: int = 4) -> pd.Series:
    """Annualised roll yield from the slope between two contracts; positive = backwardation.

    Contracts 2 and 4 are used by default: contract 1 is distorted in the days before expiry
    (April 2020 is the extreme case), and the strategy never holds it.
    """
    a, b = prices[f"{root}{near}"], prices[f"{root}{far}"]
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = np.log(a / b)
    return (slope * 12 / (far - near)).where((a > 0) & (b > 0)).rename(root)


def seasonal_adjust(monthly: pd.Series, years: int = 5, min_years: int = 3) -> pd.Series:
    """Carry minus its average in the same calendar month over the previous `years` years.

    Gasoline and natural gas curves have a built-in seasonal shape (summer driving, winter heating),
    so raw carry partly measures the calendar. Only past years are used, so there is no look-ahead.
    """
    out = monthly.copy() * np.nan
    for m in range(1, 13):
        same = monthly[monthly.index.month == m]
        past = same.shift(1).rolling(years, min_periods=min_years).mean()
        out.loc[same.index] = same - past
    return out


def curve_state(c: float, flat: float = 0.02) -> str:
    if np.isnan(c):
        return "n/a"
    return "backwardation" if c > flat else "contango" if c < -flat else "flat"

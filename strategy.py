"""Carry strategies on the energy futures curve, rebalanced monthly on daily data.

All returns are excess returns (futures P&L before interest on collateral). Positions are set at
the last trading day of each month from information available at that close, then left to drift
until the next rebalance.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import curves as cv

ROOTS = ["CL", "RB", "HO", "NG"]


@dataclass(frozen=True)
class Config:
    hold: int = 2            # contract held (2 = second month, never into expiry)
    vol_window: int = 60     # trading days for inverse-volatility sizing
    n_long: int = 2          # names in each leg of the cross-sectional strategy
    cost_bps: float = 5.0    # per unit of notional traded at rebalance
    roll_bps: float = 2.0    # per unit of notional rolled at each expiry


def daily_returns(prices: pd.DataFrame, hold: int) -> pd.DataFrame:
    return pd.DataFrame({r: cv.held_returns(prices, r, hold) for r in ROOTS}).sort_index()


def roll_days(returns: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({r: cv.roll_flags(returns.index, r) for r in ROOTS})


def month_ends(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby(index.to_period("M")).last().to_numpy())


def monthly_carry(prices: pd.DataFrame, dates: pd.DatetimeIndex, seasonal: bool) -> pd.DataFrame:
    """Carry on each rebalance date, from the last available settlement on or before it."""
    raw = pd.DataFrame({r: cv.carry(prices, r) for r in ROOTS}).ffill(limit=3)
    if seasonal:  # adjust on the full month-end history so early dates have past years to compare with
        raw = raw.reindex(month_ends(raw.index)).apply(cv.seasonal_adjust)
    return raw.reindex(dates, method="ffill")


def time_series(signal: pd.DataFrame, iv: pd.DataFrame) -> pd.DataFrame:
    """Long each commodity only while its curve is backwardated (carry > 0); otherwise flat."""
    w = iv.where(signal > 0)
    n = signal.notna().sum(axis=1).replace(0, np.nan)
    sized = iv.where(signal.notna()).div(iv.where(signal.notna()).sum(axis=1), axis=0)
    return sized.where(w.notna()).fillna(0.0).where(n.notna(), 0.0)


def inverse_vol(returns: pd.DataFrame, dates: pd.DatetimeIndex, window: int) -> pd.DataFrame:
    vol = returns.rolling(window, min_periods=window // 2).std() * np.sqrt(252)
    return 1 / vol.reindex(dates)


def long_only(signal: pd.DataFrame, iv: pd.DataFrame) -> pd.DataFrame:
    w = iv.where(signal.notna())
    return w.div(w.sum(axis=1), axis=0).fillna(0.0)


def top_long(signal: pd.DataFrame, iv: pd.DataFrame, n: int) -> pd.DataFrame:
    """Long-only: the n most backwardated commodities, inverse-vol weighted."""
    rank = signal.rank(axis=1, ascending=False)
    w = iv.where(rank <= n)
    return w.div(w.sum(axis=1), axis=0).fillna(0.0)


def long_short(signal: pd.DataFrame, iv: pd.DataFrame, n: int) -> pd.DataFrame:
    """Long the n highest-carry names, short the n lowest; each leg is 50% of capital."""
    hi = signal.rank(axis=1, ascending=False) <= n
    lo = signal.rank(axis=1, ascending=True) <= n
    longs, shorts = iv.where(hi), iv.where(lo)
    w = longs.div(longs.sum(axis=1), axis=0).fillna(0) * 0.5 - shorts.div(shorts.sum(axis=1), axis=0).fillna(0) * 0.5
    return w.where(signal.notna().sum(axis=1) >= 2 * n, 0.0)


def simulate(weights: pd.DataFrame, returns: pd.DataFrame, rolls: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Daily NAV returns with positions set at each month-end and drifting in between."""
    r = returns.fillna(0.0)
    starts = weights.index
    out, prev_end = [], None
    for i, d in enumerate(starts[:-1]):
        w = weights.loc[d]
        block = r.loc[(r.index > d) & (r.index <= starts[i + 1])]
        if block.empty:
            continue
        growth = (1 + block).cumprod()
        pos = growth * w                                   # notional of each position, in start-of-month NAV
        nav = 1 + (pos - w).sum(axis=1)
        daily = nav / nav.shift(1, fill_value=1.0) - 1
        traded = (w - prev_end).abs().sum() if prev_end is not None else w.abs().sum()
        roll_cost = (rolls.loc[block.index] * pos.abs().shift(1, fill_value=0) * w.abs().gt(0)).sum(axis=1)
        daily.iloc[0] -= traded * cfg.cost_bps / 1e4
        daily -= roll_cost * cfg.roll_bps / 1e4
        prev_end = (pos.iloc[-1] / nav.iloc[-1]).fillna(0.0)
        out.append(pd.DataFrame({"ret": daily, "turnover": 0.0}))
        out[-1].iloc[0, 1] = traded
    return pd.concat(out)


# --- statistics ------------------------------------------------------------
def drawdown(r: pd.Series) -> pd.Series:
    wealth = (1 + r).cumprod()
    return wealth / wealth.cummax().clip(lower=1.0) - 1


def newey_west_t(x: np.ndarray, lags: int = 3) -> float:
    """t-stat of the mean of x with Newey-West standard errors."""
    u = x - x.mean()
    s = (u @ u) / len(x)
    for k in range(1, lags + 1):
        s += 2 * (1 - k / (lags + 1)) * (u[k:] @ u[:-k]) / len(x)
    return float(x.mean() / np.sqrt(s / len(x)))


def stats(daily: pd.Series, turnover: pd.Series | None = None) -> dict:
    monthly = (1 + daily).groupby(daily.index.to_period("M")).prod() - 1
    years = len(daily) / 252
    dd = drawdown(daily)
    trough = dd.idxmin()
    peak = (1 + daily).cumprod().loc[:trough].idxmax()
    cagr = (1 + daily).prod() ** (1 / years) - 1
    out = {
        "cagr": cagr,
        "vol": daily.std() * np.sqrt(252),
        "sharpe": daily.mean() / daily.std() * np.sqrt(252),
        "t_stat": newey_west_t(monthly.to_numpy()),
        "max_dd": dd.min(),
        "max_dd_peak": str(peak.date()),
        "max_dd_trough": str(trough.date()),
        "calmar": cagr / abs(dd.min()) if dd.min() < 0 else np.nan,
        "worst_month": monthly.min(),
        "hit_rate": (monthly > 0).mean(),
    }
    if turnover is not None:
        out["turnover"] = turnover.sum() / years
    return out

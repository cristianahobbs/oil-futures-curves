"""Run the carry backtest and the April 2020 case study; write output/ and the README findings.

    python main.py              # cached data in data/
    python main.py --refresh    # re-download from EIA
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

import curves as cv
import strategy as st
from data import COMMODITIES, load_cushing, load_futures, load_spot

ROOT = Path(__file__).parent
OUT = ROOT / "output"
README = ROOT / "README.md"
START, END = "2008-01-01", "2024-03-31"

NAMES = {"long": "Long-only, all four", "ts": "Long only when backwardated",
         "xs": "Carry long-short", "xs_sa": "Carry long-short, seasonally adjusted"}


def build(prices: pd.DataFrame, cfg: st.Config, near: int = 2, far: int = 4):
    R = st.daily_returns(prices.loc["2004":], cfg.hold).loc["2007-06":END]
    rolls = st.roll_days(R)
    dates = st.month_ends(R.index)
    dates = dates[dates >= "2007-12-01"]
    iv = st.inverse_vol(R, dates, cfg.vol_window)
    raw = pd.DataFrame({r: cv.carry(prices, r, near, far) for r in st.ROOTS}).ffill(limit=3)
    carry = raw.reindex(dates, method="ffill")
    carry_sa = raw.reindex(st.month_ends(raw.index)).apply(cv.seasonal_adjust).reindex(dates, method="ffill")
    weights = {"long": st.long_only(carry, iv), "ts": st.time_series(carry, iv),
               "xs": st.long_short(carry, iv, cfg.n_long), "xs_sa": st.long_short(carry_sa, iv, cfg.n_long)}
    sims = {k: st.simulate(w, R, rolls, cfg).loc[START:END] for k, w in weights.items()}
    return R, dates, carry, weights, sims


def per_commodity(R: pd.DataFrame, carry: pd.DataFrame, rolls: pd.DataFrame, cfg: st.Config) -> dict:
    """Each commodity alone: always long vs long only while backwardated."""
    out = {}
    for r in st.ROOTS:
        one = pd.DataFrame({r: 1.0}, index=carry.index).where(carry[[r]].notna(), 0.0)
        always = st.simulate(one, R[[r]], rolls[[r]], cfg).loc[START:END]
        gated = st.simulate(one.where(carry[[r]] > 0, 0.0), R[[r]], rolls[[r]], cfg).loc[START:END]
        months = carry[r].loc[START:END]
        m = (1 + R[r].loc[START:END]).groupby(R.loc[START:END].index.to_period("M")).prod() - 1
        sig = pd.Series(carry[r].to_numpy(), index=carry.index.to_period("M")).shift(1).reindex(m.index)
        out[r] = {
            "always": st.stats(always.ret), "backwardated_only": st.stats(gated.ret),
            "share_backwardated": float((months > 0).mean()),
            "next_month_if_backwardated": float(m[sig > 0].mean()),
            "next_month_if_contango": float(m[sig < 0].mean()),
        }
    return out


def roll_cost(prices: pd.DataFrame) -> dict:
    """Annual change in the front-month price vs the annual return from holding rolled futures."""
    out = {}
    for r in st.ROOTS:
        front = prices[f"{r}1"].dropna().loc[START:END]
        years = (front.index[-1] - front.index[0]).days / 365.25
        held = cv.held_returns(prices.loc["2007-12":END], r, 2).loc[START:END]
        price = (front.iloc[-1] / front.iloc[0]) ** (1 / years) - 1
        futures = (1 + held).prod() ** (1 / years) - 1
        out[r] = {"price": price, "futures": futures, "gap": futures - price}
    return out


def case_study_2020(prices: pd.DataFrame, cushing: pd.Series) -> dict:
    cl = prices[["CL1", "CL2", "CL3", "CL4"]].loc["2020-01":"2020-06"].dropna()
    low_day = cl["CL1"].idxmin()
    front = cv.held_returns(prices.loc["2019-12":"2020-06"], "CL", 1).loc["2020-03-01":"2020-04-30"]
    second = cv.held_returns(prices.loc["2019-12":"2020-06"], "CL", 2).loc["2020-03-01":"2020-04-30"]
    c20 = cushing.loc["2020"]
    upto = slice("2020-03-01", str(low_day.date()))
    return {
        "low_day": str(low_day.date()),
        "low_price": float(cl.loc[low_day, "CL1"]),
        "prev_close": float(cl["CL1"].shift(1).loc[low_day]),
        "c2_on_low_day": float(cl.loc[low_day, "CL2"]),
        "spread_c1_c2": float(cl.loc[low_day, "CL2"] - cl.loc[low_day, "CL1"]),
        "jan_curve": cl.loc["2020-01"].iloc[0].round(2).to_dict(),
        "jan_date": str(cl.loc["2020-01"].index[0].date()),
        "carry_c2_c4_low_day": float(cv.carry(prices, "CL").loc[low_day]),
        "front_month_low_day": float(front.loc[low_day]),
        "front_month_to_low_day": float((1 + front.loc[upto]).prod() - 1),
        "second_month_to_low_day": float((1 + second.loc[upto]).prod() - 1),
        "second_month_mar_apr": float((1 + second).prod() - 1),
        "cushing_peak_kbbl": float(c20.max()),
        "cushing_peak_date": str(c20.idxmax().date()),
        "cushing_feb_2020_kbbl": float(cushing.loc["2020-02"].iloc[-1]),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-readme", action="store_true")
    args = ap.parse_args()
    cfg = st.Config()

    prices = load_futures(refresh=args.refresh)
    cushing = load_cushing(refresh=args.refresh)
    load_spot(refresh=args.refresh)

    R, dates, carry, weights, sims = build(prices, cfg)
    rolls = st.roll_days(R)
    summary = {k: st.stats(s.ret, s.turnover) for k, s in sims.items()}
    corr = pd.DataFrame({k: s.ret for k, s in sims.items()}).corr().round(2)

    # Robustness: which contracts define the slope, and costs
    slope_grid = {}
    for near, far in [(1, 2), (2, 3), (2, 4), (1, 4)]:
        _, _, _, _, s2 = build(prices, cfg, near, far)
        slope_grid[f"C{near}-C{far}"] = {k: st.stats(s2[k].ret)["sharpe"] for k in ("ts", "xs", "xs_sa")}
    cost_grid = {}
    for bps in (0, 5, 10, 20):
        c2 = st.Config(cost_bps=bps, roll_bps=bps / 2)
        cost_grid[bps] = {k: st.stats(st.simulate(w, R, rolls, c2).loc[START:END].ret)["sharpe"]
                          for k, w in weights.items()}

    result = {
        "config": asdict(cfg), "start": START, "end": END, "summary": summary,
        "correlation": corr.to_dict(), "per_commodity": per_commodity(R, carry, rolls, cfg),
        "slope_grid": slope_grid, "cost_grid": cost_grid, "roll_cost": roll_cost(prices),
        "case_2020": case_study_2020(prices, cushing),
    }
    OUT.mkdir(exist_ok=True)
    daily = pd.DataFrame({k: s.ret for k, s in sims.items()})
    daily.to_csv(OUT / "daily_returns.csv", float_format="%.6f")
    carry.to_csv(OUT / "monthly_carry.csv", float_format="%.4f")
    (OUT / "results.json").write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")

    print(f"{'':40}{'CAGR':>8}{'Vol':>8}{'Sharpe':>8}{'t':>7}{'MaxDD':>8}")
    for k, s in summary.items():
        print(f"{NAMES[k]:40}{s['cagr']:8.1%}{s['vol']:8.1%}{s['sharpe']:8.2f}{s['t_stat']:7.2f}{s['max_dd']:8.1%}")
    print("\nPer commodity (Sharpe always long -> long only when backwardated):")
    for r, d in result["per_commodity"].items():
        print(f"  {r}: {d['always']['sharpe']:.2f} -> {d['backwardated_only']['sharpe']:.2f}   "
              f"next month {d['next_month_if_backwardated']:+.2%} backwardated vs {d['next_month_if_contango']:+.2%} contango")
    print("\nSlope definition:", json.dumps(slope_grid, default=lambda x: round(x, 2)))
    print("Costs:", json.dumps(cost_grid, default=lambda x: round(x, 2)))
    print("\n2020:", json.dumps(result["case_2020"], default=float))
    if not args.no_readme and README.exists():
        update_readme(result)


def pct(x: float) -> str:
    return f"{x:.1%}"


def findings_block(res: dict) -> str:
    s = res["summary"]
    order = list(NAMES)
    head = "| | " + " | ".join(NAMES[k] for k in order) + " |\n|---|" + "---|" * len(order) + "\n"
    rows = [
        ("Annual return", lambda d: pct(d["cagr"])),
        ("Volatility", lambda d: pct(d["vol"])),
        ("Sharpe", lambda d: f"{d['sharpe']:.2f}"),
        ("t-stat (Newey-West)", lambda d: f"{d['t_stat']:.2f}"),
        ("Max drawdown", lambda d: pct(d["max_dd"])),
        ("Worst month", lambda d: pct(d["worst_month"])),
        ("Annual turnover", lambda d: f"{d['turnover']:.1f}x"),
    ]
    table = head + "\n".join(f"| {n} | " + " | ".join(f(s[k]) for k in order) + " |" for n, f in rows)
    pc = res["per_commodity"]
    t2 = ("| | Share of months backwardated | Next-month return, backwardated | Next-month return, contango "
          "| Sharpe, always long | Sharpe, long only when backwardated |\n|---|---|---|---|---|---|\n")
    t2 += "\n".join(
        f"| {COMMODITIES[r]['name']} | {d['share_backwardated']:.0%} | {d['next_month_if_backwardated']:+.1%} | "
        f"{d['next_month_if_contango']:+.1%} | {d['always']['sharpe']:.2f} | {d['backwardated_only']['sharpe']:.2f} |"
        for r, d in pc.items())
    rc = res["roll_cost"]
    t3 = ("| | Front-month price, per year | Holding rolled futures, per year | Difference (roll yield) |\n"
          "|---|---|---|---|\n" + "\n".join(
              f"| {COMMODITIES[r]['name']} | {d['price']:+.1%} | {d['futures']:+.1%} | {d['gap']:+.1%} |"
              for r, d in rc.items()))
    return ("**What owning oil through futures actually earned.** Anything that holds futures (most oil and gas "
            "ETFs and ETCs) earns the futures return, not the price change. In contango every roll sells "
            "the cheap expiring contract and buys a dearer one.\n\n" + t3 + "\n\n" +
            f"**Carry strategies.** Backtest {res['start'][:7]} to {res['end'][:7]}, daily data, monthly rebalancing, second-month "
            f"contracts, net of costs, excess of cash. Generated by `python main.py`; raw numbers are in "
            f"[`output/`](output/).\n\n" + table + "\n\n**By commodity.** Does a backwardated curve at "
            "month-end predict next month's return?\n\n" + t2 + "\n\nHistorical simulation, not investment advice.")


def update_readme(res: dict) -> None:
    text = README.read_text(encoding="utf-8")
    new = re.sub(r"(<!-- findings:start -->\n).*?(<!-- findings:end -->)",
                 lambda m: m.group(1) + findings_block(res) + "\n" + m.group(2), text, flags=re.S)
    README.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    main()

"""Render README charts (light + dark PNGs). Run after main.py; update.py re-renders the live curves.

    python charts.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import pandas as pd  # noqa: E402

from data import COMMODITIES, load_cushing, load_futures, load_live_curves  # noqa: E402
from strategy import drawdown  # noqa: E402

ROOT = Path(__file__).parent
OUT = ROOT / "output"
CHARTS = ROOT / "docs" / "charts"

THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#898781",
              "grid": "#e1e0d9", "axis": "#c3c2b7", "s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a"},
    "dark": {"surface": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#898781",
             "grid": "#2c2c2a", "axis": "#383835", "s1": "#3987e5", "s2": "#d95926", "s3": "#199e70"},
}
plt.rcParams.update({"font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 10})


def style_axes(ax, t: dict, grid_axis: str = "y") -> None:
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["axis"])
    ax.tick_params(colors=t["muted"], length=0)
    ax.grid(axis=grid_axis, color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)


def title(ax, t: dict, text: str, sub: str) -> None:
    ax.set_title(text, loc="left", color=t["ink"], fontsize=12, fontweight="bold", pad=24)
    ax.text(0, 1.02, sub, transform=ax.transAxes, color=t["ink2"], fontsize=9.5, va="bottom")


def legend(ax, t: dict, **kw) -> None:
    ax.legend(frameon=False, labelcolor=t["ink2"], fontsize=9, **kw)


def save(fig, name: str, theme: str) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    suffix = "" if theme == "light" else "-dark"
    fig.savefig(CHARTS / f"{name}{suffix}.png", dpi=200, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)


def money(v: float, decimals: int = 2) -> str:
    return f"{'−' if v < 0 else ''}${abs(v):,.{decimals}f}"


def pct_axis(ax, decimals: int = 0) -> None:
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=decimals))


# ---------------------------------------------------------------------------
def equity(theme: str) -> None:
    t = THEMES[theme]
    r = pd.read_csv(OUT / "daily_returns.csv", index_col=0, parse_dates=True)
    lines = [("long", "Long-only, all four", {"color": t["muted"], "lw": 1.3, "ls": (0, (4, 3))}),
             ("ts", "Long only when backwardated", {"color": t["s1"], "lw": 1.8}),
             ("xs", "Carry long-short", {"color": t["s2"], "lw": 1.8}),
             ("xs_sa", "Carry long-short, seasonally adjusted", {"color": t["s3"], "lw": 1.8})]
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8.6, 6.2), facecolor=t["surface"], sharex=True,
                                  gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.12})
    style_axes(ax, t)
    style_axes(ax2, t)
    for col, label, kw in lines:
        wealth = (1 + r[col]).cumprod()
        ax.plot(wealth.index, wealth, label=label, **kw)
        ax.annotate(f"${wealth.iloc[-1]:.2f}", (wealth.index[-1], wealth.iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", va="center", color=t["ink2"], fontsize=9)
        ax2.plot(r.index, drawdown(r[col]), **kw)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v:g}"))
    ax.yaxis.set_minor_formatter(mtick.NullFormatter())
    ax.set_yticks([0.1, 0.25, 0.5, 1, 2])
    pct_axis(ax2)
    ax2.text(0, 1.02, "Drawdown from previous peak", transform=ax2.transAxes, color=t["ink2"], fontsize=9.5)
    legend(ax, t, loc="lower left")
    title(ax, t, "Growth of $1 in energy futures, 2008–2024",
          "Second-month WTI, gasoline, heating oil and natural gas; net of costs, excess of cash; log scale")
    save(fig, "equity", theme)


def predictive(theme: str) -> None:
    t = THEMES[theme]
    pc = json.loads((OUT / "results.json").read_text(encoding="utf-8"))["per_commodity"]
    roots = list(pc)
    fig, ax = plt.subplots(figsize=(8.6, 3.6), facecolor=t["surface"])
    style_axes(ax, t)
    x = range(len(roots))
    w = 0.36
    b = [pc[r]["next_month_if_backwardated"] for r in roots]
    c = [pc[r]["next_month_if_contango"] for r in roots]
    ax.bar([i - w / 2 - 0.01 for i in x], b, w, color=t["s1"], label="After a backwardated month-end")
    ax.bar([i + w / 2 + 0.01 for i in x], c, w, color=t["s2"], label="After a contango month-end")
    for i, (vb, vc) in enumerate(zip(b, c)):
        for xpos, v in ((i - w / 2 - 0.01, vb), (i + w / 2 + 0.01, vc)):
            ax.annotate(f"{v:+.1%}", (xpos, v), xytext=(0, 4 if v >= 0 else -12), textcoords="offset points",
                        ha="center", color=t["ink2"], fontsize=8.5)
    ax.axhline(0, color=t["axis"], lw=0.8)
    ax.set_xticks(list(x), [COMMODITIES[r]["name"] for r in roots], color=t["ink2"])
    pct_axis(ax, 0)
    legend(ax, t, loc="lower left")
    title(ax, t, "Average next-month return by curve shape, 2008–2024",
          "Backwardation helps crude and heating oil; gasoline and gas have seasonal curves that mislead")
    save(fig, "predictive", theme)


def april_2020(theme: str) -> None:
    t = THEMES[theme]
    f = load_futures().loc["2020-02-15":"2020-05-31"]
    cush = load_cushing().loc["2019-06":"2020-12"] / 1000
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8.6, 6.0), facecolor=t["surface"],
                                  gridspec_kw={"height_ratios": [1.8, 1], "hspace": 0.45})
    style_axes(ax, t)
    style_axes(ax2, t)
    ax.plot(f.index, f["CL1"], color=t["s2"], lw=1.8, label="Front-month contract (May, then June)")
    ax.plot(f.index, f["CL2"], color=t["s1"], lw=1.8, label="Second-month contract")
    ax.axhline(0, color=t["axis"], lw=0.8)
    low = f["CL1"].idxmin()
    ax.annotate(f"{low:%d %b}: {money(f.loc[low, 'CL1'])}", (low, f.loc[low, "CL1"]), xytext=(12, 0),
                textcoords="offset points", va="center", color=t["ink"], fontsize=9)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: money(v, 0)))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    legend(ax, t, loc="lower left")
    title(ax, t, "WTI crude settles at −$37.63",
          "The expiring May contract had nowhere to go; the June contract bottomed at $11.57")
    ax2.plot(cush.index, cush, color=t["s3"], lw=1.8)
    ax2.fill_between(cush.index, cush, cush.min() * 0.9, color=t["s3"], alpha=0.12, lw=0)
    ax2.set_ylim(cush.min() * 0.9, cush.max() * 1.08)
    ax2.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"{v:.0f}m"))
    ax2.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))
    ax2.set_title("Crude stocks at Cushing, Oklahoma (million barrels, weekly)", loc="left",
                  color=t["ink2"], fontsize=9.5)
    save(fig, "april_2020", theme)


def snapshots(theme: str) -> None:
    """WTI curve (contracts 1-4) on a few memorable days, relative to the front contract."""
    t = THEMES[theme]
    f = load_futures()
    days = [("2008-07-03", "Jul 2008 peak", t["s1"]), ("2020-04-22", "Apr 2020 glut", t["s2"]),
            ("2022-03-08", "Mar 2022 Russia shock", t["s3"])]
    fig, ax = plt.subplots(figsize=(8.6, 3.8), facecolor=t["surface"])
    style_axes(ax, t)
    for d, label, color in days:
        row = f.loc[:d, ["CL1", "CL2", "CL3", "CL4"]].dropna().iloc[-1]
        ax.plot([1, 2, 3, 4], row.to_numpy() / row.iloc[0], color=color, lw=2, marker="o", ms=6,
                markeredgecolor=t["surface"], markeredgewidth=2, label=f"{label} (${row.iloc[0]:.0f} front)")
    ax.set_xticks([1, 2, 3, 4], ["1st", "2nd", "3rd", "4th"], color=t["ink2"])
    pct_axis(ax)
    ax.axhline(1, color=t["axis"], lw=0.8)
    ax.set_xlabel("Contract (months to delivery)", color=t["muted"])
    legend(ax, t, loc="center right")
    title(ax, t, "What contango and backwardation look like",
          "WTI futures by delivery month, as a % of the front contract. Rising = contango, falling = backwardation")
    save(fig, "snapshots", theme)


def live_curves(live: pd.DataFrame | None = None) -> None:
    live = load_live_curves() if live is None else live
    as_of_file = ROOT / "data" / "live_curves_as_of.txt"
    as_of = as_of_file.read_text(encoding="utf-8").strip() if as_of_file.exists() else ""
    for theme, t in THEMES.items():
        fig, axes = plt.subplots(2, 2, figsize=(8.6, 5.4), facecolor=t["surface"])
        fig.subplots_adjust(hspace=0.55, wspace=0.25)
        for ax, root in zip(axes.flat, COMMODITIES):
            style_axes(ax, t)
            c = live[root].dropna()
            ax.plot(c.index, c, color=t["s1"], lw=2, marker="o", ms=3.5)
            ax.set_title(f"{COMMODITIES[root]['name']} ({COMMODITIES[root]['unit']})", loc="left",
                         color=t["ink"], fontsize=10)
            ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))
            ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=[1, 7]))
        fig.suptitle(f"Futures curves on {as_of}", x=0.125, ha="left", color=t["ink"], fontsize=12,
                     fontweight="bold")
        save(fig, "live_curves", theme)


def main() -> None:
    for theme in THEMES:
        equity(theme)
        predictive(theme)
        april_2020(theme)
        snapshots(theme)
    live_curves()
    print(f"Charts written to {CHARTS}")


if __name__ == "__main__":
    main()

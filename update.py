"""Daily brief: today's curves, carry signals, spot prices, Cushing stocks and energy headlines.

Refreshes the live data, writes docs/daily/<date>.md, re-renders the live-curve chart and replaces
the "Today" section of the README. Run by .github/workflows/daily.yml every weekday.

    python update.py             # download fresh data
    python update.py --offline   # rebuild from what is already in data/
"""
from __future__ import annotations

import argparse
import email.utils
import re
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import curves as cv
from data import COMMODITIES, DATA, _get, load_cushing, load_futures, load_live_curves, load_spot

ROOT = Path(__file__).parent
DAILY = ROOT / "docs" / "daily"
README = ROOT / "README.md"
NEWS_QUERY = '"crude oil" OR OPEC OR "oil prices" OR gasoline prices OR diesel prices OR "natural gas prices" when:1d'
FEEDS = {
    "headlines": "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": NEWS_QUERY, "hl": "en-US", "gl": "US", "ceid": "US:en"}),
    "eia": "https://www.eia.gov/rss/todayinenergy.xml",
}


# --- signals from today's curve --------------------------------------------
def live_carry(curve: pd.Series) -> float:
    """Same definition as the backtest: slope between the 2nd and 4th listed contracts, annualised."""
    c = curve.dropna()
    if len(c) < 4 or (c.iloc[[1, 3]] <= 0).any():
        return np.nan
    months = (c.index[3].year - c.index[1].year) * 12 + c.index[3].month - c.index[1].month
    return float(np.log(c.iloc[1] / c.iloc[3]) * 12 / months)


def seasonal_norm(prices: pd.DataFrame, root: str, month: int, years: int = 5) -> float:
    """Average month-end carry in this calendar month over the last `years` years of EIA history."""
    c = cv.carry(prices, root).dropna()
    me = c.groupby(c.index.to_period("M")).last()
    same = me[me.index.month == month]
    return float(same.iloc[-years:].mean())


def signals(live: pd.DataFrame, prices: pd.DataFrame, today: date) -> pd.DataFrame:
    rows = {}
    for r in COMMODITIES:
        curve = live[r].dropna()
        c = live_carry(curve)
        norm = seasonal_norm(prices, r, today.month)
        rows[r] = {"front": curve.iloc[0] if len(curve) else np.nan,
                   "front_month": curve.index[0].strftime("%b %Y") if len(curve) else "",
                   "twelfth": curve.iloc[11] if len(curve) > 11 else np.nan,
                   "carry": c, "state": cv.curve_state(c), "seasonal_norm": norm, "carry_sa": c - norm}
    df = pd.DataFrame(rows).T
    sa = df["carry_sa"].astype(float)
    df["rank_sa"] = sa.rank(ascending=False)
    df["long_short"] = np.where(df["rank_sa"] <= 2, "long", "short")
    df["backwardated_only"] = np.where(df["carry"].astype(float) > 0, "long", "flat")
    return df


# --- news ------------------------------------------------------------------
ENERGY_WORDS = re.compile(r"\b(oil|crude|opec|brent|wti|gas|gasoline|diesel|fuel|petrol|lng|refin\w*|barrels?|energy)\b", re.I)


def fetch_feed(url: str, limit: int, newest_first: bool = True, energy_only: bool = False) -> list[dict]:
    try:
        root = ET.fromstring(_get(url))
    except Exception as e:  # news is optional; never fail the update over it
        print(f"news feed failed: {e}")
        return []
    items, seen = [], set()
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        source = (it.findtext("source") or "").strip()
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3]
        key = re.sub(r"\W+", " ", re.sub(r"\s*--\s*update$", "", title.lower()))[:40]
        if not title or key in seen or (energy_only and not ENERGY_WORDS.search(title)):
            continue
        seen.add(key)
        try:
            when = email.utils.parsedate_to_datetime(it.findtext("pubDate"))
        except (TypeError, ValueError):
            when = datetime.now(timezone.utc)
        items.append({"title": title, "link": (it.findtext("link") or "").strip(), "source": source, "when": when})
    if newest_first:
        items.sort(key=lambda d: d["when"], reverse=True)
    return items[:limit]


def md_link(item: dict) -> str:
    title = item["title"].replace("[", "(").replace("]", ")")
    src = f" ({item['source']})" if item["source"] else ""
    return f"[{title}]({item['link']}){src}"


# --- write-up --------------------------------------------------------------
def fmt_price(root: str, x: float) -> str:
    return "n/a" if pd.isna(x) else (f"${x:,.2f}" if root in ("CL", "NG") else f"${x:.3f}")


def spot_lines(spot: pd.DataFrame) -> list[str]:
    s = spot.dropna(how="all")
    last = s.index[-1]
    out = []
    for name in ("WTI", "Brent"):
        col = s[name].dropna()
        now = col.iloc[-1]
        wk = col.asof(last - pd.Timedelta(days=7))
        mo = col.asof(last - pd.Timedelta(days=30))
        out.append(f"| {name} | ${now:,.2f} | {now / wk - 1:+.1%} | {now / mo - 1:+.1%} |")
    spread = s["Brent"].dropna().iloc[-1] - s["WTI"].dropna().iloc[-1]
    return out, last, spread


def brief(today: date, sig: pd.DataFrame, spot: pd.DataFrame, cushing: pd.Series,
          headlines: list[dict], eia: list[dict]) -> str:
    rows = "\n".join(
        f"| {COMMODITIES[r]['name']} | {fmt_price(r, d['front'])} ({d['front_month']}) | "
        f"{fmt_price(r, d['twelfth'])} | {d['state']} ({d['carry']:+.1%}) | {d['carry_sa']:+.1%} | "
        f"{d['backwardated_only']} | {d['long_short']} |"
        for r, d in sig.iterrows())
    sp, sp_date, spread = spot_lines(spot)
    wk = cushing.iloc[-1] - cushing.iloc[-2]
    same_week = cushing[(cushing.index.isocalendar().week == cushing.index[-1].isocalendar().week)
                        & (cushing.index.year < cushing.index[-1].year)].iloc[-5:].mean()
    news = "\n".join(f"- {md_link(i)}" for i in headlines) or "- No headlines retrieved today."
    eia_news = "\n".join(f"- {md_link(i)}" for i in eia)
    return f"""### Energy brief: {today:%A %d %B %Y}

**Curves and signals** (futures from Yahoo Finance; carry is the annualised slope between the 2nd and
4th listed contracts, the same definition as the backtest)

| | Front month | 12th month | Curve | Carry vs 5-year norm for {today:%B} | Long only when backwardated | Carry long-short |
|---|---|---|---|---|---|---|
{rows}

**Spot** (EIA, as of {sp_date:%d %b %Y}). Brent trades ${spread:,.2f} above WTI.

| | Price | 1 week | 1 month |
|---|---|---|---|
{chr(10).join(sp)}

**Cushing crude stocks** (EIA weekly, {cushing.index[-1]:%d %b %Y}): {cushing.iloc[-1] / 1000:.1f} million barrels,
{wk / 1000:+.1f} million on the week, vs {same_week / 1000:.1f} million on average for this week over the past five years.

**Headlines**

{news}

**From EIA**

{eia_news}

<sub>Signals follow the rules tested in this repo. The backtest shows they are weak, so treat them as
a description of the curve, not a recommendation. Not investment advice.</sub>
"""


def replace_block(text: str, tag: str, body: str) -> str:
    return re.sub(rf"(<!-- {tag}:start -->\n).*?(<!-- {tag}:end -->)",
                  lambda m: m.group(1) + body + "\n" + m.group(2), text, flags=re.S)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()
    fresh = not args.offline
    today = date.today()

    prices = load_futures()
    live = load_live_curves(refresh=fresh)
    if live.notna().sum().min() < 4:
        raise SystemExit("Live curves incomplete; keeping the previous brief.")
    spot = load_spot(refresh=fresh)
    cushing = load_cushing(refresh=fresh)
    sig = signals(live, prices, today)
    headlines = fetch_feed(FEEDS["headlines"], 8, energy_only=True) if fresh else []
    eia = fetch_feed(FEEDS["eia"], 3, newest_first=False) if fresh else []

    text = brief(today, sig, spot, cushing, headlines, eia)
    DAILY.mkdir(parents=True, exist_ok=True)
    (DAILY / f"{today.isoformat()}.md").write_text(text, encoding="utf-8")
    sig.to_csv(DATA / "signals_today.csv", float_format="%.4f")

    import charts  # noqa: PLC0415  (matplotlib is slow to import; only needed here)
    charts.live_curves(live)

    if README.exists():
        archive = f"\n[Previous briefs](docs/daily/)"
        README.write_text(replace_block(README.read_text(encoding="utf-8"), "today", text + archive),
                          encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

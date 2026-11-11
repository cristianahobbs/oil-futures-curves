"""Price data: EIA history for the first four NYMEX contracts, and today's full curve from Yahoo.

EIA publishes daily settlements for contracts 1-4 of WTI crude, RBOB gasoline, heating oil and
natural gas. It stopped updating these series on 2024-04-05, so the history ends there. Spot
prices and Cushing stocks are still current. Everything is cached under data/ so runs are
reproducible offline; pass refresh=True to re-download.
"""
from __future__ import annotations

import io
import json
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
DATA = ROOT / "data"

COMMODITIES = {
    "CL": {"name": "WTI crude oil", "unit": "$/bbl", "eia": ("pet", "RCLC{k}")},
    "RB": {"name": "RBOB gasoline", "unit": "$/gal", "eia": ("pet", "EER_EPMRR_PE{k}_Y35NY_DPG")},
    "HO": {"name": "Heating oil / ULSD", "unit": "$/gal", "eia": ("pet", "EER_EPD2F_PE{k}_Y35NY_DPG")},
    "NG": {"name": "Natural gas", "unit": "$/MMBtu", "eia": ("ng", "RNGC{k}")},
}
SPOT = {"WTI": ("pet", "RWTC"), "Brent": ("pet", "RBRTE")}
CUSHING = ("pet", "W_EPC0_SAX_YCUOK_MBBL")  # weekly crude stocks at Cushing, thousand barrels
MONTH_CODES = "FGHJKMNQUVXZ"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.URLError:
            if attempt == 3:
                raise
            time.sleep(5 * 2 ** attempt)


def eia_series(path: str, series: str, freq: str = "d") -> pd.Series:
    raw = _get(f"https://www.eia.gov/dnav/{path}/hist_xls/{series}{freq}.xls")
    df = pd.read_excel(io.BytesIO(raw), sheet_name="Data 1", skiprows=2, engine="xlrd")
    s = pd.Series(df.iloc[:, 1].to_numpy(dtype=float), index=pd.to_datetime(df.iloc[:, 0]), name=series)
    return s.dropna().sort_index()


def _cached(name: str, build, refresh: bool) -> pd.DataFrame:
    path = DATA / name
    if path.exists() and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    df = build()
    DATA.mkdir(exist_ok=True)
    df.to_csv(path, float_format="%.5f")
    return df


def load_futures(refresh: bool = False) -> pd.DataFrame:
    """Daily settlements, columns like CL1..CL4 (CL1 = nearest unexpired contract)."""
    def build():
        cols = {}
        for root, spec in COMMODITIES.items():
            path, pattern = spec["eia"]
            for k in range(1, 5):
                cols[f"{root}{k}"] = eia_series(path, pattern.format(k=k))
        return pd.DataFrame(cols).sort_index()
    return _cached("futures.csv", build, refresh)


def load_spot(refresh: bool = False) -> pd.DataFrame:
    return _cached("spot.csv", lambda: pd.DataFrame(
        {k: eia_series(*v) for k, v in SPOT.items()}).sort_index(), refresh)


def load_cushing(refresh: bool = False) -> pd.Series:
    df = _cached("cushing.csv", lambda: eia_series(*CUSHING, freq="w").rename("cushing_kbbl").to_frame(),
                 refresh)
    return df.iloc[:, 0]


# --- today's full curve ----------------------------------------------------
def contract_months(n: int, today: date) -> list[tuple[int, int]]:
    """Next n (year, month) delivery months starting next calendar month."""
    out, y, m = [], today.year, today.month
    for _ in range(n):
        m += 1
        if m > 12:
            y, m = y + 1, 1
        out.append((y, m))
    return out


def yahoo_symbol(root: str, year: int, month: int) -> str:
    return f"{root}{MONTH_CODES[month - 1]}{year % 100:02d}.NYM"


def live_curve(root: str, months: int = 24, today: date | None = None) -> pd.Series:
    """Last price for each listed contract, indexed by delivery month. Missing contracts are skipped."""
    prices = {}
    for y, m in contract_months(months, today or date.today()):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(root, y, m)}?range=5d&interval=1d"
        try:
            meta = json.loads(_get(url))["chart"]["result"][0]["meta"]
        except (urllib.error.HTTPError, KeyError, TypeError):
            continue
        traded = pd.Timestamp(meta.get("regularMarketTime") or 0, unit="s")
        fresh = (pd.Timestamp(today or date.today()) - traded).days <= 5  # expired contracts keep a stale quote
        if meta.get("regularMarketPrice") is not None and fresh:
            prices[pd.Timestamp(y, m, 1)] = float(meta["regularMarketPrice"])
    return pd.Series(prices, name=root, dtype=float)


def load_live_curves(refresh: bool = False) -> pd.DataFrame:
    """Live curves for all four commodities, one row per delivery month; saved with the download date."""
    path = DATA / "live_curves.csv"
    if path.exists() and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    df = pd.DataFrame({root: live_curve(root) for root in COMMODITIES})
    df.attrs["as_of"] = date.today().isoformat()
    DATA.mkdir(exist_ok=True)
    df.to_csv(path, float_format="%.4f")
    (DATA / "live_curves_as_of.txt").write_text(date.today().isoformat(), encoding="utf-8")
    return df
